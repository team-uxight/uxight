-- 로컬 전용 관리자 계정. local 프로필일 때만 Flyway 가 적용한다 (application-local.yml).
-- 가입은 모두 리서처로 시작하므로(design-decision 6.1) 관리자 화면 · /api/admin/** 을 로컬에서 확인하려면 seed 가 필요하다.
-- 이메일(uk_users_email)로 upsert 한다 — 다시 적용하면 역할 · 활성 여부 · 비밀번호가 아래 값으로 돌아온다.
-- 비밀번호 admin1234 의 BCrypt 해시 — 로컬 seed 전용이라 공개해도 되는 값이다.
INSERT INTO users (email, password_hash, auth_provider, google_sub, name, role, is_active)
VALUES ('admin@uxight.com', '$2a$10$X60cHevwrt1KU3YTlDCwoewR/knOpRHvEk7rRqMHhJzFQBa2MD2Z6', 'local', NULL, '관리자', 'admin', true) AS new
ON DUPLICATE KEY UPDATE password_hash = new.password_hash, name = new.name, role = new.role, is_active = new.is_active;
