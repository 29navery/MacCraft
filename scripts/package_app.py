#!/usr/bin/env python3
"""Distribute MacCraft as a drag-to-Applications disk image."""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    app = ROOT / "dist/MacCraft.app"
    if not (app / "Contents/MacOS/MacCraft").is_file():
        raise FileNotFoundError("Build MacCraft.app first")
    staging = ROOT / "build/dmg"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(app, staging / "MacCraft.app", symlinks=True)
    os.symlink("/Applications", staging / "Applications")
    (staging / "Read Me.txt").write_text(
        "MacCraft\n\nDrag MacCraft.app to Applications, then open it and choose Sign in with Google.\n"
        "Use the Google account that owns Minecraft for Android. After signing in, choose Download and play.\n\n"
        "This developer app is not notarized. macOS may require allowing it in System Settings > Privacy & Security.\n"
        "Google login, downloads, and game compatibility still need testing with your own account and Mac.\n\n"
        "Source and instructions: https://github.com/29navery/MacCraft\n")
    subprocess.run(["hdiutil", "create", "-volname", "MacCraft", "-srcfolder", str(staging),
                    "-ov", "-format", "UDZO", str(ROOT / "dist/MacCraft-arm64.dmg")], check=True)


if __name__ == "__main__":
    main()
