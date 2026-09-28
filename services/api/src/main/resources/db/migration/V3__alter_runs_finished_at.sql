-- UXight DDL v3 - MySQL 8
-- runs 테이블 구조 변경
--   V1에서 의도적으로 뺐던 finished_at 컬럼을 추가한다 (Flyway 마이그레이션 검증용).
--   [P] 컬럼: Python이 런 종료(done/failed/cancelled) 시점에 기록한다.

ALTER TABLE `runs`
  ADD COLUMN `finished_at` DATETIME NULL AFTER `started_at`;
