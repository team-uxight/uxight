-- 로컬 전용 테스트 데이터. local 프로필일 때만 Flyway 가 V* 다음에 적용한다 (application-local.yml).
-- 이 파일 내용이 바뀌면 다음 기동 때 다시 적용되므로, 모든 INSERT 는 다시 실행해도 같은 결과가 되게 쓴다.
-- 테스트 계정 1행만 넣는다. 프로젝트 · Persona 는 API 로 생성한다. 전역 정책은 모든 환경에 필요해 V4 마이그레이션이 넣는다.
-- 공용 Persona seed 는 profile 스키마가 정해지면(GACA-66) 다시 넣는다. 그 전에 seed 를 받은 로컬 DB 에는
-- persona_id 1 이 남아 있다 — 이 파일은 행을 지우지 않으므로 필요하면 `docker compose down -v` 로 초기화한다.

-- 로컬 로그인용 계정. 비밀번호 test1234 의 BCrypt 해시 — 로컬 seed 전용이라 공개해도 되는 값이다.
INSERT INTO users (user_id, email, password_hash, auth_provider, google_sub, name, role, is_active)
VALUES (1, 'test@uxight.com', '$2a$10$SUsLblj3/oiOFeaG8TWjauj2SEJm/P4sAxWVcX5tgf6cRM9c5DrQm', 'local', NULL, '재완', 'researcher', true) AS new
ON DUPLICATE KEY UPDATE name = new.name, password_hash = new.password_hash;
