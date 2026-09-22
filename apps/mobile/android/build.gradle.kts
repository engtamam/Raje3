apply(from = "fix-jcenter.gradle")

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

// Legacy plugin subprojects (e.g. mic_stream) don't declare Java/Kotlin source
// compatibility themselves, so they pick up mismatched defaults (javac on 11,
// Kotlin on 17) under this JDK/AGP/Kotlin combo and fail Gradle's JVM-target
// consistency check. Force every subproject's compile tasks onto JVM 17 so
// javac and kotlinc agree, without touching those plugins' own build files.
subprojects {
    val configureJvmTarget: Project.() -> Unit = {
        extensions.findByType(com.android.build.gradle.BaseExtension::class.java)?.let { android ->
            android.compileOptions.sourceCompatibility = JavaVersion.VERSION_17
            android.compileOptions.targetCompatibility = JavaVersion.VERSION_17
        }
        tasks.withType(org.jetbrains.kotlin.gradle.tasks.KotlinCompile::class.java).configureEach {
            compilerOptions.jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
    // ":app" already declares its own matching JVM 17 compatibility and is forced
    // to evaluate early above via evaluationDependsOn; re-touching its (already
    // finalized) compileOptions here would fail, so only patch the other plugin
    // subprojects (like mic_stream) that leave compatibility unset.
    if (name != "app") {
        if (state.executed) configureJvmTarget() else afterEvaluate { configureJvmTarget() }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
