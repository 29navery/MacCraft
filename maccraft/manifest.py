"""Minimal, bounds-checked Android binary XML manifest reader."""
import struct
import xml.etree.ElementTree as ET


class InvalidManifest(ValueError):
    pass


def manifest_info(data: bytes) -> dict:
    if data.lstrip().startswith(b"<"):
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise InvalidManifest("Invalid XML manifest") from exc
        attrs = {key.rsplit("}", 1)[-1]: value for key, value in root.attrib.items()}
        if root.tag != "manifest":
            raise InvalidManifest("Expected manifest root")
        return _result(attrs)
    if len(data) < 8:
        raise InvalidManifest("Truncated Android manifest")
    kind, header, total = struct.unpack_from("<HHI", data)
    if kind != 3 or header != 8 or total != len(data):
        raise InvalidManifest("Invalid Android binary XML header")
    strings = []

    def string(index):
        if index >= len(strings):
            raise InvalidManifest("Invalid manifest string index")
        return strings[index]

    offset = header
    while offset < total:
        if offset + 8 > total:
            raise InvalidManifest("Truncated XML chunk")
        kind, head, size = struct.unpack_from("<HHI", data, offset)
        if head < 8 or size < head or offset + size > total:
            raise InvalidManifest("Invalid XML chunk bounds")
        chunk = data[offset:offset + size]
        if kind == 1:
            if head < 28:
                raise InvalidManifest("Invalid string pool header")
            count, _, flags, start, styles_start = struct.unpack_from("<IIIII", chunk, 8)
            if head + count * 4 > size or start < head + count * 4 or start > size:
                raise InvalidManifest("Invalid string pool offsets")
            limit = styles_start or size
            if limit < start or limit > size:
                raise InvalidManifest("Invalid string pool bounds")
            def length(pos, utf8):
                unit = 1 if utf8 else 2
                if pos + unit > limit:
                    raise InvalidManifest("Truncated string length")
                value = chunk[pos] if utf8 else struct.unpack_from("<H", chunk, pos)[0]
                pos += unit
                bit = 0x80 if utf8 else 0x8000
                if value & bit:
                    if pos + unit > limit:
                        raise InvalidManifest("Truncated string length")
                    tail = chunk[pos] if utf8 else struct.unpack_from("<H", chunk, pos)[0]
                    value = ((value & (bit - 1)) << (8 if utf8 else 16)) | tail
                    pos += unit
                return value, pos
            strings = []
            for i in range(count):
                pos = start + struct.unpack_from("<I", chunk, head + i * 4)[0]
                utf8 = bool(flags & 0x100)
                if utf8:
                    _, pos = length(pos, True)
                count_bytes, pos = length(pos, utf8)
                count_bytes *= 1 if utf8 else 2
                terminator = 1 if utf8 else 2
                if pos + count_bytes + terminator > limit or any(chunk[pos + count_bytes:pos + count_bytes + terminator]):
                    raise InvalidManifest("Invalid manifest string")
                try:
                    strings.append(chunk[pos:pos + count_bytes].decode("utf-8" if utf8 else "utf-16-le"))
                except UnicodeDecodeError as exc:
                    raise InvalidManifest("Invalid manifest string encoding") from exc
        elif kind == 0x102:
            if head < 16 or size < head + 20:
                raise InvalidManifest("Invalid start element")
            _, name, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", chunk, head)
            if string(name) == "manifest":
                first = head + attr_start
                if attr_start < 20 or attr_size < 20 or first + attr_size * attr_count > size:
                    raise InvalidManifest("Invalid manifest attributes")
                attrs = {}
                for i in range(attr_count):
                    _, key, raw, value_size, _, value_type, value = struct.unpack_from(
                        "<IIIHBBI", chunk, first + i * attr_size)
                    if value_size != 8:
                        raise InvalidManifest("Invalid typed XML attribute")
                    if raw != 0xffffffff:
                        attrs[string(key)] = string(raw)
                    elif value_type == 3:
                        attrs[string(key)] = string(value)
                    elif value_type in (0x10, 0x11):
                        attrs[string(key)] = str(value)
                return _result(attrs)
        offset += size
    raise InvalidManifest("Manifest root was not found")


def _result(attrs):
    if attrs.get("package") != "com.mojang.minecraftpe":
        raise InvalidManifest("Package must be com.mojang.minecraftpe")
    try:
        code = int(attrs["versionCode"])
    except (KeyError, ValueError) as exc:
        raise InvalidManifest("Minecraft manifest must have a numeric versionCode") from exc
    return {"package": attrs["package"], "version_code": code,
            "version_name": attrs.get("versionName", "unknown"), "split": attrs.get("split", "")}
