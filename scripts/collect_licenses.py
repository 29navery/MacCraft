#!/usr/bin/env python3
"""Preserve upstream/dependency notices alongside developer binaries."""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def collect():
    destination = ROOT / "build/runtime/install/share/maccraft/licenses"
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    sources = [("runtime", ROOT / "vendor/runtime"),
                           ("downloaded-dependencies", ROOT / "build/runtime/_deps"),
                           ("launcher", ROOT / "vendor/launcher")]
    if shutil.which("brew"):
        brew = Path(subprocess.check_output(["brew", "--prefix"], text=True).strip())
        for formula in ("qtbase", "qtdeclarative", "qtwebengine", "qtwebchannel", "qtsvg", "qttools", "protobuf", "abseil", "libzip", "openssl@3"):
            if (brew / "opt" / formula).exists():
                sources.append(("dependencies/" + formula, (brew / "opt" / formula).resolve()))
    for prefix, source in sources:
        if not source.exists():
            continue
        for path in source.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            name = path.name.upper()
            if (name.startswith(("LICENSE", "LICENCE", "COPYING", "COPYRIGHT"))
                    or name in ("NOTICE", "NOTICE.TXT", "THIRD_PARTY_NOTICES")
                    or any(part.upper() in ("LICENSES", "LICENCES", "COPYRIGHTS") for part in path.relative_to(source).parts)):
                target = destination / prefix / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                count += 1
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / name, destination / name)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (destination / "source.json").write_text(json.dumps({
        "maccraft_source": "https://github.com/29navery/MacCraft",
        "maccraft_revision": revision,
        "runtime_revision": "91220f0f7ccfd460090d14056ab1bf12e82869b1",
        "build_instructions": "README.md",
        "patches": "patches/",
        "launcher_revision": "779d057d9d729e492c403d4e0927006342da1dfe",
    }, indent=2) + "\n")
    print("Collected %s dependency license/notice files" % count)


if __name__ == "__main__":
    collect()
