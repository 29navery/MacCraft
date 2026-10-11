# Third-party notices

MacCraft's native runtime is based on the Minecraft Bedrock Launcher project and its contributors:

- https://github.com/minecraft-linux/mcpelauncher-manifest
- Pinned revision: `91220f0f7ccfd460090d14056ab1bf12e82869b1`
- Manifest license: GNU GPL version 3. See `vendor/runtime/LICENSE`.

The runtime includes separately licensed submodules, including its Android linker, libc shims, libjnivm, GLFW fork, SDL3, and supporting libraries. Their original license files must accompany any distributed build as applicable. MacCraft's patch files modify upstream sources and must not be represented as upstream originals.

ANGLE is optional, supplied separately, and is not distributed by this repository. Its own license and third-party licenses apply: https://github.com/google/angle/blob/main/LICENSE.

Minecraft game files are not included. Their ownership and licensing remain with their respective rights holders.
