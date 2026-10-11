-- projects · personas 삭제 표시(soft delete) — 프로젝트 삭제 · Persona 삭제 API(GACA-102). schema_blueprint.sql 의 정의를 그대로 옮긴다.

ALTER TABLE `projects`
  ADD COLUMN `deleted_at` DATETIME AFTER `allowed_domains`;   -- 삭제 시각. NULL 이면 사용 중

ALTER TABLE `personas`
  ADD COLUMN `deleted_at` DATETIME AFTER `profile`;           -- 삭제 시각. NULL 이면 사용 중

-- deleted_at: 삭제는 행을 지우지 않고 이 값만 기록한다. tasks · runs · run_personas 가 외래 키로 참조하고,
--   지난 실험의 결과는 남아야 하기 때문이다. 삭제된 행은 FE 응답과 새 실험 요청에서 제외한다.
-- projects: 진행 중인 실험(queued · accepted · running 회차)이 있으면 삭제할 수 없다. 프로젝트 행을 잠근 뒤 확인한다.
-- personas: 진행 중인 실험이 있어도 삭제할 수 있다. 회차는 Persona 스냅샷으로 실행된다 (design-decision 7.1).
