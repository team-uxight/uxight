CREATE TABLE IF NOT EXISTS `users` (
  `user_id` BIGINT NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255),
  `auth_provider` VARCHAR(20) NOT NULL,
  `google_sub` VARCHAR(255),
  `name` VARCHAR(100),
  `role` VARCHAR(20) NOT NULL,
  `is_active` BOOLEAN NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uk_users_email` (`email`),
  UNIQUE KEY `uk_users_google_sub` (`google_sub`),
  CONSTRAINT `ck_users_role` CHECK (`role` IN ('admin', 'researcher')),
  CONSTRAINT `ck_users_auth_provider` CHECK (`auth_provider` IN ('local', 'google')),
  CONSTRAINT `ck_users_credential` CHECK (
    (`auth_provider` = 'local' AND `password_hash` IS NOT NULL)
    OR (`auth_provider` = 'google' AND `google_sub` IS NOT NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
