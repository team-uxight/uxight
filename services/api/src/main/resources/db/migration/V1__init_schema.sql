-- UXight DDL v1 - MySQL 8
-- 최종 스키마(설계/데이터베이스/schema_blueprint.sql, 26.10.08 기준) 중 Walking Skeleton 파이프라인이 쓰는 테이블 7개.
--   users · projects · tasks · personas · runs · run_personas · run_metrics
-- 나머지 테이블(policies · test_accounts · findings · improvements · approvals · patch_versions · audit_log · refresh_tokens)과
-- fk_runs_improvement 제약은 해당 기능을 구현할 때 V2 부터 추가한다. runs.improvement_id 컬럼은 있으나 FK 는 아직 없다.

SET NAMES utf8mb4;

-- ───────── 설정 계층 (전부 Spring 소유) ─────────

CREATE TABLE `users` (                                  -- 계정
  `user_id`       BIGINT       NOT NULL AUTO_INCREMENT,
  `email`         VARCHAR(255) NOT NULL,                -- 로그인 ID
  `password_hash` VARCHAR(255),                         -- local 가입만. Google 전용 계정이면 NULL
  `auth_provider` VARCHAR(20)  NOT NULL,                -- local / google
  `google_sub`    VARCHAR(255),                         -- Google 계정 고유 식별자
  `name`          VARCHAR(100),                         -- 표시 이름
  `role`          VARCHAR(20)  NOT NULL,                -- admin / researcher
  `is_active`     BOOLEAN      NOT NULL,                -- 계정 비활성화 플래그
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uk_users_email` (`email`),
  UNIQUE KEY `uk_users_google_sub` (`google_sub`),
  CONSTRAINT `ck_users_role`
    CHECK (`role` IN ('admin', 'researcher')),
  CONSTRAINT `ck_users_auth_provider`
    CHECK (`auth_provider` IN ('local', 'google')),
  CONSTRAINT `ck_users_credential`          -- 로그인 수단이 하나도 없는 계정 방지
    CHECK (
      (`auth_provider` = 'local'  AND `password_hash` IS NOT NULL)
      OR
      (`auth_provider` = 'google' AND `google_sub`    IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- is_active: 계정을 꺼도 이미 발급된 JWT 는 만료 전까지 유효하다. 그래서 access 토큰에는 userId 만 담고,
--   role 과 is_active 는 매 요청 DB 에서 확인한다. refresh 토큰으로 재발급할 때도 확인한다.

CREATE TABLE `projects` (                               -- 대상 사이트 단위. 실행보다 한 층 위
  `project_id`      BIGINT        NOT NULL AUTO_INCREMENT,
  `user_id`         BIGINT        NOT NULL,             -- 소유 리서처
  `title`            VARCHAR(100)  NOT NULL,             -- 제목
  `target_url`      VARCHAR(2048) NOT NULL,             -- 시작 URL
  `description`     TEXT,								-- 설명 / 애플리케이션에서 길이 상한 설정
  `allowed_domains` JSON          NOT NULL,             -- 가드 허용 도메인 목록
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`project_id`),
  KEY `ix_projects_user_id` (`user_id`),
  CONSTRAINT `fk_projects_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- allowed_domains: Agent 가 이 목록 밖 도메인으로 나가려 하면 Runner 가 차단하고
--   blocked step 으로 기록한다(§9). 실험 요청마다 입력받는 값이 아니라 project 에 고정해야 통제로 기능한다.
--   회차는 요청 시점 값을 allowed_domains_snapshot으로 가진다.

CREATE TABLE `tasks` (                                  -- 과업 정의
  `task_id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `project_id`       BIGINT       NOT NULL,
  `goal`             VARCHAR(200) NOT NULL,             -- 사람이 읽는 목표 문장
  `success_rule`     TEXT         NOT NULL,             -- Agent가 제안하는 성공 기준(메인)
  `success_url`      VARCHAR(2048) NOT NULL,             -- 성공 기준 URL(보조)
  `is_one_shot`      BOOLEAN      NOT NULL DEFAULT false,             -- 1회성 Task 제외 플래그 (미결)
  `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`task_id`),
  KEY `ix_tasks_project_id` (`project_id`),
  CONSTRAINT `fk_tasks_project`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- success_url: Task 성공 판정의 보조 기준이다. Agent가 스스로 'done'을 냈는지를 메인 기준으로 한다.
-- is_one_shot: 해지·탈퇴처럼 한 번 하면 되돌릴 수 없는 Task (D19). true 면 실험 대상에서
--   제외한다 — 첫 Persona 의 성공이 나머지 Persona 의 화면을 바꿔 버린다.

CREATE TABLE `personas` (                               -- 가상 사용자 정의
  `persona_id` BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT,                                  -- 소유 유저 / NULL: 관리자 소유 페르소나로, 모든 프로젝트에 적용되는 공용 페르소나
  `name`       VARCHAR(100) NOT NULL,                   -- 표시 이름
  `profile`    JSON         NOT NULL,                   -- 속성 묶음
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`persona_id`),
  KEY `ix_personas_user_id` (`user_id`),
  CONSTRAINT `fk_personas_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- profile: 웹 숙련도 · 사용 기기 · 도메인 지식 · 배경. 이 값이 프롬프트로 들어가 Agent
--   행동을 좌우한다. domainKnowledge 는 대상 사이트 분야에 대한 상대적 수준(low / mid / high)으로 정의한다.
--   나머지 속성의 데이터 형식(등급 vs 척도 vs 서술형)은 미확정 (GACA-66).

-- ───────── 실행 계층 ─────────

CREATE TABLE `runs` (                                   -- 회차 1회 = Persona N명 전체
  `run_id`              BIGINT        NOT NULL AUTO_INCREMENT,
  `project_id`          BIGINT        NOT NULL,         -- [S]
  `task_id`             BIGINT        NOT NULL,         -- [S]
  `mode`                VARCHAR(20)   NOT NULL,         -- [S] diagnose / improve / loop
  `loop_max`            INT,                            -- [S] mode='loop'일 때 최대 회차 수(최초 회차 포함)
  `parent_run_id`       BIGINT,                         -- [S] 부모 회차 식별자.
  `first_run_id`        BIGINT,                         -- [S] 실험 식별자. 최초 회차의 run_id
  `improvement_id`      BIGINT,                         -- [S] 검증 대상 개선안
  `target_url_snapshot` VARCHAR(2048) NOT NULL,         -- [S] 실험 요청 시점 URL 사본
  `allowed_domains_snapshot` JSON     NOT NULL,         -- [S] 실험 요청 시점 허용 도메인 사본
  `task_snapshot`       JSON          NOT NULL,         -- [S] 실험 요청 시점 Task 사본
  `policy_snapshot`     JSON          NOT NULL,         -- [S] 실험 요청 시점 정책 사본
  `persona_snapshot`    JSON          NOT NULL,         -- [S] 실험 요청 시점 Persona 사본
  `dispatch_state`      VARCHAR(20),                    -- [S] sent / unreachable / timeout
  `cancel_requested`    BOOLEAN       NOT NULL DEFAULT false,         -- [S] kill switch
  `status`              VARCHAR(20)   NOT NULL,         -- [P] queued/accepted/running/done/failed/cancelled
  `progress`            INT,                            -- [P] 완료 Persona 수
  `heartbeat_at`        DATETIME,                       -- [P] 살아 있음 신호
  `error`               TEXT,                           -- [P] 실패 사유
  `tokens`              BIGINT,                         -- [P] 누적 토큰
  `cost_usd`            DECIMAL(10,4),                  -- [P] 누적 비용
  `accepted_at`         DATETIME,                       -- [P]
  `started_at`          DATETIME,                       -- [P]
  `finished_at`         DATETIME,                       -- [P]
  `created_at`          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- [S]
  PRIMARY KEY (`run_id`),
  KEY `ix_runs_status` (`status`),
  KEY `ix_runs_project_created` (`project_id`, `created_at`),
  KEY `ix_runs_task_id` (`task_id`),
  KEY `ix_runs_parent_run_id` (`parent_run_id`),
  KEY `ix_runs_first_run_id` (`first_run_id`),
  KEY `ix_runs_improvement_id` (`improvement_id`),
  CONSTRAINT `fk_runs_project`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`),
  CONSTRAINT `fk_runs_task`
    FOREIGN KEY (`task_id`) REFERENCES `tasks` (`task_id`),
  CONSTRAINT `fk_runs_parent_run`
    FOREIGN KEY (`parent_run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `fk_runs_first_run`
    FOREIGN KEY (`first_run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `ck_runs_mode`
    CHECK (`mode` IN ('diagnose', 'improve', 'loop')),
  CONSTRAINT `ck_runs_status`
    CHECK (`status` IN ('queued', 'accepted', 'running', 'done', 'failed', 'cancelled')),
  CONSTRAINT `ck_runs_dispatch_state`       -- NULL = 아직 호출 전
    CHECK (`dispatch_state` IN ('sent', 'unreachable', 'timeout')),
  CONSTRAINT `ck_runs_non_negative`
    CHECK (
          (`progress` IS NULL OR `progress` >= 0)
      AND (`tokens`   IS NULL OR `tokens`   >= 0)
      AND (`cost_usd` IS NULL OR `cost_usd` >= 0)
      AND (`loop_max` IS NULL OR `loop_max` >  0)
    )
  -- fk_runs_improvement 는 improvements 테이블을 만드는 마이그레이션에서 ALTER 로 추가한다. runs → improvements → findings → runs
  -- 가 닫힌 고리라 어느 순서로 놓아도 하나는 미완성이 되기 때문. 실제 데이터 사이클은 아니다.
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- status: 이 컬럼을 UPDATE 하는 쪽은 Python 하나뿐이다. 단 하나의 예외가 INSERT 시점으로,
--   Spring 이 초기값 'queued' 를 넣는다. Python 이 재시작하면 queued · accepted 인 행을
--   스캔해 집어 간다 — 대기열의 실체가 이 queued 행들이다. running 인 행은 다시 실행하지 않고
--   failed(취소 요청된 행은 cancelled)로 기록하며, 그 회차의 running 인 run_personas 행도 정리한다.
--   accepted 는 실행 시작이 아니라 접수다. 동시 실행 한도가 차 있으면 accepted 로 자리를 기다린다.
-- dispatch_state: Spring 이 POST /runs 를 부른 결과만 기록한다. status 를 쓰지 않는 이유가
--   중요하다. 타임아웃은 "응답을 못 받았다" 일 뿐 Python 이 이미 수락해 돌고 있을 수 있다.
--   여기서 Spring 이 status=failed 를 쓰면 화면은 실패를 보여주는데 run 은 계속 도는 상태가 된다.
--   대신 Spring 은 queued로 일정 시간 남아 있는 회차에 POST /runs 를 다시 보낸다(재전송, 취소 요청된 회차 포함).
--   POST /runs가 멱등이라 이미 받은 회차에는 200만 돌아온다.
-- cancel_requested: 취소 요청은 실험 단위로 받고, Spring 이 그 실험의 마지막 회차 하나에만 기록한다. 마지막 회차가
--   진행 중(queued · accepted · running)이거나, done 이고 다음 회차 승인을 기다리는 경우만 받는다. Spring 은 프로젝트
--   행을 잠근 뒤 기록한다 — 승인 대기 중인 회차를 두고 다음 회차 승인과 경쟁하기 때문이다.
--   전체 중단(kill switch)은 진행 중인 회차에만 기록한다.
--   running 인 회차는 Watcher 가 매 스텝 경계에서 확인하고 10초 안에 브라우저 context 를 폐기한다.
--   queued · accepted 인 회차는 Python 이 실행을 시작하기 전에 확인한다. done 인 회차는 Python 이 읽지 않으며,
--   기록되면 그 회차에서 다음 회차를 승인할 수 없다.
--   Spring 이 직접 status 를 cancelled 로 바꾸지 않는다 — 실제 중단 시점을 아는 건 Python 이다.
-- heartbeat_at: Watcher 가 스텝마다 갱신한다. Spring은 조회 시 now - heartbeat_at 이 임계를
--   넘고 status='running' 이면 응답에 stale 표시만 싣는다. 자동으로 failed 로 바꾸지 않는다.
-- mode: 회차가 파이프라인을 어디까지 진행하는지 정한다.
--   loop: 개선안까지 진행한 뒤, 리서처가 승인한 개선안을 주입한 다음 회차를 loop_max 회차까지 반복한다.
--   다음 회차마다 새 runs 행을 INSERT하고, 다음 회차도 mode='loop'를 유지한다.
-- loop_max: mode='loop'일 때만 사용한다. 다음 회차에도 최초 회차의 값을 그대로 복사한다.
-- parent_run_id · improvement_id: 다음 회차에만 사용한다. parent_run_id는 직전 회차,
--   improvement_id는 이번 회차를 만든 승인 개선안이다. 이전 회차들의 개선안도 누적해 주입하므로,
--   실제로 주입된 패치 전체는 patch_versions 에 있다. 최초 회차는 둘 다 NULL이다.
-- first_run_id: 회차가 속한 실험의 식별자(최초 회차의 run_id). 최초 회차는 run_id가 INSERT 후에 정해지므로
--   Spring이 같은 트랜잭션 안에서 자기 run_id로 UPDATE 하고, 다음 회차는 직전 회차의 값을 복사한다.
--   NULL은 최초 회차를 만드는 트랜잭션 안에서만 존재하며, 커밋된 행에는 항상 값이 있다.
--   parent_run_id 사슬과 같은 정보지만, 실험 단위 조회(취소 대상 회차, 회차 목록, 실험 이력, 결과 비교)를
--   사슬 탐색 없이 하기 위해 둔다. INSERT 이후 바뀌지 않으므로 parent_run_id 와 어긋날 여지는 INSERT 코드뿐이다.
--   회차는 first_run_id가 같은 회차 중 run_id가 해당 회차 이하인 회차의 개수로 센다. 다음 회차는 이전 회차가
--   종료되고 승인된 뒤에만 생성되므로 run_id 순서가 회차 순서와 같다.
-- 스냅샷 컬럼 다섯 개: 최초 회차는 Spring이 INSERT 할 때 만들고, 다음 회차는 직전 회차의 값을 그대로 복사한다.
--   한 실험의 회차는 모두 같은 스냅샷으로 실행한다. daily_token_budget은 넣지 않는다(policies 참고).

CREATE TABLE `run_personas` (                           -- Persona 한 명의 실행 결과 [P]
  `run_persona_id` BIGINT        NOT NULL AUTO_INCREMENT,
  `run_id`         BIGINT        NOT NULL,
  `persona_id`     BIGINT        NOT NULL,              -- 정의 참조
  `status`         VARCHAR(20)   NOT NULL,              -- running / done / max_steps / fail / timeout / cancelled : 'done'인 경우 성공 (메인 판정 기준)
  `url_reached`   BOOLEAN,               			    -- 성공 보조 판정 — success_url 일치 여부
  `steps`          INT,                                 -- 총 스텝 수
  `backtracks`     INT,                                 -- 뒤로가기 횟수
  `tokens`         BIGINT,                              -- 누적 토큰
  `cost_usd`       DECIMAL(10,4),                       -- 누적 비용
  `log_path`       VARCHAR(500),                        -- steps.jsonl 파일 경로
  `started_at`     DATETIME,
  `finished_at`    DATETIME,
  PRIMARY KEY (`run_persona_id`),
  UNIQUE KEY `uk_run_personas_run_persona` (`run_id`, `persona_id`),  -- 같은 Persona 행 중복 생성 방지
  KEY `ix_run_personas_persona_id` (`persona_id`),
  CONSTRAINT `fk_run_personas_run`
    FOREIGN KEY (`run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `fk_run_personas_persona`
    FOREIGN KEY (`persona_id`) REFERENCES `personas` (`persona_id`),
  CONSTRAINT `ck_run_personas_status`
    CHECK (`status` IN ('running', 'done', 'max_steps', 'fail', 'timeout', 'cancelled')),
  CONSTRAINT `ck_run_personas_non_negative`
    CHECK (
          (`steps`      IS NULL OR `steps`      >= 0)
      AND (`backtracks` IS NULL OR `backtracks` >= 0)
      AND (`tokens`     IS NULL OR `tokens`     >= 0)
      AND (`cost_usd`   IS NULL OR `cost_usd`   >= 0)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- persona_id: 이건 참조일 뿐 실행에 쓰인 실제 값은 runs.persona_snapshot 안에 있다.
--   personas 행이 나중에 수정돼도 과거 회차가 재현 가능해야 하기 때문이다.
-- tokens · cost_usd: 스텝마다 갱신된다. 실시간 화면의 누적 비용이 여기서 나온다.
-- log_path: 행동 로그는 DB 가 아니라 파일이다(T6). Spring 이 이 경로를 읽기 전용으로 마운트해
--   스텝 로그 · 스크린샷 API 로 서빙한다. steps.jsonl 파일 한 줄 당 한 스텝.

CREATE TABLE `run_metrics` (                            -- 회차 종료 시 확정 집계 [P]
  `run_metric_id`  BIGINT        NOT NULL AUTO_INCREMENT,
  `run_id`         BIGINT        NOT NULL,              -- 회차 당 1행
  `success_rate`   DECIMAL(5,2),                        -- 성공 Persona(run_personas.status='done') 비율
  `avg_steps`      DECIMAL(6,2),                        -- 평균 스텝 수
  `avg_backtracks` DECIMAL(6,2),                        -- 평균 뒤로가기
  `avg_seconds`    DECIMAL(8,2),                        -- 평균 소요 시간
  `tokens`         BIGINT,
  `cost_usd`       DECIMAL(10,4),
  `created_at`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`run_metric_id`),
  UNIQUE KEY `uk_run_metrics_run_id` (`run_id`),
  CONSTRAINT `fk_run_metrics_run`
    FOREIGN KEY (`run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `ck_run_metrics_success_rate`  -- 0~100 기준으로 가정
    CHECK (`success_rate` IS NULL OR `success_rate` BETWEEN 0 AND 100),
  CONSTRAINT `ck_run_metrics_non_negative`
    CHECK (
          (`avg_steps`      IS NULL OR `avg_steps`      >= 0)
      AND (`avg_backtracks` IS NULL OR `avg_backtracks` >= 0)
      AND (`avg_seconds`    IS NULL OR `avg_seconds`    >= 0)
      AND (`tokens`         IS NULL OR `tokens`         >= 0)
      AND (`cost_usd`       IS NULL OR `cost_usd`       >= 0)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- 존재 이유: run_personas 를 매번 집계하면 되지 않나 싶지만, Before/After 대시보드가 이
--   테이블의 두 행을 나란히 놓는 것으로 끝나야 한다. 그리고 회차 종료 시점의 확정값을 고정해
--   둬야 나중에 Persona 정의가 바뀌어도 과거 지표가 흔들리지 않는다.

