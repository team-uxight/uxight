-- audit_log — 감사 로그 (GACA-126). schema_blueprint.sql 의 정의를 그대로 옮긴다.

CREATE TABLE `audit_log` (                              -- 감사 로그. append-only
  `audit_log_id` BIGINT       NOT NULL AUTO_INCREMENT,
  `actor`        VARCHAR(100) NOT NULL,                 -- user:<id> 또는 agent:<run_id>
  `action`       VARCHAR(50)  NOT NULL,                 -- 행위 종류
  `target`       VARCHAR(200),                          -- 대상
  `detail`       JSON,                                  -- 부가 정보
  `ts`           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`audit_log_id`),
  KEY `ix_audit_log_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- actor 가 FK 가 아닌 이유: 주체가 두 종류다. 사람(운영 행위)과 Agent(차단된 액션).
--   Spring 과 Python 이 각자 행을 추가하고, 기존 행을 고치는 쪽은 없다.
