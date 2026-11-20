-- GACA-196 제출용 사본 정리 — export-submission.sh 가 임시 스키마(uxight_submit)에서만 실행한다. dev DB 원본에는 돌리지 않는다.
-- 지우는 것: 비밀번호 해시 · refresh 토큰 해시 · 테스트 계정 암호문 · Google 계정 식별자,
--           그리고 샘플이 아닌(실제 팀원) 계정의 이메일 · 이름 — 계정 표와 감사 로그(user.create) 양쪽.
-- 행은 지우지 않는다(표마다 건수 · 외래 키가 그대로 남아야 한다). 값만 의미 없는 값으로 바꾼다.
-- updated_at = updated_at 은 ON UPDATE CURRENT_TIMESTAMP 로 시각이 바뀌지 않게 한다.

SET NAMES utf8mb4;
SET @sample_domain = 'sample.uxight.example';

START TRANSACTION;

-- 비밀번호 해시 — ck_users_credential 때문에 local 계정은 NULL 로 둘 수 없어 고정 문자열로 바꾼다
UPDATE users SET password_hash = '[removed]', updated_at = updated_at WHERE password_hash IS NOT NULL;

-- Google 계정 식별자 — uk_users_google_sub 를 지키려고 user_id 를 붙인다
UPDATE users SET google_sub = CONCAT('removed-', user_id), updated_at = updated_at WHERE google_sub IS NOT NULL;

-- 실제 계정의 이메일 · 이름. 감사 로그를 먼저 바꾼다(계정 표의 이메일로 실제 계정인지 가리기 때문)
UPDATE audit_log a
  JOIN users u ON a.target = CONCAT('user:', u.user_id)
   SET a.detail = JSON_SET(a.detail, '$.email', CONCAT('user', u.user_id, '@example.com'),
                                     '$.name', CONCAT('사용자', u.user_id))
 WHERE a.action = 'user.create'
   AND u.email NOT LIKE CONCAT('%@', @sample_domain);

UPDATE users
   SET email = CONCAT('user', user_id, '@example.com'), name = CONCAT('사용자', user_id), updated_at = updated_at
 WHERE email NOT LIKE CONCAT('%@', @sample_domain);

-- refresh 토큰 해시 — uk_refresh_tokens_token_hash 를 지키려고 id 로 만든 의미 없는 해시를 넣는다
UPDATE refresh_tokens SET token_hash = SHA2(CONCAT('removed-', refresh_token_id), 256);

-- 테스트 계정 암호문
UPDATE test_accounts SET secret_enc = x'';

COMMIT;
