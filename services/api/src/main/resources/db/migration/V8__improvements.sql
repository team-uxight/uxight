-- improvements · approvals · patch_versions — 개선안과 다음 회차 승인 (GACA-192). schema_blueprint.sql 의 정의를 그대로 옮긴다.

CREATE TABLE `improvements` (                           -- 개선안. 회차 당 최대 3안 [P]
  `improvement_id`  BIGINT      NOT NULL AUTO_INCREMENT,
  `run_id`          BIGINT      NOT NULL,               -- 개선안을 산출한 회차
  `finding_ids`     JSON        NOT NULL,               -- 이 개선안이 다루는 진단 목록
  `option_no`       INT         NOT NULL,               -- 1~3안
  `patch_kind`      VARCHAR(20) NOT NULL,               -- 패치 4종
  `patch`           JSON        NOT NULL,               -- 종류별 파라미터
  `rationale`       TEXT,                               -- 근거
  `expected_effect` TEXT,                               -- 예상 영향
  `fix_cost`        VARCHAR(20),                        -- 구현 비용 추정
  `created_at`      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`improvement_id`),
  UNIQUE KEY `uk_improvements_run_option` (`run_id`, `option_no`),
  CONSTRAINT `fk_improvements_run`
    FOREIGN KEY (`run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `ck_improvements_option_no`
    CHECK (`option_no` BETWEEN 1 AND 3),
  CONSTRAINT `ck_improvements_patch_kind`   -- 패치 4종 (D7). 코드값은 가칭
    CHECK (`patch_kind` IN ('relabel', 'move', 'highlight', 'help_text'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- 쓰는 쪽은 AI 모듈(Python). 회차를 done 으로 기록하기 전에 저장한다 — 그 뒤 회차가 실패 · 취소되어도 남는다.
-- finding_ids: 이 개선안이 다루는 진단의 finding_id 배열(예: [3, 5]). JSON 이라 외래 키가 없다 —
--   Spring 은 개선안과 같은 회차의 진단만 읽는다.
-- patch_kind: 라벨 변경 · 요소 이동 · 요소 강조 · 도움말 삽입 네 가지뿐이다 (D7). 자유 형식
--   DOM 조각을 저장하지 않는 것이 핵심이다 — 종류를 네 개로 묶어 둬야 Patcher 가 검증된
--   주입 로직으로 분기할 수 있고, 안 되는 패치가 애초에 생성되지 않는다.
-- patch: 종류별로 필요한 값이 다르다. 예를 들어 라벨 변경이면 대상 요소와 새 문구. 키는 snake_case.
-- 승인 상태가 여기 없는 이유: 이 테이블은 Python 소유인데 승인은 사람이 하는 행위라 Spring 이
--   쓴다. 같은 행을 두 프로세스가 쓰지 않도록 approvals 로 분리했다.

CREATE TABLE `approvals` (                              -- 다음 회차 진행 승인 / 반려 [S]
  `approval_id`    BIGINT      NOT NULL AUTO_INCREMENT,
  `improvement_id` BIGINT      NOT NULL,
  `user_id`        BIGINT      NOT NULL,                -- 결정한 사람
  `decision`       VARCHAR(20) NOT NULL,                -- approve / reject
  `note`           TEXT,                                -- 결정 사유
  `decided_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`approval_id`),
  UNIQUE KEY `uk_approvals_improvement_id` (`improvement_id`),
  KEY `ix_approvals_user_id` (`user_id`),
  CONSTRAINT `fk_approvals_improvement`
    FOREIGN KEY (`improvement_id`) REFERENCES `improvements` (`improvement_id`),
  CONSTRAINT `fk_approvals_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`),
  CONSTRAINT `ck_approvals_decision`
    CHECK (`decision` IN ('approve', 'reject'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- improvement_id 가 UNIQUE 인 이유: 개선안 하나에 대한 결정은 한 번뿐이다. 반려된 개선안은 다시
--   승인할 수 없고, 승인하면 다음 회차가 시작되므로 그 회차의 개선안은 더 이상 결정할 수 없다(API 409).
--   승인 가능 조건은 프로젝트 행 잠금 안에서 검사하고, 이 UNIQUE 는 같은 개선안의 중복 결정을 DB 에서 한 번 더 막는다.

CREATE TABLE `patch_versions` (                         -- 실제로 주입된 패치 [P]
  `patch_version_id` BIGINT      NOT NULL AUTO_INCREMENT,
  `run_id`           BIGINT      NOT NULL,
  `improvement_id`   BIGINT      NOT NULL,
  `patch_kind`       VARCHAR(20) NOT NULL,
  `patch`            JSON        NOT NULL,              -- 주입 시점 사본
  `applied`          BOOLEAN     NOT NULL,              -- 주입 성공 여부
  `fail_reason`      TEXT,                              -- 실패 사유
  `created_at`       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`patch_version_id`),
  KEY `ix_patch_versions_run_id` (`run_id`),
  KEY `ix_patch_versions_improvement_id` (`improvement_id`),
  CONSTRAINT `fk_patch_versions_run`
    FOREIGN KEY (`run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `fk_patch_versions_improvement`
    FOREIGN KEY (`improvement_id`) REFERENCES `improvements` (`improvement_id`),
  CONSTRAINT `ck_patch_versions_patch_kind` -- improvements 와 같은 목록 유지
    CHECK (`patch_kind` IN ('relabel', 'move', 'highlight', 'help_text'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- improvements 와 따로 있는 이유: 개선안은 '제안' 이고 이건 '실제 적용 결과' 이다. 주입은
--   실패할 수 있고(DOM 구조가 바뀌었다든가) 그 실패가 Before/After 해석에 필요하다.
--   같은 개선안이 여러 회차에 적용될 수 있으므로 회차별 기록이 남아야 한다.
--   AI 모듈은 다음 회차를 실행할 때 이전 회차들의 패치까지 누적해 주입하고, 실제 주입 결과를 회차별로 여기에 기록한다.

-- runs.improvement_id(다음 회차에 적용한 개선안)의 외래 키. V1 에서는 improvements 가 없어 미뤘다.
-- runs → improvements → findings → runs 가 닫힌 고리라 마지막에 ALTER 로 단다. 실제 데이터 사이클은 아니다.
ALTER TABLE `runs`
  ADD CONSTRAINT `fk_runs_improvement`
  FOREIGN KEY (`improvement_id`) REFERENCES `improvements` (`improvement_id`);
