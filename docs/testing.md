# Testing MacCraft

## Packaged graphical app

ARM64 macOS CI builds the app and runs it with `MACCRAFT_UI_SMOKE` pointing to an output directory, `QT_QPA_PLATFORM=cocoa`, and `QT_QUICK_BACKEND=software`. It verifies that the live QML welcome screen creates its Google sign-in button, saves `login.png`, navigates to the real home screen in test mode, and saves `home.png`. Test mode uses the Qt test settings identity, avoids Keychain access and version-list requests, and does not sign into Google or start game delivery. The app then exits. The screenshots are uploaded as the `MacCraft-UI-previews` artifact.

On a physical Mac, test sign-in, cancellation, account purchase failure, an owned game download including splits, install, Play, restart with a remembered account, and sign-out. Confirm that a second Mac without Homebrew can open the packaged app and Google login window. These live-account checks have not been completed by CI. Microsoft/Xbox game services are separate from Google Play access.

## Automated checks

```sh
python3 -m unittest discover -s tests -v
cmake -S . -B build/native
cmake --build build/native
ctest --test-dir build/native --output-on-failure
python3 scripts/build_runtime.py --prepare-only
python3 scripts/build_runtime.py --prepare-only
```

The package fixtures contain synthetic XML/ELF structures, not Minecraft. GitHub Actions also compiles the native ARM64 compatibility engine and executes `mcpelauncher-client --build-info`. This tests a build, not game launch.

## Physical-Mac acceptance checks

Record the Mac model, chip, macOS version, source APK version/code, runtime revision, ANGLE revision and graphics-probe output with every test. Use a separate `--root` and disposable worlds.

| Check | Acceptance condition | Current status |
| --- | --- | --- |
| APK import | Real base plus ARM64/assets splits imports and hashes verify | Untested with a real APK |
| Legacy baseline | A supported older ARM64 release reaches title screen | Untested |
| Metal preflight | Required GLES context, shader translation, draw and readback pass | Implemented; GPU run untested |
| Cocoa presentation | Metal game window draws and survives resize/fullscreen | Untested |
| World lifecycle | Create, save, exit, reopen; contents persist correctly | Untested |
| Input and audio | Mouse capture, WASD, text entry, controller, sound | Untested |
| Multiplayer | Join a matching-version Bedrock server by address | Untested |
| Accounts | Microsoft login, friends and invitations | Account components not packaged |
| Services | Realms, Marketplace and purchased content | Unimplemented/unverified |
| Latest Minecraft | Current ARM64 release launches and plays | Unverified |
| MacBook Neo | ARM64 binary and renderer pass on physical A18 Pro hardware | Unverified |

After a crash, retain the timestamped launch log and macOS crash report. Do not post authentication callback URLs or account tokens from logs publicly. Diagnose the first failed dependency/graphics operation before changing game code or claiming version support.
