-- findings — 진단(검출된 Friction 1건) (GACA-190). schema_blueprint.sql 의 정의를 그대로 옮긴다.
-- improvements · fk_runs_improvement 는 개선안 기능을 구현할 때 추가한다.

CREATE TABLE `findings` (                               -- 검출된 Friction 1건 [P]
  `finding_id` BIGINT      NOT NULL AUTO_INCREMENT,
  `run_id`     BIGINT      NOT NULL,
  `taxonomy`   VARCHAR(30) NOT NULL,                    -- Friction 유형
  `severity`   VARCHAR(10) NOT NULL,                    -- 심각도
  `evidence`   JSON        NOT NULL,                    -- 근거
  `summary`    TEXT,                                    -- 진단 단계에서 채우는 요약
  `created_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`finding_id`),
  KEY `ix_findings_run_id` (`run_id`),
  CONSTRAINT `fk_findings_run`
    FOREIGN KEY (`run_id`) REFERENCES `runs` (`run_id`),
  CONSTRAINT `ck_findings_taxonomy`         -- 4종 우선 (D11'). 코드값은 가칭
    CHECK (`taxonomy` IN ('navigation_confusion', 'interaction_failure',
                          'task_failure', 'excessive_steps'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- 쓰는 쪽은 AI 모듈(Python), Spring 은 읽기만 한다.
-- taxonomy: 전체 7종 중 4종 우선 구현 (D11') —
--   Navigation Confusion · Interaction Failure · Task Failure · Excessive Steps.
-- evidence: 어느 Persona 의 몇 번째 스텝 구간에서, 어느 URL 에서 나왔는지. 실제 로그 원문은
--   파일에 있으므로 여긴 위치만 담는다. 키는 snake_case 배열로 쓴다 (내부 API · 행동 로그와 같은 규칙):
--   [{"persona_id": 3, "step_from": 4, "step_to": 7, "url": "https://..."}]
--   step 번호는 steps.jsonl · step-<n>.png 와 같은 번호다. Spring 이 camelCase 로 바꿔 응답한다.
-- severity: 산정 기준 미확정 (GACA-68).
-- summary 가 별도인 이유: 3단계(검출)가 행을 만들고 4단계(진단)가 이 컬럼을 채운다.
--   한 테이블에 두 단계가 순서대로 쓴다.
