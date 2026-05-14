import java.io.File

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "kr.yeotaeho.app_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = "kr.yeotaeho.app_mobile"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // dart_defines/local.env → 카카오/네이버 네이티브 SDK용 문자열 (최상위 fun 은 Kotlin DSL에서 compileSdk 적용을 깨뜨릴 수 있어 인라인)
        val envFile = rootProject.projectDir.resolve("../dart_defines/local.env")
        val env: Map<String, String> =
            if (!envFile.isFile) {
                logger.lifecycle(
                    "[app] dart_defines/local.env 없음 → 카카오/네이버 문자열 리소스 비움. " +
                        "dart_defines/example.env 참고 후 local.env 생성.",
                )
                emptyMap()
            } else {
                envFile.readLines()
                    .map { it.trim() }
                    .filter { it.isNotEmpty() && !it.startsWith("#") }
                    .mapNotNull { line ->
                        val eq = line.indexOf('=')
                        if (eq < 1) return@mapNotNull null
                        val key = line.substring(0, eq).trim()
                        var value = line.substring(eq + 1).trim()
                        if (value.length >= 2) {
                            val q = value.first()
                            if ((q == '"' || q == '\'') && value.last() == q) {
                                value = value.substring(1, value.length - 1)
                            }
                        }
                        key to value
                    }
                    .toMap()
            }

        val kakaoNative = env["KAKAO_NATIVE_APP_KEY"].orEmpty()
        val naverId = env["NAVER_CLIENT_ID"].orEmpty()
        val naverSecret = env["NAVER_CLIENT_SECRET"].orEmpty()
        val naverName = env["NAVER_CLIENT_NAME"]?.trim()?.takeIf { it.isNotEmpty() } ?: "청년 인사이트"

        resValue("string", "kakao_native_app_key", kakaoNative)
        resValue("string", "client_id", naverId)
        resValue("string", "client_secret", naverSecret)
        resValue("string", "client_name", naverName)

        // AndroidManifest.xml 의 ${kakaoScheme} 를 카카오 OAuth redirect 스킴으로 치환.
        // 카카오 SDK redirect: kakao{NATIVE_APP_KEY}://oauth
        manifestPlaceholders["kakaoScheme"] = "kakao$kakaoNative"
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}
