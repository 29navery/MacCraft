#!/usr/bin/env python3
"""Build and deploy a native, self-contained MacCraft.app."""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVISION = "779d057d9d729e492c403d4e0927006342da1dfe"


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def prepare(source):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if revision != REVISION:
        raise ValueError("Launcher source revision does not match the pin")
    for name, directory in (("launcher-maccraft.patch", "mcpelauncher-ui-qt"),
                            ("launcher-signin.patch", "playdl-signin-ui-qt")):
        patch = ROOT / "patches" / name
        target = source / directory
        applied = subprocess.run(["git", "apply", "--reverse", "--check", str(patch)], cwd=target, capture_output=True)
        if applied.returncode:
            run("git", "apply", "--check", patch, cwd=target)
            run("git", "apply", patch, cwd=target)
    target = source / "mcpelauncher-ui-qt"
    for name in ("MacCraftKeychain.h", "MacCraftKeychain.mm"):
        shutil.copyfile(ROOT / "ui" / name, target / name)
    shutil.copyfile(ROOT / "ui/LoginScreen.qml", target / "qml/LoginScreen.qml")


def macho(path):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(4) in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                                  b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf")


def dependencies(path):
    output = subprocess.check_output(["otool", "-L", str(path)], text=True)
    return [line.strip().split(" (compatibility version", 1)[0]
            for line in output.splitlines()[1:] if line.startswith("\t")]


def relocate(app):
    """Bundle remaining non-system dylibs, including the native engine's OpenSSL."""
    frameworks = app / "Contents/Frameworks"
    frameworks.mkdir(exist_ok=True)
    pending = [p for p in app.rglob("*") if macho(p)]
    copied = {}
    for path in pending:
        for name in dependencies(path):
            if not name.startswith(("/opt/homebrew/", "/usr/local/", "/Users/")):
                continue
            source = Path(name)
            if ".framework/" in name:
                raise RuntimeError("Qt framework was not deployed: " + name)
            target = frameworks / source.name
            resolved = source.resolve()
            if source.name in copied and copied[source.name] != resolved:
                raise RuntimeError("Conflicting bundled dependency: " + source.name)
            if not target.exists():
                shutil.copy2(resolved, target)
                target.chmod(0o755)
                run("install_name_tool", "-id", "@rpath/" + target.name, target)
                copied[source.name] = resolved
                pending.append(target)
            relative = os.path.relpath(target, path.parent)
            run("install_name_tool", "-change", name, "@loader_path/" + relative, path)
    # No builder paths should remain in linked dependencies of distributed binaries.
    for path in app.rglob("*"):
        if macho(path):
            leaking = [d for d in dependencies(path) if d.startswith(("/opt/homebrew/", "/usr/local/", "/Users/"))]
            if leaking:
                raise RuntimeError("Unbundled dependencies in " + str(path) + ": " + repr(leaking))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    source = ROOT / "vendor/launcher"
    if not (source / "CMakeLists.txt").exists():
        run("git", "submodule", "update", "--init", "--recursive", "--jobs", "8", cwd=ROOT)
    prepare(source)
    if args.prepare_only:
        return
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("Build MacCraft.app on ARM64 macOS")
    native = ROOT / "build/runtime/install"
    if not (native / "bin/mcpelauncher-client").is_file():
        parser.error("Build the native runtime first with scripts/build_runtime.py")
    brew = subprocess.check_output(["brew", "--prefix"], text=True).strip()
    prefixes = [brew + "/opt/" + n for n in ("qtbase", "qtdeclarative", "qtsvg", "qtwebengine", "qtwebchannel", "qttools", "protobuf", "abseil", "libzip", "openssl@3")]
    build = ROOT / "build/launcher"
    run("cmake", "-S", source, "-B", build, "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OSX_ARCHITECTURES=arm64",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5", "-DCMAKE_PREFIX_PATH=" + ";".join(prefixes + [brew]),
        "-DOPENSSL_ROOT_DIR=" + brew + "/opt/openssl@3", "-DUSE_WEBENGINE=ON",
        "-DGAME_LAUNCHER_PATH=.", "-DLAUNCHER_VERSION_NAME=MacCraft 0.2.0", "-DLAUNCHER_VERSION_CODE=2",
        "-DLAUNCHER_ENABLE_GOOGLE_PLAY_LICENCE_CHECK=ON", "-DLAUNCHER_ENABLE_GLFW=OFF",
        "-DENABLE_UPDATE_CHECK=OFF", "-DENABLE_APPIMAGE_UPDATE_CHECK=OFF")
    run("cmake", "--build", build, "--target", "mcpelauncher-ui-qt", "--parallel", str(min(os.cpu_count() or 2, 4)))
    app = ROOT / "dist/MacCraft.app"
    if app.exists():
        shutil.rmtree(app)
    app.parent.mkdir(exist_ok=True)
    shutil.copytree(build / "mcpelauncher-ui-qt/MacCraft.app", app, symlinks=True)
    shutil.copy2(source / "mcpelauncher-ui-qt/Resources/mcpelauncher-icon.icns", app / "Contents/Resources/MacCraft.icns")
    shutil.copy2(native / "bin/mcpelauncher-client", app / "Contents/MacOS/mcpelauncher-client")
    shutil.copy2(ROOT / "build/native/maccraft-graphics-probe", app / "Contents/MacOS/maccraft-graphics-probe")
    # The native loader locates these Android shim and host audio libraries relative to its executable.
    shutil.copytree(native / "share/mcpelauncher", app / "Contents/share/mcpelauncher", symlinks=True)
    deploy = next((Path(brew) / path for path in ("opt/qttools/bin/macdeployqt", "opt/qtbase/bin/macdeployqt", "bin/macdeployqt", "opt/qt/bin/macdeployqt") if (Path(brew) / path).exists()), None)
    if deploy is None:
        raise FileNotFoundError("Install Qt's macdeployqt deployment tool")
    run(deploy, app, "-qmldir=" + str(source / "mcpelauncher-ui-qt/qml"),
        "-executable=" + str(app / "Contents/MacOS/mcpelauncher-client"), "-always-overwrite")
    relocate(app)
    run("lipo", app / "Contents/MacOS/MacCraft", "-verify_arch", "arm64")
    run("lipo", app / "Contents/MacOS/mcpelauncher-client", "-verify_arch", "arm64")
    # Collect both source trees and their downloaded build dependencies.
    run(sys.executable, ROOT / "scripts/collect_licenses.py")
    shutil.copytree(native / "share/maccraft/licenses", app / "Contents/Resources/licenses", dirs_exist_ok=True)
    run("codesign", "--force", "--deep", "--sign", "-", "--entitlements", ROOT / "ui/entitlements.plist", app)
    run("codesign", "--verify", "--deep", "--strict", app)
    run(app / "Contents/MacOS/mcpelauncher-client", "--build-info")
    print("Built " + str(app))


if __name__ == "__main__":
    main()
