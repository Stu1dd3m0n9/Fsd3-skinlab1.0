# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""XUIZ (.xzp) container reader/writer.

Layout: magic b'XUIZ', big-endian header, raw file bytes.
  header: u32 flags, u32 total_len, u32 unk, u32 dir_len, u16 count
  per entry: u32 file_len, u32 file_off (from data start),
             u8 name_len (UTF-16 code units), name UTF-16BE with \\ separators
"""
from __future__ import annotations

import os
import struct

MAGIC = b"XUIZ"


class XzpError(ValueError):
    pass


def read_xzp(path: str) -> dict[str, bytes]:
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:4] != MAGIC:
        raise XzpError("not an XUIZ package")
    _flags, total, _unk, dirlen, count = struct.unpack(">LLLLH", blob[4:22])
    if total != len(blob):
        raise XzpError(f"total_len mismatch: header={total} actual={len(blob)}")
    files: dict[str, bytes] = {}
    pos = 22
    base = 22 + dirlen
    for _ in range(count):
        flen, fptr, fnlen = struct.unpack(">LLB", blob[pos:pos + 9])
        pos += 9
        name = blob[pos:pos + 2 * fnlen].decode("utf-16-be")
        pos += 2 * fnlen
        files[name.lower()] = blob[base + fptr:base + fptr + flen]
    return files


def write_xzp(skin_folder: str, out_path: str) -> tuple[int, int]:
    entries: list[tuple[str, bytes]] = []
    for root, _d, names in os.walk(skin_folder):
        for name in names:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, skin_folder).replace("/", "\\")
            if len(rel.encode("utf-16-be")) // 2 > 255:
                continue
            with open(full, "rb") as fh:
                entries.append((rel, fh.read()))
    entries.sort(key=lambda t: t[0].lower())
    directory = b""
    off = 0
    for rel, data in entries:
        name = rel.encode("utf-16-be")
        directory += struct.pack(">L", len(data))
        directory += struct.pack(">L", off)
        directory += struct.pack(">B", len(name) // 2)
        directory += name
        off += len(data)
    total = 4 + 18 + len(directory) + off
    header = MAGIC + struct.pack(">L", 1) + struct.pack(">L", total)
    header += struct.pack(">L", 0) + struct.pack(">L", len(directory))
    header += struct.pack(">H", len(entries))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(header)
        fh.write(directory)
        for _rel, data in entries:
            fh.write(data)
    return len(entries), total
