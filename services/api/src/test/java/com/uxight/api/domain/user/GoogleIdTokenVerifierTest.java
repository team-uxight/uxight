package com.uxight.api.domain.user;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.function.UnaryOperator;

import static org.assertj.core.api.Assertions.assertThat;

/** Google 공개키 대신 테스트용 RSA 키로 서명한 ID 토큰을 검증한다. 네트워크를 쓰지 않는다. */
class GoogleIdTokenVerifierTest {

  private static final String CLIENT_ID = "test-client-id.apps.googleusercontent.com";

  private static RSAKey googleKey;
  private static RSAKey otherKey;
  private static GoogleIdTokenVerifier verifier;

  @BeforeAll
  static void setUp() throws JOSEException {
    googleKey = new RSAKeyGenerator(2048).keyID("google-kid").generate();
    otherKey = new RSAKeyGenerator(2048).keyID("google-kid").generate();
    verifier = new GoogleIdTokenVerifier(CLIENT_ID, new ImmutableJWKSet<>(new JWKSet(googleKey.toPublicJWK())));
  }

  @Test
  void validToken_returnsAccount() throws JOSEException {
    assertThat(verifier.verify(sign(googleKey, claims -> claims)))
        .contains(new GoogleAccount("google-sub-1", "user@gmail.com", "홍길동"));
  }

  @Test
  void issuerWithoutScheme_isAccepted() throws JOSEException {
    assertThat(verifier.verify(sign(googleKey, claims -> claims.issuer("accounts.google.com")))).isPresent();
  }

  @Test
  void tokenForAnotherClient_isRejected() throws JOSEException {
    assertThat(verifier.verify(sign(googleKey, claims -> claims.audience("another-client-id")))).isEmpty();
  }

  @Test
  void expiredToken_isRejected() throws JOSEException {
    Date past = Date.from(Instant.now().minus(1, ChronoUnit.HOURS));
    assertThat(verifier.verify(sign(googleKey, claims -> claims.expirationTime(past)))).isEmpty();
  }

  @Test
  void tokenFromAnotherIssuer_isRejected() throws JOSEException {
    assertThat(verifier.verify(sign(googleKey, claims -> claims.issuer("https://evil.example.com")))).isEmpty();
  }

  @Test
  void unverifiedEmail_isRejected() throws JOSEException {
    assertThat(verifier.verify(sign(googleKey, claims -> claims.claim("email_verified", false)))).isEmpty();
  }

  @Test
  void tokenSignedWithAnotherKey_isRejected() throws JOSEException {
    assertThat(verifier.verify(sign(otherKey, claims -> claims))).isEmpty();
  }

  @Test
  void hmacSignedToken_isRejected() throws JOSEException {
    SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), validClaims().build());
    jwt.sign(new MACSigner("hmac-secret-key-must-be-at-least-32-bytes"));

    assertThat(verifier.verify(jwt.serialize())).isEmpty();
    assertThat(verifier.verify("not-a-jwt")).isEmpty();
  }

  @Test
  void blankClientId_rejectsEverything() throws JOSEException {
    GoogleIdTokenVerifier unconfigured =
        new GoogleIdTokenVerifier("", new ImmutableJWKSet<>(new JWKSet(googleKey.toPublicJWK())));

    assertThat(unconfigured.verify(sign(googleKey, claims -> claims))).isEmpty();
  }

  private static String sign(RSAKey key, UnaryOperator<JWTClaimsSet.Builder> customize) throws JOSEException {
    SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.getKeyID()).build(),
        customize.apply(validClaims()).build());
    jwt.sign(new RSASSASigner(key));
    return jwt.serialize();
  }

  // Google ID 토큰의 모양을 따른다
  private static JWTClaimsSet.Builder validClaims() {
    Instant now = Instant.now();
    return new JWTClaimsSet.Builder()
        .issuer("https://accounts.google.com")
        .subject("google-sub-1")
        .audience(CLIENT_ID)
        .issueTime(Date.from(now))
        .expirationTime(Date.from(now.plus(1, ChronoUnit.HOURS)))
        .claim("email", "user@gmail.com")
        .claim("email_verified", true)
        .claim("name", "홍길동");
  }
}
