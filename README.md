# MacCraft

Experimental native ARM64 compatibility runtime for the **Android / Google Play version of Minecraft Bedrock on macOS**.

MacCraft builds on the open-source [Minecraft Bedrock Launcher runtime](https://github.com/minecraft-linux/mcpelauncher-manifest), pinned to a specific commit. Its Android ELF loader, Bionic compatibility shims, and fake JNI implementation execute the Android game's ARM64 code in a macOS process. No Android VM, Windows VM, or Rosetta is involved.

**Status: developer prototype, not a verified playable release.** Package handling and the graphics probe are tested independently. No Minecraft APK is included, and gameplay, Microsoft login, Realms, Marketplace, current Minecraft versions, and MacBook Neo hardware have not been verified. There is no graphical launcher yet.

## Implemented

- Transactional import of a purchased ARM64 Minecraft APK or a base APK plus matching native/assets splits.
- Android binary XML manifest parsing, package/version validation, ELF64 AArch64 inspection, dependency reporting, and file-integrity verification.
- Native ARM64 runtime build with pinned upstream source and reviewable MacCraft patches.
- An experimental ANGLE **Metal** graphics path, using a supplied ARM64 EGL/GLES driver pair.
- A native graphics probe that creates a Metal-backed GLES context, compiles shaders, draws a triangle, and checks pixel readback before game launch.
- Separate installations, world/cache directories, launch logs, and a lock to prevent concurrent access to the same worlds.
- GitHub Actions builds on an ARM64 macOS runner and publishes a developer artifact when the build passes.

## Build on an Apple silicon Mac

Install Xcode Command Line Tools and [Homebrew](https://brew.sh), then:

```sh
xcode-select --install
brew install python cmake ninja openssl@3
git clone --recurse-submodules https://github.com/29navery/MacCraft.git
cd MacCraft
cmake -S . -B build/native -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_OSX_ARCHITECTURES=arm64
cmake --build build/native
ctest --test-dir build/native --output-on-failure
python3 scripts/build_runtime.py
python3 -m maccraft doctor
```

The build patches two upstream submodules in your local checkout. Patches are idempotent and refuse to apply to unexpected source. A modified submodule status after building is expected. The upstream source revision is `91220f0f7ccfd460090d14056ab1bf12e82869b1`.

## Import and launch

Supply your own purchased Google Play Minecraft files. A Windows or iOS purchase is not an Android APK. MacCraft does not download Minecraft, obtain Google credentials, verify APK publisher signatures, or implement store purchasing.

```sh
# A complete ARM64 APK:
python3 -m maccraft import /path/to/minecraft.apk

# Or a base APK and its matching splits:
python3 -m maccraft import /path/to/base.apk /path/to/split_config.arm64_v8a.apk /path/to/assets.apk

python3 -m maccraft list
python3 -m maccraft verify INSTALLATION_ID
python3 -m maccraft launch INSTALLATION_ID --dry-run
python3 -m maccraft launch INSTALLATION_ID
```

Replace `INSTALLATION_ID` with the ID printed by import/list. Run commands from the repository root. Python only manages installation and starts the native C++ executable; it does not emulate the game. `.apks`/`.xapk` outer containers are not supported: extract their component APKs first.

The default `legacy` renderer uses upstream's desktop OpenGL compatibility path. It is intended as a baseline for older game versions. The upstream README lists experimental ARM64 macOS support for **1.19.70–1.21.73**; importing another version is not evidence that it will run. MacCraft explicitly disables upstream's automatic bundled MoltenVK selection when launching in legacy mode.

### Experimental Metal renderer

Provide ARM64 `libEGL.dylib` and `libGLESv2.dylib` from the same [ANGLE](https://github.com/google/angle) build, with its Metal backend enabled. ANGLE and its dependencies are not bundled or built by this prototype. See [ANGLE's build documentation](https://github.com/google/angle/blob/main/doc/DevSetup.md).

```sh
build/native/maccraft-graphics-probe /path/to/angle/libs 3.0
python3 -m maccraft launch INSTALLATION_ID --renderer metal --angle /path/to/angle/libs

# Explicitly require GLES 3.1 where the target game needs it:
python3 -m maccraft launch INSTALLATION_ID --renderer metal --angle /path/to/angle/libs --gles 3.1
```

A Metal backend does **not** imply GLES 3.1 support. The probe fails if the requested context or actual shader rendering is unavailable. Passing the probe checks a small graphics workload; it does not verify Minecraft shaders, Vibrant Visuals, or overall game compatibility. No silent fallback to GLES 2 or a different renderer occurs in Metal mode.

## Data and logs

Default storage is `~/Library/Application Support/MacCraft/`:

| Directory | Contents |
| --- | --- |
| `versions/` | Imported libraries, assets, base manifest, and source/file hashes |
| `data/games/com.mojang/` | Worlds and Minecraft settings |
| `cache/` | Runtime cache |
| `logs/` | Timestamped stdout/stderr from game launches |

Different game versions share `data/` under a given root. Use a separate root for testing versions or valuable worlds:

```sh
python3 -m maccraft --root "$HOME/Library/Application Support/MacCraft-Test" import /path/to/minecraft.apk
python3 -m maccraft --root "$HOME/Library/Application Support/MacCraft-Test" launch INSTALLATION_ID
```

Make a copy of any existing worlds before testing them. MacCraft does not import or modify another launcher's world directory.

## Validation and next milestones

The test suite uses synthetic packages; it checks ARM64/package validation, binary manifests, split merging, failed-import cleanup, hostile archive paths, tampering, and launch arguments. CI verifies compilation and runtime `--version`. It does not run Minecraft or test Metal on a physical GPU.

See [architecture](docs/architecture.md) for the runtime boundary and [testing](docs/testing.md) for the next gameplay acceptance checks.

## License and attribution

MacCraft is GPL-3.0-only. The pinned runtime and its dependencies retain their respective licenses. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Minecraft remains proprietary and is not distributed in this repository. MacCraft is unofficial and is not affiliated with Mojang or Microsoft.
