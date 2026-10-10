-- 로컬 전용 테스트 데이터. local 프로필일 때만 Flyway 가 V* 다음에 적용한다 (application-local.yml).
-- 이 파일 내용이 바뀌면 다음 기동 때 다시 적용되므로, 모든 INSERT 는 다시 실행해도 같은 결과가 되게 쓴다.
-- Persona 관리 기능이 없어 테스트 계정 1행과 공용 Persona 1행만 넣는다. 나머지는 API 로 생성한다.

-- 로컬 로그인용 계정. 비밀번호 test1234 의 BCrypt 해시 — 로컬 seed 전용이라 공개해도 되는 값이다.
INSERT INTO users (user_id, email, password_hash, auth_provider, google_sub, name, role, is_active)
VALUES (1, 'test@uxight.com', '$2a$10$SUsLblj3/oiOFeaG8TWjauj2SEJm/P4sAxWVcX5tgf6cRM9c5DrQm', 'local', NULL, '재완', 'researcher', true) AS new
ON DUPLICATE KEY UPDATE name = new.name, password_hash = new.password_hash;

-- user_id NULL = 관리자 소유 공용 Persona. profile 키는 camelCase, 속성 형식은 미확정 (GACA-66).
INSERT INTO personas (persona_id, user_id, name, profile)
VALUES (1, NULL, '재완',
        '{"ageGroup": 20, "webSkill": "low", "device": "desktop", "domainKnowledge": "low", "patience": "medium", "explorationTendency": "low", "behaviorInstruction": ["메뉴 이름이 모호하면 쉽게 헤맨다.", "실패한 경로를 반복하지 않는다."]}') AS new
ON DUPLICATE KEY UPDATE name = new.name, profile = new.profile;
