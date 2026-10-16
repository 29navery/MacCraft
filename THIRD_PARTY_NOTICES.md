# Third-party notices

MacCraft's native runtime is based on the Minecraft Bedrock Launcher project and its contributors:

- https://github.com/minecraft-linux/mcpelauncher-manifest
- Pinned revision: `91220f0f7ccfd460090d14056ab1bf12e82869b1`
- Manifest license: GNU GPL version 3. See `vendor/runtime/LICENSE`.

The runtime includes separately licensed submodules, including its Android linker, libc shims, libjnivm, GLFW fork, SDL3, and supporting libraries. Their original license files must accompany any distributed build as applicable. MacCraft's patch files modify upstream sources and must not be represented as upstream originals.

ANGLE is optional, supplied separately, and is not distributed by this repository. Its own license and third-party licenses apply: https://github.com/google/angle/blob/main/LICENSE.

Minecraft game files are not included. Their ownership and licensing remain with their respective rights holders.

The graphical launcher and Google Play integration use:

- https://github.com/minecraft-linux/mcpelauncher-ui-manifest (Qt 6 branch, pinned `779d057d9d729e492c403d4e0927006342da1dfe`).
- Its mcpelauncher-ui-qt, playdl-signin-ui-qt, Google-Play-API, extraction and supporting submodules, each retaining its original license.
- Qt 6, with its original Qt and third-party licenses: https://www.qt.io/licensing/. Google sign-in uses the system WebKit framework on macOS; Chromium is not bundled.
- Protocol Buffers, Abseil, libzip, OpenSSL, and their dependencies, retaining their upstream licenses.

MacCraft's welcome screen, packaging, integration patches, and macOS Keychain adapter are MacCraft changes, not upstream originals. Corresponding source and patches are available in this repository at the revision recorded in the app's bundled `source.json`.
