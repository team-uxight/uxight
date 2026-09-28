-- Walking Skeleton 로컬 전용 테스트 데이터.
-- Flyway 마이그레이션이 아니다. V1 적용 후(Spring 최초 기동 후) 손으로 1회 실행한다.
-- 회원가입 기능이 없어 mock 계정 1행만 넣는다. 나머지는 화면에서 생성한다.

INSERT INTO users (user_id, email, password_hash, auth_provider, google_sub, name, role, is_active)
VALUES (1, 'test@uxight.com', 'mock-not-a-real-hash', 'local', NULL, '재완', 'researcher', true)
ON DUPLICATE KEY UPDATE name = VALUES(name);
