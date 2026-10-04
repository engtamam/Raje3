import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(keystorePropertiesFile.inputStream())
}

android {
    namespace = "com.raje3.app"
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.raje3.app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // arm64-v8a ONLY — found live (2026-09-28): the direct-download APK jumped from ~69MB to
        // ~180MB the moment flutter_gemma_litertlm was added, and `flutter build apk
        // --target-platform=android-arm64` (scripts/build_apk_direct.sh) turned out to only
        // restrict FLUTTER's own compiled output (libapp.so/libflutter.so) — it does nothing to a
        // third-party AAR's own bundled native libs. flutter_litert (flutter_gemma's own inference
        // runtime dependency) ships prebuilt .so files for all four ABIs, and without this filter
        // Gradle packages every one of them into a single APK regardless of --target-platform.
        // arm64-v8a covers the overwhelming majority of real devices this app is installed on
        // (the exact reasoning build_apk_direct.sh's own header already gives for that flag).
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    // BELT AND SUSPENDERS ON THE SAME FIX — found live (2026-09-28): `ndk.abiFilters` alone did
    // NOT strip anything here, even after a clean build. flutter_litert's own build.gradle.kts
    // contributes its downloaded .so files as a GENERATED jniLibs source directory via the AGP 9
    // Variant API (`androidComponents.onVariants { jniLibs.addGeneratedSourceDirectory(...) }`),
    // copying every ABI folder from upstream unconditionally — `abiFilters` (meant for THIS
    // module's own NDK-compiled output) never gets a say over a source contributed that way.
    // Excluding the unwanted ABI paths at the final packaging step works regardless of which
    // module or mechanism contributed them.
    packaging {
        jniLibs {
            excludes += setOf("lib/armeabi-v7a/**", "lib/x86_64/**", "lib/x86/**")
        }
    }

    signingConfigs {
        if (keystorePropertiesFile.exists()) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (keystorePropertiesFile.exists())
                signingConfigs.getByName("release")
            else
                signingConfigs.getByName("debug")
        }
    }

    // The on-device AI model ships as its own install-time asset pack (../ai_model_pack) instead
    // of a plain app/src/main/assets file — see that module's own build.gradle.kts for why.
    assetPacks += ":ai_model_pack"
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    // Reads android/ai_model_pack's real on-device path at runtime (MainActivity.kt's own
    // MethodChannel bridge) — the official Play Core asset-delivery library, not a third-party
    // wrapper.
    implementation("com.google.android.play:asset-delivery:2.3.0")
    implementation("com.google.android.play:asset-delivery-ktx:2.3.0")
}

flutter {
    source = "../.."
}
