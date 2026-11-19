-- test_accounts — 테스트 계정 풀 (GACA-196). schema_blueprint.sql 의 정의를 그대로 옮긴다.
-- 표만 먼저 만든다. 등록 · 조회 · 삭제 API 와 실험 요청 때의 수 확인 · 배정은 GACA-133 에서 넣는다
-- (RunService · ImprovementService 의 TODO). 그 전까지 Spring 은 이 표를 읽지도 쓰지도 않는다.

CREATE TABLE `test_accounts` (                          -- 테스트 계정 풀
  `test_account_id` BIGINT         NOT NULL AUTO_INCREMENT,
  `project_id`      BIGINT         NOT NULL,
  `login_id`        VARCHAR(255)   NOT NULL,            -- 테스트 계정 아이디. 목록 표시와 중복 검사를 위해 평문 저장
  `secret_enc`      VARBINARY(512) NOT NULL,            -- 암호화 저장된 비밀번호
  `assigned_run_id` BIGINT,                             -- 마지막으로 배정된 회차. NULL이면 아직 배정된 적 없음
  `created_at`      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`test_account_id`),
  KEY `ix_test_accounts_assigned_run_id` (`assigned_run_id`),
  UNIQUE KEY `uk_test_accounts_project_login` (`project_id`, `login_id`),
  CONSTRAINT `fk_test_accounts_project`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`project_id`),
  CONSTRAINT `fk_test_accounts_run`
    FOREIGN KEY (`assigned_run_id`) REFERENCES `runs` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- secret_enc: 복호화는 Spring 만 한다. AI 모듈이 GET /internal/runs/{runId}/credentials 를 호출하면,
--   회차 status 가 accepted 이고 취소 요청이 없을 때 횟수 제한 없이 제공한다. 재시작한 AI 모듈이
--   accepted 회차를 다시 가져가면 다시 받아야 하기 때문이다. 평문은 DB, LLM 프롬프트, 로그, 스크린샷
--   어디에도 남기지 않고, 로그인은 스크립트가 수행한다(D18).
-- assigned_run_id: Persona 당 계정 1개를 점유해 상태 오염을 막는다. 같은 계정을 두 Persona 가
--   동시에 쓰면 한쪽의 행동이 다른 쪽 화면을 바꾼다.
--   배정 해제는 하지 않는다. 프로젝트당 진행 중인 실험은 하나뿐이라 새 회차를 배정할 때는 그 프로젝트의
--   모든 계정이 비어 있으므로, Spring이 배정할 때마다 새 회차의 run_id 로 덮어쓴다.
