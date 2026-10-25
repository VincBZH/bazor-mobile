# BAZOR CHAT Android

Separate native Android application module for issue #223. It uses the upstream `llama.cpp` Android JNI example, pinned in CI to commit `6050b467c07a95c7b87debd4ddac2f8ba8d9b807`, to perform real, on-device GGUF inference. It does not call BAZOR PC, NoTrack, an API, or any paid service.

## Current implementation status

- Native Android Activity with local chat, two distinct agent instructions, sequential automatic responses, manual mode, STOP, and locally persisted conversation text.
- Offers an explicit download of Qwen2.5 1.5B Q4_K_M (about 986 MB) from Hugging Face, checks server-provided size and SHA-256, reports progress, and allows cancellation. It also imports a GGUF only after the user explicitly chooses a file. Files are stored privately and checked for a GGUF header.
- Uses one loaded model for both logical agents to conserve memory.
- Runs offline after a compatible model has been imported.
- No network, contact, SMS, camera, microphone, or broad media permissions are declared.

This is an initial implementation, not a verified V1.0.0 release. Room-based multiple conversations, image generation/analysis, NoTrack, and device testing remain incomplete. The app intentionally does not claim those functions. The sample model download is optional and explicit; inference is fully local after download. A S21+ has several hardware variants; model speed and memory headroom depend on the exact device and model quantization.

## Build

The upstream source must be present at `android/llama.cpp` because the upstream JNI CMake project builds against its repository root. CI fetches the pinned commit and builds an ARM64 debug APK. Requires JDK 17, Gradle 8.13, Android SDK 36, NDK 29.0.13113456, and CMake 3.31.6.

```sh
git clone https://github.com/ggml-org/llama.cpp.git android/llama.cpp
git -C android/llama.cpp checkout 6050b467c07a95c7b87debd4ddac2f8ba8d9b807
cd android/bazor-chat
gradle :app:testDebugUnitTest :app:assembleDebug
```

The model weights are not bundled. Obtain a compatible GGUF model whose license permits your use, transfer it to the phone, then choose it in the app. The first import can take time and requires free storage approximately equal to the model size. Inference stays on the phone.

The upstream `llama.cpp` project is MIT-licensed. This app builds its JNI library from the pinned upstream checkout rather than copying its native source into this repository.
