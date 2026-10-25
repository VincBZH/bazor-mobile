pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
    versionCatalogs {
        create("libs") {
            from(files("../llama.cpp/examples/llama.android/gradle/libs.versions.toml"))
        }
    }
}
rootProject.name = "BazorChat"
include(":app", ":llama-lib")
project(":llama-lib").projectDir = file("../llama.cpp/examples/llama.android/lib")
