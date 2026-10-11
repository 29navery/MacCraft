"""Transactional installation of user-supplied Minecraft Android packages."""
import hashlib
import json
import stat
import tempfile
import zipfile
from contextlib import ExitStack
from pathlib import Path, PurePosixPath

from .elf import inspect_elf
from .manifest import manifest_info

MAX_TOTAL = 4 * 1024 ** 3
MAX_ENTRIES = 100000


def _name(entry):
    name = entry.filename
    path = PurePosixPath(name)
    if (not name or "\\" in name or "\0" in name or path.is_absolute()
            or any(part in ("..", ".") for part in name.split("/"))):
        raise ValueError("Unsafe APK entry path: " + repr(name))
    mode = entry.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ValueError("APK symlinks are not supported")
    return name


def _hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def import_packages(paths, root):
    paths = [Path(p).expanduser().resolve(strict=True) for p in paths]
    if not paths:
        raise ValueError("Supply a base APK and, if necessary, its ARM64/assets splits")
    root = Path(root)
    versions = root / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    total = entries = 0
    with ExitStack() as stack:
        archives, sources, manifests = [], [], []
        for path in paths:
            archive = stack.enter_context(zipfile.ZipFile(path))
            names = set()
            for entry in archive.infolist():
                name = _name(entry)
                if name in names:
                    raise ValueError("Duplicate entry within APK: " + name)
                names.add(name)
                total += entry.file_size
                entries += 1
                if total > MAX_TOTAL or entries > MAX_ENTRIES:
                    raise ValueError("APK set exceeds the installation size or entry limit")
                if entry.flag_bits & 1:
                    raise ValueError("Encrypted APKs are not supported")
            if "AndroidManifest.xml" not in names:
                raise ValueError("Each APK must contain AndroidManifest.xml")
            if archive.getinfo("AndroidManifest.xml").file_size > 8 * 1024 ** 2:
                raise ValueError("Manifest is too large")
            manifests.append(manifest_info(archive.read("AndroidManifest.xml")))
            archives.append(archive)
            sources.append({"name": path.name, "sha256": _hash_file(path)})
        base_indices = [i for i, m in enumerate(manifests) if not m["split"]]
        if len(base_indices) != 1:
            raise ValueError("APK set must have exactly one base package")
        base = base_indices[0]
        info = manifests[base]
        if any(m["version_code"] != info["version_code"] for m in manifests):
            raise ValueError("Base APK and splits must have matching version codes")
        identity = hashlib.sha256("".join(sorted(s["sha256"] for s in sources)).encode()).hexdigest()
        version_id = str(info["version_code"]) + "-" + identity[:12]
        destination = versions / version_id
        if destination.exists():
            existing = json.loads((destination / "maccraft.json").read_text())
            if existing.get("package_hash") != identity:
                raise ValueError("Existing installation has conflicting package metadata")
            return version_id
        with tempfile.TemporaryDirectory(prefix=".import-", dir=versions) as temporary:
            staging = Path(temporary) / "game"
            staging.mkdir()
            hashes = {}
            for i, archive in enumerate(archives):
                for entry in archive.infolist():
                    name = entry.filename
                    if entry.is_dir():
                        continue
                    selected = (name.startswith("assets/") or name.startswith("lib/arm64-v8a/")
                                or (i == base and (name == "AndroidManifest.xml"
                                    or name == "resources.arsc" or name.startswith("res/"))))
                    if not selected:
                        continue
                    target = staging / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    duplicate = name in hashes
                    h = hashlib.sha256()
                    # Compare duplicate split resources without replacing the first copy.
                    with archive.open(entry) as stream:
                        output = tempfile.TemporaryFile() if duplicate else target.open("wb")
                        try:
                            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                                h.update(chunk)
                                output.write(chunk)
                        finally:
                            output.close()
                    digest = h.hexdigest()
                    if duplicate and hashes[name] != digest:
                        raise ValueError("Conflicting resources in APK splits: " + name)
                    hashes[name] = digest
            library = staging / "lib/arm64-v8a/libminecraftpe.so"
            if not library.is_file():
                raise ValueError("Missing ARM64 libminecraftpe.so; include the arm64-v8a APK split")
            libraries = {}
            for path in (staging / "lib/arm64-v8a").glob("*.so"):
                libraries[path.name] = inspect_elf(path.read_bytes())
            if not any(name.startswith("assets/") for name in hashes):
                raise ValueError("Missing Minecraft assets; include the base/assets APK splits")
            metadata = {**info, "id": version_id, "package_hash": identity,
                        "sources": sources, "libraries": libraries, "file_sha256": hashes}
            (staging / "maccraft.json").write_text(json.dumps(metadata, indent=2) + "\n")
            staging.rename(destination)
    return version_id


def installation(root, version_id):
    if not version_id or any(c not in "0123456789-abcdef" for c in version_id):
        raise ValueError("Invalid installation ID; use maccraft list")
    path = (Path(root) / "versions" / version_id).resolve()
    parent = (Path(root) / "versions").resolve()
    if path.parent != parent or not path.is_dir():
        raise ValueError("Installation was not found")
    info = json.loads((path / "maccraft.json").read_text())
    return path, info


def verify_installation(path, info):
    for name, expected in info["file_sha256"].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe path in installation metadata")
        target = (path / name).resolve()
        if not target.is_relative_to(path.resolve()) or not target.is_file() or _hash_file(target) != expected:
            raise ValueError("Installation file is missing or modified: " + name)
