-- UXight DDL v1 - MySQL 8
-- Walking Skeleton 흐름에 필요한 테이블 7개만 포함 (ERD v0.3 기준).
-- 제외: 나머지 테이블 7개, fk_runs_improvement 제약조건, runs.finished_at 컬럼

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

CREATE TABLE `projects` (                               -- 대상 사이트 단위. 실행보다 한 층 위
  `project_id`      BIGINT        NOT NULL AUTO_INCREMENT,
  `user_id`         BIGINT        NOT NULL,             -- 소유 리서처
  `name`            VARCHAR(100)  NOT NULL,             -- 표시 이름
  `target_url`      VARCHAR(2048) NOT NULL,             -- 시작 URL
  `allowed_domains` JSON          NOT NULL,             -- 가드 허용 도메인 목록
  `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`project_id`),
  KEY `ix_projects_user_id` (`user_id`),
  CONSTRAINT `fk_projects_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tasks` (                                  -- 과업 정의
  `task_id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `project_id`       BIGINT       NOT NULL,
  `goal`             VARCHAR(200) NOT NULL,             -- 사람이 읽는 목표 문장
  `success_criteria` JSON         NOT NULL,             -- 성공 기준
  `is_one_shot`      BOOLEAN      NOT NULL,             -- 1회성 Task 제외 플래그
  `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`task_id`),
  KEY `ix_tasks_project_id` (`project_id`),
  CONSTRAINT `fk_tasks_project`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `personas` (                               -- 가상 사용자 정의
  `persona_id` BIGINT       NOT NULL AUTO_INCREMENT,
  `project_id` BIGINT       NOT NULL,
  `name`       VARCHAR(100) NOT NULL,                   -- 표시 이름
  `profile`    JSON         NOT NULL,                   -- 속성 묶음
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`persona_id`),
  KEY `ix_personas_project_id` (`project_id`),
  CONSTRAINT `fk_personas_project`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ───────── 실행 계층 ─────────

CREATE TABLE `runs` (                                   -- 실험 1회 = Persona N명 전체
  `run_id`              BIGINT        NOT NULL AUTO_INCREMENT,
  `project_id`          BIGINT        NOT NULL,         -- [S]
  `task_id`             BIGINT        NOT NULL,         -- [S]
  `mode`                VARCHAR(20)   NOT NULL,         -- [S] diagnose / improve / loop
  `loop_max`            INT,                            -- [S] 루프 최대 회차
  `parent_run_id`       BIGINT,                         -- [S] 재실험 원본
  `improvement_id`      BIGINT,                         -- [S] 검증 대상 개선안
  `target_url_snapshot` VARCHAR(2048) NOT NULL,         -- [S] 시작 시점 URL 사본   ← 확인 필요
  `task_snapshot`       JSON          NOT NULL,         -- [S] 시작 시점 Task 사본  ← 확인 필요
  `policy_snapshot`     JSON          NOT NULL,         -- [S] 시작 시점 정책 사본
  `persona_snapshot`    JSON          NOT NULL,         -- [S] 시작 시점 Persona 사본
  `dispatch_state`      VARCHAR(20),                    -- [S] sent / unreachable / timeout
  `cancel_requested`    BOOLEAN       NOT NULL DEFAULT false,         -- [S] kill switch
  `status`              VARCHAR(20)   NOT NULL,         -- [P] queued/accepted/running/done/failed/cancelled
  `progress`            INT,                            -- [P] 완료 Persona 수
  `heartbeat_at`        DATETIME,                       -- [P] 살아 있음 신호
  `next_loop_requested` BOOLEAN       NOT NULL DEFAULT false,         -- [P] 다음 회차 요청 플래그
  `error`               TEXT,                           -- [P] 실패 사유
  `tokens`              BIGINT,                         -- [P] 누적 토큰
  `cost_usd`            DECIMAL(10,4),                  -- [P] 누적 비용
  `accepted_at`         DATETIME,                       -- [P]
  `started_at`          DATETIME,                       -- [P]
  `created_at`          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- [S]
  PRIMARY KEY (`run_id`),
  KEY `ix_runs_status` (`status`),
  KEY `ix_runs_project_created` (`project_id`, `created_at`),
  KEY `ix_runs_task_id` (`task_id`),
  KEY `ix_runs_parent_run_id` (`parent_run_id`),
  KEY `ix_runs_improvement_id` (`improvement_id`),
  CONSTRAINT `fk_runs_project`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`),
  CONSTRAINT `fk_runs_task`
    FOREIGN KEY (`task_id`) REFERENCES `tasks` (`task_id`),
  CONSTRAINT `fk_runs_parent_run`
    FOREIGN KEY (`parent_run_id`) REFERENCES `runs` (`run_id`),
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `run_personas` (                           -- Persona 한 명의 실행 결과 [P]
  `run_persona_id` BIGINT        NOT NULL AUTO_INCREMENT,
  `run_id`         BIGINT        NOT NULL,
  `persona_id`     BIGINT        NOT NULL,              -- 정의 참조
  `status`         VARCHAR(20)   NOT NULL,              -- running / completed(정상 종료: done 또는 max_steps 소진 등) / fail / timeout / cancelled
  `agent_done`     BOOLEAN,                   			-- 메인 판정 — Agent 가 done 을 냈나
  `rule_success`   BOOLEAN,               			    -- 보조 판정 — success_rule 일치 여부
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
    CHECK (`status` IN ('running', 'completed', 'fail', 'timeout', 'cancelled')),
  CONSTRAINT `ck_run_personas_non_negative`
    CHECK (
          (`steps`      IS NULL OR `steps`      >= 0)
      AND (`backtracks` IS NULL OR `backtracks` >= 0)
      AND (`tokens`     IS NULL OR `tokens`     >= 0)
      AND (`cost_usd`   IS NULL OR `cost_usd`   >= 0)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `run_metrics` (                            -- run 종료 시 확정 집계 [P]
  `run_metric_id`  BIGINT        NOT NULL AUTO_INCREMENT,
  `run_id`         BIGINT        NOT NULL,              -- run 당 1행
  `success_rate`   DECIMAL(5,2),                        -- 성공 Persona 비율
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
