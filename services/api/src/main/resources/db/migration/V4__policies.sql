-- policies — 실행 한도 · 정책값 (GACA-131). schema_blueprint.sql 의 정의를 그대로 옮기고 전역 정책 1행을 넣는다.
-- 전역 정책 한 행을 실험 요청 때 회차의 policy_snapshot 으로 복사한다.

CREATE TABLE `policies` (                               -- 실행 한도 · 정책값
  `policy_id`             BIGINT      NOT NULL AUTO_INCREMENT,
  `max_steps`             INT,                          -- Persona 당 최대 스텝
  `max_seconds`           INT,                          -- Persona 당 최대 시간
  `max_tokens`            INT,                          -- 회차 당 토큰 상한
  `run_concurrency`       INT,                          -- 동시 실험(회차) 수
  `persona_concurrency`   INT,                          -- 하나의 run 안의 동시 Persona 수
  `rate_limit_per_domain` INT,                          -- 도메인당 요청 상한
  `daily_token_budget`    BIGINT,                       -- 일일 토큰 예산
  `model_map`             JSON,                         -- 역할별 모델 · base URL
  `created_at`            DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`policy_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- rate_limit_per_domain: 실험 도메인으로부터 차단당하지 않기 위함.
-- daily_token_budget: 이 값만은 회차 스냅샷에 넣지 않는다. 다른 한도는 회차 자기 몫이지만 이 값은
--   모든 회차가 나눠 쓰는 하나의 한도라, 회차마다 다른 값을 들고 있으면 같은 누적량을 두고 판단이 갈리고
--   관리자가 낮춘 값이 진행 중인 회차에 적용되지 않는다. 매 LLM 호출 직전에 policies 의 현재 값과
--   당일 누적 토큰(runs.tokens 합계)을 함께 읽어 집행한다.

-- 전역 정책. 로컬 · 배포 환경 모두 이 행을 쓴다 — 정책 관리자 API 가 생기기 전까지 값을 바꾸려면 새 마이그레이션으로 UPDATE 한다.
-- 테스트가 빨리 끝나고 비용이 적게 들도록 작은 값으로 시작한다. model_map 은 AI 모듈의 기본값을 쓰도록 비워 둔다.
-- rate_limit_per_domain 의 단위(분당 · 초당)는 미정 — 30 은 분당으로 가정한 값이다 [확인 필요].
INSERT INTO `policies` (`policy_id`, `max_steps`, `max_seconds`, `max_tokens`, `run_concurrency`, `persona_concurrency`,
                        `rate_limit_per_domain`, `daily_token_budget`, `model_map`)
VALUES (1, 10, 120, 20000, 1, 2, 30, 200000, NULL);
