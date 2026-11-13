-- users.last_login_at — 계정 목록의 마지막 로그인 (GACA-207). 기존 행은 NULL(로그인 기록 없음)로 시작한다.

ALTER TABLE `users`
  ADD COLUMN `last_login_at` DATETIME NULL AFTER `is_active`;

-- 쓰는 쪽은 Spring 이다. 이메일 · Google 로그인이 성공해 토큰을 발급할 때 갱신한다.
-- access 토큰 재발급(refresh)은 로그인으로 치지 않는다 — 로그인 상태를 이어 가는 것일 뿐이다.
