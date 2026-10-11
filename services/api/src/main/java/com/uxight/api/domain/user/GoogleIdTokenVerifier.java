package com.uxight.api.domain.user;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.jwk.source.JWKSourceBuilder;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTClaimsVerifier;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.MalformedURLException;
import java.net.URI;
import java.util.Optional;
import java.util.Set;

/**
 * 프론트엔드가 Google 에서 받은 ID 토큰을 검증한다 — 서명(Google 공개키, RS256) · 발급자 · 발급 대상(우리 client ID) · 만료.
 * Google 공개키(JWKS)는 처음 검증할 때 받아 캐시하고, 키가 바뀌면 다시 받는다.
 */
@Slf4j
@Component
public class GoogleIdTokenVerifier {

  private static final String GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs";
  private static final Set<String> GOOGLE_ISSUERS = Set.of("accounts.google.com", "https://accounts.google.com");

  private final boolean configured;
  private final ConfigurableJWTProcessor<SecurityContext> processor;

  @Autowired
  public GoogleIdTokenVerifier(@Value("${uxight.auth.google-client-id}") String clientId) throws MalformedURLException {
    this(clientId, JWKSourceBuilder.<SecurityContext>create(URI.create(GOOGLE_JWKS_URL).toURL()).retrying(true).build());
  }

  /** 테스트에서 임의 키로 서명한 토큰을 검증할 수 있게 공개키 출처를 받는다. */
  GoogleIdTokenVerifier(String clientId, JWKSource<SecurityContext> googleKeys) {
    // client ID 가 없으면 aud 를 확인할 수 없다 — 다른 앱에 발급된 토큰까지 받지 않도록 모두 거절한다
    this.configured = clientId != null && !clientId.isBlank();
    if (!configured) {
      log.warn("GOOGLE_CLIENT_ID is not set. Google login will always fail.");
    }
    this.processor = new DefaultJWTProcessor<>();
    processor.setJWSKeySelector(new JWSVerificationKeySelector<>(JWSAlgorithm.RS256, googleKeys));
    // aud 가 client ID 와 같아야 하고, 만료(exp)는 기본 허용 오차(60초) 안에서 확인한다
    processor.setJWTClaimsSetVerifier(new DefaultJWTClaimsVerifier<>(
        clientId, null, Set.of("iss", "sub", "aud", "exp", "email")));
  }

  /** 검증에 성공하면 계정 정보, 실패하면 empty. */
  public Optional<GoogleAccount> verify(String idToken) {
    if (!configured) {
      return Optional.empty();
    }
    try {
      JWTClaimsSet claims = processor.process(idToken, null);
      if (!GOOGLE_ISSUERS.contains(claims.getIssuer()) || !isEmailVerified(claims)) {
        return Optional.empty();
      }
      return Optional.of(new GoogleAccount(claims.getSubject(), claims.getStringClaim("email"), claims.getStringClaim("name")));
    } catch (Exception e) {
      // 위조 · 만료 · 형식 오류 · 공개키를 못 받은 경우 모두 인증 실패로 본다
      log.info("Google ID token rejected: {}", e.getMessage());
      return Optional.empty();
    }
  }

  // 확인되지 않은 이메일로는 계정을 만들지 않는다 — 이메일이 계정 식별(uk_users_email)에 쓰이기 때문이다
  private static boolean isEmailVerified(JWTClaimsSet claims) {
    Object emailVerified = claims.getClaim("email_verified");
    return Boolean.TRUE.equals(emailVerified) || "true".equals(emailVerified);
  }
}
