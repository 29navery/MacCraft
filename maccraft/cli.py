"""Developer CLI. Python manages files; the C++ runtime executes ARM64 game code."""
import argparse
import fcntl
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .packages import import_packages, installation, verify_installation

REPO = Path(__file__).resolve().parent.parent


def default_root():
    return Path.home() / "Library/Application Support/MacCraft"


def native_host():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Launching requires macOS on ARM64 Apple silicon, without Rosetta")


def arm64_binary(path):
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Native runtime is missing or not executable: " + str(path))
    result = subprocess.run(["/usr/bin/lipo", "-archs", str(path)], capture_output=True, text=True)
    if result.returncode or "arm64" not in result.stdout.split():
        raise ValueError("Native runtime must be a macOS ARM64 executable")


def launch_plan(args, root):
    game, info = installation(root, args.version)
    runtime = Path(args.runtime).expanduser().resolve()
    environment = os.environ.copy()
    command = [str(runtime), "--game-dir", str(game) + "/",
               "--data-dir", str(root / "data") + "/",
               "--cache-dir", str(root / "cache") + "/",
               "--width", str(args.width), "--height", str(args.height)]
    if args.renderer == "metal":
        if not args.angle:
            raise ValueError("--renderer metal requires --angle /path/to/ANGLE/libs")
        angle = Path(args.angle).expanduser().resolve()
        for name in ("libEGL.dylib", "libGLESv2.dylib"):
            if not (angle / name).is_file():
                raise ValueError("Missing ANGLE library: " + str(angle / name))
        environment.update(MACCRAFT_EGL_LIBRARY=str(angle / "libEGL.dylib"),
                           MACCRAFT_GLES_LIBRARY=str(angle / "libGLESv2.dylib"),
                           MACCRAFT_RENDERER="metal", MACCRAFT_GLES_MINOR=args.gles[-1],
                           ANGLE_DEFAULT_PLATFORM="metal")
        environment.pop("VK_ICD_FILENAMES", None)
        command.append("--force-opengles")
    else:
        # Keep legacy GL deterministic, even if another launcher configured ANGLE.
        for key in ("MACCRAFT_EGL_LIBRARY", "MACCRAFT_GLES_LIBRARY", "MACCRAFT_RENDERER", "MACCRAFT_GLES_MINOR"):
            environment.pop(key, None)
        environment["MACCRAFT_RENDERER"] = "legacy"
    return command, environment, game, info


def launch(args, root):
    command, environment, game, info = launch_plan(args, root)
    if args.dry_run:
        print(json.dumps({"command": command, "renderer": args.renderer,
                          "environment": {k: v for k, v in environment.items()
                                          if k.startswith("MACCRAFT_") or k == "ANGLE_DEFAULT_PLATFORM"}}, indent=2))
        return 0
    native_host()
    arm64_binary(Path(command[0]))
    verify_installation(game, info)
    if args.renderer == "metal":
        probe = Path(args.probe).expanduser().resolve()
        arm64_binary(probe)
        subprocess.run([str(probe), args.angle, args.gles], check=True, env=environment)
    for folder in ("data", "cache", "logs"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    with (root / "data/runtime.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("MacCraft is already running with this world directory") from exc
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        log = root / "logs" / (stamp + ".log")
        print("Launch log: " + str(log), flush=True)
        with log.open("wb") as output:
            with subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT) as result:
                for line in iter(result.stdout.readline, b""):
                    output.write(line)
                    output.flush()
                    sys.stdout.write(line.decode("utf-8", errors="replace"))
                    sys.stdout.flush()
                result.wait()
        if result.returncode:
            print("Runtime exited with code %s; inspect %s" % (result.returncode, log), file=sys.stderr)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode


def parser():
    p = argparse.ArgumentParser(description="MacCraft experimental native ARM64 Bedrock runtime")
    p.add_argument("--root", type=Path, default=default_root(), help="Installation and world storage")
    sub = p.add_subparsers(dest="action", required=True)
    imp = sub.add_parser("import", help="Import your purchased Android APK and optional splits")
    imp.add_argument("apks", type=Path, nargs="+")
    sub.add_parser("list", help="List imported installations")
    check = sub.add_parser("verify", help="Verify installed package file hashes")
    check.add_argument("version")
    sub.add_parser("doctor", help="Report host and build prerequisites")
    run = sub.add_parser("launch", help="Launch an imported game through the native C++ runtime")
    run.add_argument("version")
    run.add_argument("--runtime", default=str(REPO / "build/runtime/install/bin/mcpelauncher-client"))
    run.add_argument("--renderer", choices=("legacy", "metal"), default="legacy")
    run.add_argument("--angle", help="Directory containing ARM64 ANGLE EGL/GLES dylibs")
    run.add_argument("--probe", default=str(REPO / "build/native/maccraft-graphics-probe"))
    run.add_argument("--gles", choices=("3.0", "3.1"), default="3.0", help="Minimum GLES version to probe")
    run.add_argument("--width", type=int, default=1280)
    run.add_argument("--height", type=int, default=720)
    run.add_argument("--dry-run", action="store_true", help="Print the launch plan without running code")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        if args.action == "import":
            root.mkdir(parents=True, exist_ok=True)
            with (root / "import.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(import_packages(args.apks, root))
        elif args.action == "list":
            for path in sorted((root / "versions").glob("*/maccraft.json")):
                info = json.loads(path.read_text())
                print("%s  Minecraft %s (ARM64)" % (info["id"], info["version_name"]))
        elif args.action == "verify":
            path, info = installation(root, args.version)
            verify_installation(path, info)
            print("Installation verified")
        elif args.action == "doctor":
            print(json.dumps({"system": platform.system(), "architecture": platform.machine(),
                              "native_launch_host": platform.system() == "Darwin" and platform.machine() == "arm64",
                              "tools": {name: shutil.which(name) for name in ("cmake", "ninja", "git", "clang++")},
                              "root": str(root)}, indent=2))
        else:
            if not 1 <= args.width <= 16384 or not 1 <= args.height <= 16384:
                raise ValueError("Window dimensions must be between 1 and 16384")
            return launch(args, root)
        return 0
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError,
            zipfile.BadZipFile) as exc:
        print("MacCraft: " + str(exc), file=sys.stderr)
        return 1
