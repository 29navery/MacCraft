# MacCraft

A graphical Minecraft Bedrock launcher for Apple silicon Macs, using your purchased **Google Play / Android** copy of the game and a native ARM64 compatibility runtime.

## Open the app

1. Open the latest successful [GitHub Actions build](https://github.com/29navery/MacCraft/actions).
2. Download the **MacCraft-macOS-arm64** artifact and extract its ZIP.
3. Open **MacCraft-arm64.dmg**, then drag **MacCraft.app** into **Applications**.
4. Open MacCraft and select **Sign in with Google**. Use the Google account that owns Minecraft for Android.
5. Choose **Download and play**. The launcher checks your Google Play purchase, downloads the ARM64 package and its splits, extracts them, and starts the bundled native runtime. Later launches use **Play**, downloading updates when needed by the selected profile.

**No Terminal, Python, Homebrew, or manual APK import is required to use the packaged app.** A Windows or iOS purchase does not provide a Google Play purchase.

The developer app is ad-hoc signed, not notarized. If macOS blocks it, use **System Settings → Privacy & Security → Open Anyway** after attempting to open it. Do not disable Gatekeeper globally.

## What is implemented

- A Mac app bundle with a MacCraft welcome screen and embedded Google sign-in window.
- The pinned upstream launcher’s real Google Play authentication, purchase verification, delivery, split-package download, installation, version profiles, and Play workflow.
- ARM64-only store requests, avoiding incompatible x86/32-bit packages.
- Account encryption keys in **macOS Keychain**, with a private browser session for Google sign-in and rejected certificate errors.
- The patched native Bedrock runtime, its libraries, Qt, the embedded browser, and third-party dylibs bundled into the app.
- A built-in game log and separate MacCraft settings, profiles, downloads, and worlds.

Google sign-in is for obtaining your Android game. Microsoft/Xbox sign-in is separate and happens inside Minecraft; account-dependent game features still need work in the native runtime.

## Current limits

This remains an experimental project. CI builds the ARM64 app, checks that it contains no linked build-machine paths, runs native build diagnostics, and renders the packaged login and home screens without an account. Those checks do **not** verify Google’s live acceptance of an account, an actual purchased download, game rendering, Realms, Marketplace, or compatibility with every Minecraft release.

Google Play access uses the upstream community API implementation, not an official Google desktop download API. If Google rejects sign-in or delivery, the launcher reports the failure; it does not bypass purchase checks. Google controls which game versions your account can download. Use the built-in profiles to select an available version appropriate for the runtime.

The default game renderer remains the older OpenGL compatibility path. Latest Minecraft releases may require more graphics work. The experimental Metal adapter is present in the runtime but a compatible ANGLE driver pair is not bundled in this build; the GUI reports this if Metal is selected. MacBook Neo and physical-GPU gameplay remain unverified.

## Data

MacCraft uses `~/Library/Application Support/MacCraft/`:

| Folder | Contents |
| --- | --- |
| `store-versions/` | Game versions downloaded through the graphical launcher |
| `profiles/` | Launcher profiles |
| `apks/` | Temporary or retained Google Play downloads |
| `data/games/com.mojang/` | Worlds and game settings |
| `cache/` | Game cache |
| `versions/` | Installations imported through the older developer CLI |

Account settings use the MacCraft application identity; the key protecting saved login credentials is kept in the macOS login keychain. Signing out clears the saved Google account/cache and removes that key. Another launcher’s data is not imported automatically.

## Build from source

On ARM64 macOS, install Xcode Command Line Tools and Homebrew, then:

```sh
brew install python cmake ninja openssl@3 qtbase qtdeclarative qtsvg qtwebengine qttools protobuf libzip
git clone --recurse-submodules https://github.com/29navery/MacCraft.git
cd MacCraft
cmake -S . -B build/native -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_OSX_ARCHITECTURES=arm64
cmake --build build/native
ctest --test-dir build/native --output-on-failure
python3 scripts/build_runtime.py
python3 scripts/build_app.py
python3 scripts/package_app.py
```

The app is created at `dist/MacCraft.app` and its disk image at `dist/MacCraft-arm64.dmg`. The build applies reviewable, idempotent patches to pinned upstream submodules, so modified submodule status after building is expected. It does not download Minecraft or sign into an account while building.

The earlier CLI remains available for development; see [runtime/CLI instructions](docs/runtime-cli.md). See [architecture](docs/architecture.md) and [testing](docs/testing.md) for details.

## License

GPL-3.0-only. Original upstream components retain their licenses and attribution; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Dependency notices are bundled in the app. Minecraft is proprietary and is not included. MacCraft is unofficial and is not affiliated with Mojang, Microsoft, or Google.
