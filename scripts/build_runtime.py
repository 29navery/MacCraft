#!/usr/bin/env python3
"""Build the pinned native runtime with MacCraft's reversible source patches."""
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVISION = "91220f0f7ccfd460090d14056ab1bf12e82869b1"


def run(*args, cwd=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def apply_patches(source):
    for patch, directory in (("client-build.patch", "mcpelauncher-client"),
                             ("client-metal.patch", "mcpelauncher-client"),
                             ("window-metal.patch", "game-window")):
        path = ROOT / "patches" / patch
        target = source / directory
        check = subprocess.run(["git", "apply", "--reverse", "--check", str(path)],
                               cwd=target, capture_output=True)
        if check.returncode == 0:
            continue
        run("git", "apply", "--check", path, cwd=target)
        run("git", "apply", path, cwd=target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "vendor/runtime")
    parser.add_argument("--prepare-only", action="store_true", help="Validate and apply source patches without compiling")
    args = parser.parse_args()
    source = args.source.resolve()
    if not args.prepare_only and (platform.system() != "Darwin" or platform.machine() != "arm64"):
        parser.error("Build the runtime on ARM64 macOS without Rosetta")
    if not source.is_dir():
        run("git", "submodule", "update", "--init", "--recursive", "--jobs", "8", cwd=ROOT)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if head != REVISION:
        parser.error("Runtime checkout does not match the pinned revision: " + head)
    apply_patches(source)
    if args.prepare_only:
        return
    build = ROOT / "build/runtime"
    brew = subprocess.check_output(["brew", "--prefix"], text=True).strip()
    run("cmake", "-S", source, "-B", build, "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DCMAKE_OSX_ARCHITECTURES=arm64",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5", "-DCMAKE_INSTALL_PREFIX=" + str(build / "install"),
        "-DCMAKE_PREFIX_PATH=" + brew, "-DOPENSSL_ROOT_DIR=" + brew + "/opt/openssl@3",
        "-DBUILD_UI=OFF", "-DBUILD_WEBVIEW=OFF", "-DGAMEWINDOW_SYSTEM=GLFW",
        "-DUSE_OWN_CURL=OFF", "-DUSE_GAMECONTROLLERDB=OFF", "-DUSE_SDL3_AUDIO=ON",
        "-DUSE_IMGUI=OFF", "-DXAL_WEBVIEW_USE_QT=OFF", "-DXAL_WEBVIEW_USE_CLI=ON",
        "-DENABLE_QT_ERROR_UI=OFF", "-DENABLE_DEV_PATHS=OFF")
    run("cmake", "--build", build, "--parallel", str(min(os.cpu_count() or 2, 8)))
    run("cmake", "--install", build)
    run(sys.executable, ROOT / "scripts/collect_licenses.py")
    runtime = build / "install/bin/mcpelauncher-client"
    run("lipo", "-verify_arch", "arm64", runtime)
    run(runtime, "--version")


if __name__ == "__main__":
    main()
