-- refresh_tokens — 이메일 로그인(GACA-100). schema_blueprint.sql 의 정의를 그대로 옮긴다.

CREATE TABLE `refresh_tokens` (                         -- 발급된 refresh 토큰
  `refresh_token_id` BIGINT     NOT NULL AUTO_INCREMENT,
  `user_id`          BIGINT    NOT NULL,                -- 토큰 소유 계정
  `token_hash`       CHAR(64)  NOT NULL,                -- 토큰 원문의 SHA-256 해시
  `expires_at`       DATETIME  NOT NULL,                -- 만료 시각
  `revoked_at`       DATETIME,                          -- 무효화 시각. NULL 이면 유효
  `created_at`       DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`refresh_token_id`),
  UNIQUE KEY `uk_refresh_tokens_token_hash` (`token_hash`),
  KEY `ix_refresh_tokens_user_id` (`user_id`),
  CONSTRAINT `fk_refresh_tokens_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- token_hash: 원문은 저장하지 않는다. DB가 유출돼도 해시로는 재발급을 요청할 수 없다.
--   원문은 JWT가 아닌 무작위 문자열로 만들어 HttpOnly 쿠키로만 전달한다. 어차피 DB에서
--   확인하므로 토큰 안에 정보를 담을 이유가 없다.
-- 한 계정에 여러 행이 생길 수 있다. 브라우저나 기기마다 로그인이 따로 유지되기 때문이다.
-- 로그아웃: 해당 행의 revoked_at 을 기록한다. 만료되었거나 무효화된 행은 주기적으로 삭제한다.
