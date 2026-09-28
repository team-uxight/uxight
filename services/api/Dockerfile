# 1단계: 빌드 (wrapper 가 Gradle 을 받는다 — 첫 빌드는 느리다)
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY gradlew build.gradle settings.gradle ./
COPY gradle ./gradle
RUN ./gradlew --no-daemon --version
COPY src ./src
RUN ./gradlew --no-daemon bootJar -x test

# 2단계: 실행
FROM eclipse-temurin:21-jre
# JVM DNS 캐시 끄기 — compose 서비스명(agent)의 IP 가 바뀌거나 사라지면 바로 따라간다.
#   성공 캐시(기본 30초): agent 가 멈춰도 옛 IP 로 붙다가 timeout 이 난다.
#   실패 캐시(java.security 기본 10초): agent 가 다시 떠도 한동안 unreachable 로 남는다.
# 실패 캐시는 java.security 에 명시돼 있어 -D 시스템 프로퍼티로는 못 덮는다 → 파일에 직접 덧붙인다 (뒤 값이 이긴다).
RUN printf 'networkaddress.cache.ttl=0\nnetworkaddress.cache.negative.ttl=0\n' >> "$JAVA_HOME/conf/security/java.security"
WORKDIR /app
COPY --from=build /src/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
