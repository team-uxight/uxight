package com.uxight.api.domain.user;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.text.ParseException;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;

/** access 토큰(JWT, HS256). 토큰에는 userId(sub)만 담는다 — 역할 · 활성 여부는 매 요청 DB 에서 확인한다. */
@Slf4j
@Component
public class JwtProvider {

  private static final int MIN_SECRET_BYTES = 32;   // HS256 키는 256비트 이상

  private final MACSigner signer;
  private final MACVerifier verifier;
  private final Duration accessTokenTtl;

  @Autowired
  public JwtProvider(@Value("${uxight.auth.jwt-secret}") String jwtSecret,
      @Value("${uxight.auth.access-token-ttl}") Duration accessTokenTtl) throws JOSEException {
    byte[] secret = secretBytes(jwtSecret);
    this.signer = new MACSigner(secret);
    this.verifier = new MACVerifier(secret);
    this.accessTokenTtl = accessTokenTtl;
  }

  public String createAccessToken(Long userId) {
    Instant now = Instant.now();
    JWTClaimsSet claims = new JWTClaimsSet.Builder()
        .subject(String.valueOf(userId))
        .issueTime(Date.from(now))
        .expirationTime(Date.from(now.plus(accessTokenTtl)))
        .build();
    SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
    try {
      jwt.sign(signer);
    } catch (JOSEException e) {
      throw new IllegalStateException(e);   // 키 길이는 생성자에서 확인했다
    }
    return jwt.serialize();
  }

  /** 서명 · 알고리즘 · 만료가 모두 맞으면 userId. 하나라도 어긋나면 empty. */
  public Optional<Long> parseUserId(String token) {
    try {
      SignedJWT jwt = SignedJWT.parse(token);
      // 헤더의 alg 를 믿지 않는다 — 발급한 HS256 이 아니면 거절
      if (!JWSAlgorithm.HS256.equals(jwt.getHeader().getAlgorithm()) || !jwt.verify(verifier)) {
        return Optional.empty();
      }
      JWTClaimsSet claims = jwt.getJWTClaimsSet();
      Date expiresAt = claims.getExpirationTime();
      if (expiresAt == null || !expiresAt.toInstant().isAfter(Instant.now())) {
        return Optional.empty();
      }
      return Optional.of(Long.valueOf(claims.getSubject()));
    } catch (ParseException | JOSEException | NumberFormatException e) {
      return Optional.empty();
    }
  }

  // JWT_SECRET 이 없으면 기동마다 임의 키를 쓴다 — 로컬 · 테스트용. 재기동하면 발급한 토큰이 모두 무효가 된다.
  private static byte[] secretBytes(String jwtSecret) {
    if (jwtSecret == null || jwtSecret.isBlank()) {
      log.warn("JWT_SECRET is not set. Using a random key; issued access tokens become invalid on restart.");
      byte[] random = new byte[MIN_SECRET_BYTES];
      new SecureRandom().nextBytes(random);
      return random;
    }
    byte[] secret = jwtSecret.getBytes(StandardCharsets.UTF_8);
    if (secret.length < MIN_SECRET_BYTES) {
      throw new IllegalStateException("JWT_SECRET must be at least " + MIN_SECRET_BYTES + " bytes");
    }
    return secret;
  }
}
