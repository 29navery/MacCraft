# Architecture

The native execution engine comes from the pinned mcpelauncher source, rather than a new incomplete ELF loader. MacCraft supplies installation, launch policy, and explicit Metal configuration. Dependencies are checked out as git submodules; they are not copied into MacCraft-owned source files.

## Execution boundaries

1. Python reads the user's APK files, validates Android binary manifests and AArch64 ELF headers, and installs assets/libraries without executing them.
2. The launcher validates the macOS host architecture and native runtime binary. It checks installation hashes before execution.
3. In Metal mode, the standalone C++ probe loads the supplied EGL/GLES dylibs and requests an ANGLE Metal display. It tests the requested GLES version and verifies a shader draw through pixel readback.
4. The native mcpelauncher process uses its Android linker and libc shims to load the game's ELF libraries. Fake JNI and Android service implementations connect game calls to host facilities. The Android Java application and a full Android framework are not executed.
5. GLFW handles Cocoa windows and input. Android EGL calls are intercepted by upstream's FakeEGL and routed to the host context. With the MacCraft patches, GLFW selects ANGLE's Metal display and loads the explicit dylib pair. SDL3 handles upstream audio integration.

ARM64 matching removes CPU instruction-set translation. Android versus Darwin binary formats, ABI details, threading, executable memory permissions, and framework behavior still require the native engine's adaptations. New Android/Minecraft dependencies can require additional implementation work.

## MacCraft patches

- `client-metal.patch` adds explicit EGL and GLES paths, selects GLES instead of desktop GL for Metal, and skips upstream's bundled Vulkan path when MacCraft specifies a renderer.
- `window-metal.patch` selects GLFW's Metal platform before initialization, requests the preflight GLES context version, and disables silent fallback to GLES 2 for Metal.

The original sources stay in the GPL upstream submodules. Patches fail closed when the expected source is absent. `scripts/build_runtime.py --prepare-only` applies/checks patches without invoking a macOS compiler and can be run twice to verify idempotence.

## Limits

The probe uses an offscreen pbuffer; Cocoa surface creation and presentation still need testing on a Mac. Native execution does not establish full Android compatibility. Upstream account integrations may depend on separate MSA daemon/webview components; this initial headless build does not package them, so Microsoft sign-in and account-dependent features remain incomplete. There is no Google Play downloader or APK signature verification.

ANGLE Metal may lack features required by a particular game build. This prototype does not implement a MoltenVK backend, replace RenderDragon, or bypass graphics feature requirements. A real current ARM64 Minecraft APK plus physical Apple silicon hardware is needed to assess those gaps.
