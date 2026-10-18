"""Build exact-version-locked isolated apps; never launch or touch project data."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
import os
import platform
import plistlib
import sys

if not __debug__:
    raise RuntimeError("This experimental builder refuses Python -O: verification assertions must remain active")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import jianying_patch as portable

ROOT = Path(__file__).resolve().parent
EXPECTED = "6a7854189fe4b4c5e9b74441122ce62ce637c10780287fe6079b2e13d293ac33"
REL = Path("Contents/Frameworks/libVECreator.dylib")
CAVE = 0x4000
HOOKS = {
    0xc00b818: (bytes.fromhex("880240f9 08614139 e8010035"), "_parallel2_scheduler"),
    0xc00be74: (bytes.fromhex("29008052 09610139 69008052"), "_parallel2_admission"),
}
FAR = {
    "_far_scheduler_return": 0xc00b85c,
    "_far_scheduler_advance": 0xc00b80c,
    "_far_scheduler_ready": 0xc00b824,
    "_far_admission_defer": 0xc00bf64,
    "_far_admission_resume": 0xc00be80,
}
UI_OFFSET = 0x5f4df0c
UI_BEFORE = bytes.fromhex("289bff17")
UI_AFTER = bytes.fromhex("c0035fd6")


def run(*args):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"Command failed: {args!r}\n{p.stdout[-1000:]}\n{p.stderr[-3000:]}")
    return p.stdout


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(8*1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def layout(b):
    assert struct.unpack_from("<II", b) == (0xfeedfacf, 0x100000c), "Requires thin ARM64"
    count, command_size = struct.unpack_from("<II", b, 16)
    pos = 32
    sections = {}
    segments = []
    symbols = None
    for _ in range(count):
        cmd, size = struct.unpack_from("<II", b, pos)
        assert size >= 8
        if cmd == 0x19:
            name = bytes(b[pos+8:pos+24]).split(b"\0")[0].decode()
            vm, vs, off, fs, maxp, initp, ns = struct.unpack_from("<QQQQiiI", b, pos+24)
            segments.append(dict(name=name, vm=vm, size=vs, fileoff=off, header=pos,
                                 filesize=fs, maxprot=maxp, initprot=initp))
            for i in range(ns):
                at = pos+72+80*i
                sn = bytes(b[at:at+16]).split(b"\0")[0].decode()
                seg = bytes(b[at+16:at+32]).split(b"\0")[0].decode()
                a, z, o, align, reloc, nr = struct.unpack_from("<QQIIII", b, at+32)
                sections[(seg, sn)] = dict(addr=a,size=z,offset=o,nreloc=nr,header=at)
        elif cmd == 2:
            symbols = struct.unpack_from("<IIII", b, pos+8)
        pos += size
    assert pos == 32+command_size
    return dict(header_end=pos, sections=sections, segments=segments, symbols=symbols)


def symbol_offsets(path):
    result = {}
    for line in run("xcrun", "nm", "-nm", path).splitlines():
        m = re.match(r"([0-9a-f]+).*? (_\S+)$", line)
        if m:
            result[m[2]] = int(m[1], 16)
    return result


def far_jump(pc, target):
    # ADRP x16; ADD x16,x16,#pageoffset; BR x16. ADRP permits signed4GB.
    delta = (target >> 12) - (pc >> 12)
    assert -(1 << 20) <= delta < (1 << 20)
    imm = delta & ((1 << 21)-1)
    adrp = 0x90000010 | ((imm & 3) << 29) | ((imm >> 2) << 5)
    add = 0x91000210 | ((target & 0xfff) << 10)
    return struct.pack("<III", adrp, add, 0xd61f0200)


def decode_far(pc, code):
    a, d, j = struct.unpack("<III", code)
    assert a & 0x9f00001f == 0x90000010
    assert d & 0xffc003ff == 0x91000210
    assert j == 0xd61f0200
    imm = ((a >> 29) & 3) | (((a >> 5) & 0x7ffff) << 2)
    if imm & (1 << 20):
        imm -= 1 << 21
    return ((pc >> 12)+imm)*4096+((d >> 10) & 0xfff)


def build_hooks(out):
    obj = out/"parallel2_hooks.o"
    native_obj = out/"native_hooks.o"
    run("xcrun", "clang", "-arch", "arm64", "-c", ROOT/"parallel2_hooks.S", "-o", obj)
    run("xcrun", "clang", "-arch", "arm64", "-DNATIVE_HARNESS", "-c",
        ROOT/"parallel2_hooks.S", "-o", native_obj)
    symbols = symbol_offsets(obj)
    b = bytearray(obj.read_bytes())
    meta = layout(b)
    sec = meta["sections"][("__TEXT", "__text")]
    assert sec["addr"] == 0 and sec["nreloc"] == 0
    size = symbols["_parallel2_hooks_end"]
    assert size == sec["size"] == 0x168
    assert symbols["_parallel2_scheduler"] == 0
    assert symbols["_parallel2_admission"] == 0x100
    payload = bytearray(b[sec["offset"]:sec["offset"]+size])
    nb = native_obj.read_bytes()
    ns = layout(nb)["sections"][("__TEXT", "__text")]
    native = nb[ns["offset"]:ns["offset"]+size]
    nsymbols = symbol_offsets(native_obj)
    mask = set()
    jumps = []
    for name, target in FAR.items():
        at = symbols[name]
        assert nsymbols[name] == at
        assert payload[at:at+12] == bytes(12)
        code = far_jump(CAVE+at, target)
        assert decode_far(CAVE+at, code) == target
        payload[at:at+12] = code
        mask.update(range(at, at+12))
        jumps.append(dict(name=name, pc=hex(CAVE+at),target=hex(target),bytes=code.hex()))
    # Native tests execute identical hook instructions; only their exit adapters
    # differ, and those slots have independently verified far-jump encoding.
    assert all(a == native[i] for i, a in enumerate(b[sec["offset"]:sec["offset"]+size])
               if i not in mask), "Native test hook body differs"
    run("xcrun", "clang", "-arch", "arm64", "-Wall", "-Wextra", "-Werror", "-O2",
        ROOT/"native_harness.c", native_obj, "-o", out/"native-harness")
    tests = json.loads(run(out/"native-harness"))
    (out/"native-test-results.json").write_text(json.dumps(tests,indent=2)+"\n")
    (out/"parallel2-payload.bin").write_bytes(payload)
    # Address-adjust this inspection-only object so objdump displays true cave
    # PCs. This object is never loaded by the app.
    b[sec["offset"]:sec["offset"]+size] = payload
    struct.pack_into("<Q",b,sec["header"]+32,CAVE)
    for segment in meta["segments"]:
        struct.pack_into("<Q",b,segment["header"]+24,segment["vm"]+CAVE)
    symoff,nsyms,_,_ = meta["symbols"]
    for i in range(nsyms):
        at=symoff+16*i
        if b[at+4] & 0xe == 0xe:
            struct.pack_into("<Q",b,at+8,struct.unpack_from("<Q",b,at+8)[0]+CAVE)
    inspection = out/"resolved-hooks-inspection.o"
    inspection.write_bytes(b)
    dis = run("xcrun","llvm-objdump","-d",inspection)
    assert "bl\t" not in dis and "blr\t" not in dis, "Cave must remain leaf-only"
    (out/"resolved-hooks-disassembly.txt").write_text(dis)
    return payload,symbols,jumps,tests


def build_app(source, dest, changes, expected):
    # Reuse the portable safety boundary: full source/copy inventories, hardlink
    # and symlink checks, exact pre-sign change allowlist, copied-only signing,
    # signature verification and full source-integrity recheck.
    assert expected == portable.SOURCE_SHA256
    result = portable.build(source, dest, "parallel2-experiment", custom_regions=changes)
    return dict(app=str(dest), pre_sign_library_sha256=result["library_sha256_before_signing"],
                signed_library_sha256=result["library_sha256_after_signing"],
                signature_verified=True, source_inventory_unchanged=result["source_inventory_unchanged"],
                changes=result["semantic_regions"])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-app",type=Path,default=Path("/Applications/VideoFusion-macOS.app"))
    ap.add_argument("--output-dir",type=Path,help="New, non-existing output directory with an existing parent")
    ap.add_argument("--build-hooks",action="store_true",help="Compile and run only the native hook tests")
    ap.add_argument("--build-apps",action="store_true")
    ap.add_argument("--no-task-center-patch",action="store_true")
    args=ap.parse_args()
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise portable.Refusal("The native ARM64 harness requires Apple Silicon macOS")
    if args.source_app.is_symlink():
        raise portable.Refusal("Source application root must not be a symlink")
    source=args.source_app.resolve(strict=True);lib=source/REL
    if source.suffix != ".app" or not source.is_dir():
        raise portable.Refusal("Source must be a .app directory")
    info=plistlib.loads((source/"Contents/Info.plist").read_bytes())
    if info.get("CFBundleShortVersionString") != "11.6.0":
        raise portable.Refusal("Only version 11.6.0 is supported")
    portable.inventory(source)
    portable.validate_binary(lib)
    if lib.is_symlink():
        raise portable.Refusal("Patch library must not be a symlink")
    out=None
    if args.output_dir is not None:
        if args.output_dir.is_symlink() or os.path.lexists(args.output_dir):
            raise portable.Refusal("Output directory already exists or is a symlink")
        out=args.output_dir.expanduser().resolve()
        if portable.within(out,source) or portable.within(source,out):
            raise portable.Refusal("Output directory and source must be disjoint")
        if not out.parent.is_dir():
            raise portable.Refusal("Output parent must already exist")
    if (args.build_apps or args.build_hooks) and out is None:
        ap.error("--output-dir is required for --build-hooks or --build-apps")
    import mmap
    with lib.open("rb") as f:
        b=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ);meta=layout(b)
        text=next(s for s in meta["segments"] if s["name"]=="__TEXT")
        first=min(s["addr"] for s in meta["sections"].values() if s["addr"]>0)
        assert text["vm"]==text["fileoff"]==0 and text["initprot"]==5
        assert meta["header_end"]<=CAVE and CAVE+0x168<=first
        assert not any(b[meta["header_end"]:first]),"Header padding is not zero"
        for at,(before,_) in HOOKS.items():assert b[at:at+12]==before,hex(at)
        assert b[UI_OFFSET:UI_OFFSET+4]==UI_BEFORE
        padding=dict(start=hex(meta["header_end"]),end=hex(first),all_zero=True,
                     segment="__TEXT",initprot="r-x",cave_start=hex(CAVE),cave_size=0x168)
        b.close()
    if not (args.build_apps or args.build_hooks):
        print(json.dumps(dict(status="read_only_source_and_patch_sites_validated", source_library_sha256=EXPECTED,
                              cave=padding, app_runtime_tested=False, outputs_created=False)))
        return
    out.mkdir()  # exclusive reservation after validating the complete source plan
    payload,symbols,jumps,tests=build_hooks(out)
    changes=[] if args.no_task_center_patch else [(UI_OFFSET,UI_BEFORE,UI_AFTER)]
    cap_changes=[(CAVE,bytes(len(payload)),bytes(payload))]
    for at,(before,name) in HOOKS.items():
        after=far_jump(at,CAVE+symbols[name]);assert decode_far(at,after)==CAVE+symbols[name]
        cap_changes.append((at,before,after))
    manifest=dict(status="static_and_native_hook_tests_passed_not_app_runtime_tested",
                  source_app=str(source),source_library_sha256=EXPECTED,
                  cave=padding,far_jumps=jumps,native_tests=tests,apps=[],
                  task_center_patch_in_both=not args.no_task_center_patch,
                  concurrency_bound="At most2 active entries in the helper's video queue under its existing single-mutator contract; audio queue unchanged",
                  limitations=["No app launched by this builder; no cold-cache speedup measured",
                               "No vendor lifecycle/runtime acceptance yet",
                               "Forced video requests at capacity now remain pending until a completion-driven retry",
                               "Original queue mutation is assumed serialized; no cross-thread lock added",
                               "No pure-audio loudness change in this variant"])
    if args.build_apps:
        manifest["apps"].append(build_app(source,out/"Jianying-11.6.0-UIBaseline.app",changes,EXPECTED))
        manifest["apps"].append(build_app(source,out/"Jianying-11.6.0-Parallel2.app",changes+cap_changes,EXPECTED))
        manifest["status"]="two_isolated_apps_built_and_signatures_verified_not_launched"
        for name in ["UIBaseline","Parallel2"]:
            target=out/f"Jianying-11.6.0-{name}.app"/REL
            text=""
            for start,stop in [(0xc00b7f0,0xc00b884),(0xc00be64,0xc00be98)]:
                text+=run("xcrun","llvm-objdump","-d",f"--start-address={hex(start)}",
                          f"--stop-address={hex(stop)}",target)
            (out/f"{name}-hook-site-disassembly.txt").write_text(text)
    (out/"parallel2-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(dict(status=manifest["status"],tests=tests,
                          manifest=str(out/"parallel2-manifest.json"),apps=[x["app"] for x in manifest["apps"]])))


if __name__=="__main__":
    try:
        main()
    except (portable.Refusal, AssertionError, OSError, ValueError, RuntimeError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        sys.exit(1)
