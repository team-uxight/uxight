-- UXight DDL v2 - MySQL 8
-- projects 테이블 구조 변경
--   1) name -> title 컬럼명 변경
--   2) description 컬럼 추가 (선택 입력)

ALTER TABLE `projects`
  RENAME COLUMN `name` TO `title`;

ALTER TABLE `projects`
  ADD COLUMN `description` TEXT NULL AFTER `target_url`;   -- 프로젝트 설명. 미입력 허용
