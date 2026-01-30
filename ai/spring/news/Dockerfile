# ---- Build Stage ----
FROM gradle:8.5-jdk21 AS build

# 프로젝트 코드 복사
WORKDIR /app
COPY build.gradle settings.gradle ./
COPY src ./src

# Gradle 빌드 실행 (독립 프로젝트)
RUN gradle clean build -x test --no-daemon

# ---- Runtime Stage ----
FROM eclipse-temurin:21-jre

WORKDIR /app

# 빌드된 JAR 파일 복사
COPY --from=build /app/build/libs/*.jar ./app.jar

EXPOSE 8084

ENTRYPOINT ["java", "-jar", "app.jar"]
