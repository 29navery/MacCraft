"""Read Android ELF metadata without mapping or executing game code."""
import struct


class InvalidELF(ValueError):
    pass


def inspect_elf(data: bytes) -> dict:
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise InvalidELF("Expected a little-endian ELF64 library")
    fields = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    kind, machine, version, _, phoff, _, _, ehsize, phsize, phcount, *_ = fields
    if kind != 3 or machine != 183 or version != 1 or ehsize != 64:
        raise InvalidELF("Expected an Android ARM64 (AArch64) shared library")
    if phsize != 56 or not phcount or phoff < 64 or phoff + phsize * phcount > len(data):
        raise InvalidELF("Invalid ELF program header table")
    loads, dynamics = [], []
    for i in range(phcount):
        ptype, flags, offset, address, _, size, memsize, align = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + i * phsize)
        if offset + size > len(data) or size > memsize:
            raise InvalidELF("ELF segment extends outside the file")
        if ptype == 1:
            if align not in (0, 1) and (align & (align - 1) or offset % align != address % align):
                raise InvalidELF("Invalid ELF segment alignment")
            loads.append((offset, address, size, memsize, flags, align))
        elif ptype == 2:
            if size % 16:
                raise InvalidELF("Invalid ELF dynamic table")
            dynamics.append((offset, size))
    if not loads:
        raise InvalidELF("ELF has no loadable segments")
    tags, needed = {}, []
    for offset, size in dynamics:
        for pos in range(offset, offset + size, 16):
            tag, value = struct.unpack_from("<qQ", data, pos)
            if tag == 0:
                break
            if tag == 1:
                needed.append(value)
            else:
                tags[tag] = value
    dependencies = []
    if needed:
        if 5 not in tags or 10 not in tags:
            raise InvalidELF("ELF dependency names have no string table")
        address, size = tags[5], tags[10]
        string_offset = next((o + address - a for o, a, s, *_ in loads
                              if a <= address and address + size <= a + s), None)
        if string_offset is None:
            raise InvalidELF("ELF string table is outside loadable file data")
        table = data[string_offset:string_offset + size]
        for index in needed:
            end = table.find(b"\0", index)
            if index >= len(table) or end < 0:
                raise InvalidELF("Invalid ELF dependency string")
            try:
                dependencies.append(table[index:end].decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise InvalidELF("Invalid ELF dependency encoding") from exc
    return {"architecture": "arm64-v8a", "dependencies": dependencies,
            "load_segments": len(loads), "segment_alignments": sorted({s[5] for s in loads}),
            "has_dynamic_table": bool(dynamics)}
