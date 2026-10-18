#!/usr/bin/env python3
"""Read-only, version-locked checks for the investigated native audio route.

This is an evidence checker, NOT a behavior patch. No process, preference,
project, cache, or application file is changed.
"""
import argparse
import hashlib
import json
import pathlib
import struct

EXPECTED_SHA256 = "6a7854189fe4b4c5e9b74441122ce62ce637c10780287fe6079b2e13d293ac33"
SITES = (
    ("audio_provider_init_context", 0xB743B28, "7d910094", 0xB76811C),
    ("audio_context_video_default", 0xB7681D8, "63feff97", 0xB767B64),
    ("compound_default_path", 0xB767C80, "7c732294", 0xC004A70),
    ("collector_video_readiness", 0xB75E454, "53862694", 0xC0FFDA0),
    ("loudness_create_input", 0xB7B534C, "2f020094", 0xB7B5C08),
    ("loudness_track_selection", 0xBF15F34, "950dc494", 0xF019588),
    ("loudness_engine_create", 0xBF16004, "970dc494", 0xF019660),
    ("loudness_scan_invoke", 0xBF16134, "00013fd6", None),
)


def text_mapping(data):
    if len(data) < 32 or struct.unpack_from("<I", data)[0] != 0xFEEDFACF:
        raise ValueError("Requires the investigated thin little-endian Mach-O")
    cpu_type, _, _, ncmds = struct.unpack_from("<4I", data, 4)
    if cpu_type != 0x0100000C:
        raise ValueError("Requires ARM64")
    offset = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > len(data):
            raise ValueError("Malformed load command")
        if cmd == 0x19 and data[offset + 8:offset + 24].rstrip(b"\0") == b"__TEXT":
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", data, offset + 24)
            return vmaddr, vmsize, fileoff, filesize
        offset += size
    raise ValueError("Missing __TEXT")


def inspect(path):
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    vmaddr, _, fileoff, filesize = text_mapping(data)
    checks = []
    for name, address, expected_bytes, expected_target in SITES:
        position = address - vmaddr + fileoff
        if not fileoff <= position <= fileoff + filesize - 4:
            raise ValueError("Evidence site outside __TEXT")
        raw = data[position:position + 4]
        word = int.from_bytes(raw, "little")
        target = None
        if word & 0xFC000000 == 0x94000000:
            immediate = word & 0x03FFFFFF
            if immediate & 0x02000000:
                immediate -= 0x04000000
            target = address + immediate * 4
        checks.append({
            "name": name, "vm_address": hex(address),
            "file_offset": hex(position), "bytes": raw.hex(),
            "target": hex(target) if target is not None else None,
            "match": raw.hex() == expected_bytes and target == expected_target,
        })
    return {
        "kind": "read_only_static_evidence", "binary_name": path.name,
        "sha256": sha, "version_match": sha == EXPECTED_SHA256,
        "sites": checks, "all_checks_match": sha == EXPECTED_SHA256 and all(x["match"] for x in checks),
        "audio_patch_status": "research_only_no_behavior_patch",
        "runtime_speedup_established": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=pathlib.Path)
    args = parser.parse_args()
    result = inspect(args.library)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["all_checks_match"] else 2)


if __name__ == "__main__":
    main()
