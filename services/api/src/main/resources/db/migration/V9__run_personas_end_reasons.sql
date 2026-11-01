-- run_personas.status 에 종료 이유 token_limit · stuck 추가 (GACA-218). 기존 행은 그대로라 데이터 변경은 없다.

ALTER TABLE `run_personas` DROP CHECK `ck_run_personas_status`;

ALTER TABLE `run_personas`
  ADD CONSTRAINT `ck_run_personas_status`
    CHECK (`status` IN ('running', 'done', 'max_steps', 'token_limit', 'stuck', 'fail', 'timeout', 'cancelled'));

-- 쓰는 쪽은 AI 모듈(Python)이다.
-- max_steps: step 상한까지 돌았다.
-- token_limit: 토큰 상한으로 끝났다. 토큰 상한(회차 당, policy_snapshot.max_tokens)과 하루 토큰 예산
--   (policies.daily_token_budget) 둘 다 이 값이다. 어느 쪽인지는 감사 로그 agent.limit_reached 의
--   detail.reason(max_tokens · daily_token_budget)에 있다. 전에는 max_steps 로 적었다.
-- stuck: 같은 화면의 관측이 3번 이어져 끝냈다. 같은 화면은 요소 줄(step 로그의 observation.elements_hash)과
--   지금 화면 안의 본문 글이 둘 다 같은 것이다. 본문 글은 step 로그에 없다.
