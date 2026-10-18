#!/usr/bin/env python3
"""Version-locked copy-only Jianying experiment builder. Python standard library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import struct
import subprocess
import sys

LIBRARY = Path('Contents/Frameworks/libVECreator.dylib')
SOURCE_SHA256 = '6a7854189fe4b4c5e9b74441122ce62ce637c10780287fe6079b2e13d293ac33'
PATCHES = {'taskcenter': [(0x5f4df0c, bytes.fromhex('289bff17'), bytes.fromhex('c0035fd6'))]}

class Refusal(RuntimeError):
    pass

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def within(path, root):
    return path == root or root in path.parents

def paths(source, output):
    raw_source, raw_output = Path(source).expanduser(), Path(output).expanduser()
    if raw_source.is_symlink() or raw_output.is_symlink():
        raise Refusal('Application roots must not be symlinks')
    source, output = raw_source.resolve(strict=True), raw_output.resolve()
    if not source.is_dir() or source.suffix != '.app' or output.suffix != '.app':
        raise Refusal('Source and output must be .app directories')
    if within(output, source) or within(source, output):
        raise Refusal('Source and output must be disjoint; no in-place or nested output')
    if os.path.lexists(raw_output) or output.exists():
        raise Refusal('Output already exists; refusing overwrite')
    if not output.parent.is_dir():
        raise Refusal('Output parent must already exist')
    return source, output

def inventory(root):
    """Hash regular files and record links/modes; never traverse bundle symlinks."""
    root = root.resolve(strict=True)
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            p = Path(directory) / name
            rel = p.relative_to(root).as_posix()
            st = p.lstat()
            mode = stat.S_IMODE(st.st_mode)
            if stat.S_ISLNK(st.st_mode):
                if not within(p.resolve(), root):
                    raise Refusal('Symlink escapes application bundle: ' + rel)
                result[rel] = ('link', mode, os.readlink(p))
            elif stat.S_ISREG(st.st_mode):
                result[rel] = ('file', mode, digest(p))
            elif stat.S_ISDIR(st.st_mode):
                result[rel] = ('directory', mode)
            else:
                raise Refusal('Unsupported special file: ' + rel)
    return result

def validate_binary(path, expected_sha=None):
    if digest(path) != (expected_sha or SOURCE_SHA256):
        raise Refusal('Unsupported libVECreator SHA-256; no best-effort patching')
    with path.open('rb') as stream:
        header = stream.read(8)
    if header[:4] != bytes.fromhex('cffaedfe') or struct.unpack('<I', header[4:8])[0] != 0x100000c:
        raise Refusal('Expected thin little-endian ARM64 Mach-O')

def validate_regions(path, regions):
    end = -1
    with path.open('rb') as stream:
        for offset, before, after in sorted(regions):
            if offset < end or not before or len(before) != len(after) or offset % 4:
                raise Refusal('Invalid or overlapping patch regions')
            stream.seek(offset)
            if stream.read(len(before)) != before:
                raise Refusal('Unexpected instruction bytes at ' + hex(offset))
            end = offset + len(before)

def selected_regions(selection):
    if selection == 'none':
        return []
    if selection not in PATCHES:
        raise Refusal('Unknown patch: ' + selection)
    return PATCHES[selection]

def plan(source, output, selection, custom_regions=None):
    source, output = paths(source, output)
    info = plistlib.loads((source / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleShortVersionString') != '11.6.0':
        raise Refusal('Only application version 11.6.0 is supported')
    baseline = inventory(source)
    library = source / LIBRARY
    if library.is_symlink() or not library.is_file():
        raise Refusal('Patch library must be a regular file')
    validate_binary(library)
    regions = selected_regions(selection) if custom_regions is None else custom_regions
    validate_regions(library, regions)
    return source, output, regions, baseline

def run(*args):
    proc = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if proc.returncode:
        raise Refusal('Command failed: ' + str(args[0]) + '\n' + proc.stderr[-3000:])

def copy_bundle(source, output):
    # Caller exclusively reserves output. Preserve macOS xattrs, resource forks and ACLs.
    try:
        run('/bin/cp', '-cRp', str(source) + '/.', str(output) + '/')
    except Refusal:
        # Partial clone output is confined to this invocation's new directory.
        for child in output.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
        run('/usr/bin/ditto', '--rsrc', '--extattr', '--acl', source, output)

def sign_bundle(output):
    flags = '--preserve-metadata=identifier,entitlements,flags,runtime'
    run('/usr/bin/codesign', '--force', '--sign', '-', flags, output / LIBRARY)
    run('/usr/bin/codesign', '--force', '--sign', '-', flags, output)
    run('/usr/bin/codesign', '--verify', '--deep', '--strict', output)

def assert_patch_only(source, output, regions):
    """Compare entire library to source plus planned regions, including unpatched bytes."""
    with source.open('rb') as old, output.open('rb') as new:
        base = 0
        while chunk := old.read(8 * 1024 * 1024):
            expected = bytearray(chunk)
            for offset, before, after in regions:
                left, right = max(offset, base), min(offset + len(after), base + len(chunk))
                if left < right:
                    expected[left-base:right-base] = after[left-offset:right-offset]
            if new.read(len(chunk)) != expected:
                raise Refusal('Copied library differs outside the exact planned bytes')
            base += len(chunk)
        if new.read(1):
            raise Refusal('Copied library size changed')

def build(source, output, selection, copier=copy_bundle, signer=sign_bundle, custom_regions=None):
    source, output, regions, baseline = plan(source, output, selection, custom_regions)
    # Atomic reservation prevents overwriting an existing destination.
    output.mkdir()
    try:
        copier(source, output)
        copied = inventory(output)
        if copied != baseline:
            raise Refusal('Copied bundle does not match source inventory')
        for rel, entry in copied.items():
            if entry[0] == 'file' and os.path.samefile(source / rel, output / rel):
                raise Refusal('Copy contains a hardlink to source: ' + rel)
        target = output / LIBRARY
        validate_regions(target, regions)
        with target.open('r+b') as stream:
            for offset, before, after in regions:
                stream.seek(offset)
                stream.write(after)
        assert_patch_only(source / LIBRARY, target, regions)
        changed = inventory(output)
        expected = dict(baseline)
        if regions:
            expected[LIBRARY.as_posix()] = ('file', stat.S_IMODE(target.stat().st_mode), digest(target))
        if changed != expected:
            raise Refusal('Unexpected bundle changes before signing')
        pre_sign = digest(target)
        signer(output)
        # Signing changes signature blobs; opcode semantics must remain intact.
        with target.open('rb') as stream:
            for offset, before, after in regions:
                stream.seek(offset)
                if stream.read(len(after)) != after:
                    raise Refusal('Patched instruction changed during signing')
        if inventory(source) != baseline:
            raise Refusal('Source changed during build; result must not be used')
        return {'status': 'copy_built_signature_verified_not_launched', 'patch': selection,
                'source_library_sha256': SOURCE_SHA256, 'library_sha256_before_signing': pre_sign,
                'library_sha256_after_signing': digest(target),
                'semantic_regions': [{'offset': hex(a), 'before': b.hex(), 'after': c.hex()} for a,b,c in regions],
                'source_inventory_unchanged': True, 'runtime_tested_by_this_command': False}
    except BaseException:
        # A failed output is left for review; never delete user files or source.
        raise

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-app', required=True, type=Path)
    parser.add_argument('--output-app', required=True, type=Path)
    parser.add_argument('--patch', choices=['none', *PATCHES], required=True)
    parser.add_argument('--apply', action='store_true', help='Create and ad-hoc sign the copy; default is read-only plan')
    args = parser.parse_args(argv)
    try:
        if args.apply:
            if sys.platform != 'darwin':
                raise Refusal('Building and signing requires macOS')
            result = build(args.source_app, args.output_app, args.patch)
        else:
            source, output, regions, baseline = plan(args.source_app, args.output_app, args.patch)
            result = {'status': 'read_only_plan_validated', 'patch': args.patch,
                      'source_app': str(source), 'output_app': str(output),
                      'inventory_entries': len(baseline), 'semantic_patch_bytes': sum(len(b) for _,b,_ in regions),
                      'source_library_sha256': SOURCE_SHA256}
        print(json.dumps(result, indent=2))
        return 0
    except (Refusal, OSError, ValueError, plistlib.InvalidFileException) as exc:
        print('REFUSED: ' + str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
