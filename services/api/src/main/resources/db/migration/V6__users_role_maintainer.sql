-- users.role 에 maintainer 추가. 기존 행은 admin · researcher 그대로라 데이터 변경은 없다.

ALTER TABLE `users` DROP CHECK `ck_users_role`;

ALTER TABLE `users`
  ADD CONSTRAINT `ck_users_role`
    CHECK (`role` IN ('admin', 'maintainer', 'researcher'));

-- admin(최고 관리자): 관리자 화면 접근. maintainer 부여를 포함해 모든 역할을 관리한다.
-- maintainer: 관리자 화면 접근. researcher 계정만 관리하고, maintainer · admin 은 부여하지 못한다.
-- researcher: 관리자 화면에 접근하지 못한다. 가입 계정은 모두 researcher 로 시작한다.
