#!/usr/bin/env python3
"""Create a developer archive that preserves executable permissions."""
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    paths = ["build/runtime/install", "build/native/maccraft-graphics-probe", "maccraft",
             "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "docs", "patches"]
    for name in paths:
        if not (ROOT / name).exists():
            raise FileNotFoundError("Missing build component: " + name)
    output = ROOT / "dist/MacCraft-arm64-developer.tar.gz"
    output.parent.mkdir(exist_ok=True)
    def keep(info):
        if "__pycache__" in Path(info.name).parts or info.name.endswith(".pyc"):
            return None
        return info
    with tarfile.open(output, "w:gz") as archive:
        for name in paths:
            archive.add(ROOT / name, arcname="MacCraft/" + name, filter=keep)
    print(output)


if __name__ == "__main__":
    main()
