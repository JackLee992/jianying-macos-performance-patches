# Bounded two-job video-compound experiment

Status: **experimental; native two-job preparation observed, no measured speedup**. A matched copied-app ABBA run on one independent native fixture completed both precombine/loudness operations, but averaged 268.886 seconds versus the serial baseline 267.869 seconds. A later native 20m55 export passed full audio/video decoding; save/reopen retained the four cache files and both completed loudness states. Single-row cancellation preserved the sibling's progress and a later explicit retry completed. See [EVIDENCE.md](../../EVIDENCE.md) for cache/topology/timing boundaries and remaining gates. The builder performs static checks, executes an ARM64 hook harness, clones two separate apps, signs them and verifies their signatures. It never launches an app, restarts a process, opens a project, changes installed software or deletes a cache. The offline checks alone do not establish vendor-runtime correctness or speed.

**Known unfixed UI adaptation gap:** the shared helper's progress callback can write one emitted task's progress into each captured row without a task-identity check. A similar missing guard exists in the inspected state/result callback, so fixing percentages alone would be insufficient. The ordinary serial scheduling assumption is not preserved by our two-active-job cap; displayed rows can mirror progress, and state attribution is not proven. This is a gap in this experiment, not a Qt concurrency limitation or a blanket vendor-bug claim. Two physical renders are independently confirmed, but per-row progress/state is not authoritative for exact completion. The published candidate contains no guard fix, and native-runtime validation of that correction is not established. Keep serial scheduling as the practical default; see the [bounded callback evidence](../../EVIDENCE.md#parallel2-row-callback-identity-gap-not-fixed).

Requirements: Apple Silicon macOS, existing Xcode command-line tools, Python3. No downloads or injected libraries. The exact original `libVECreator.dylib` SHA-256 must be `6a7854189fe4b4c5e9b74441122ce62ce637c10780287fe6079b2e13d293ac33`. A different build is refused even if its displayed version is 11.6.0.

```sh
python3 experiments/parallel2/build_parallel2.py --source-app /Applications/VideoFusion-macOS.app
python3 experiments/parallel2/build_parallel2.py --source-app /Applications/VideoFusion-macOS.app --build-hooks --output-dir ./parallel2-hook-test
python3 experiments/parallel2/build_parallel2.py --source-app /Applications/VideoFusion-macOS.app --build-apps --output-dir ./parallel2-build
```

Run these from the repository root. The first command is a read-only source/hash/layout/site plan and creates nothing. The second compiles and runs only the native ARM64 hook harness. The third produces `Jianying-11.6.0-UIBaseline.app` and `Jianying-11.6.0-Parallel2.app`. The output directory must not already exist, its parent must exist, and it must be disjoint from the source app. Existing outputs, symlink escapes, incompatible version/architecture/hash, hardlinked copies and unexpected copy changes are refused using the same portable inventory/signing safety boundary as the main CLI. Default planning and hook-only tests never sign or launch an application. Do not use Python `-O`; the builder refuses optimized mode so its verification assertions remain active. Both include the same four-byte TaskCenter redraw change, preserve original identifiers/entitlements/runtime flags, and receive ad-hoc library and bundle signatures. Use `--no-task-center-patch` only to create a separate pair with that change absent from both. App binaries, build outputs, private project files and runtime caches do not belong in the public source repository.

## Mechanics

Two original 12-byte instruction sequences become ADRP/ADD/BR detours through caller-saved x16. A direct B cannot reach the header cave from these sites because the displacement exceeds 128 MiB. The builder decodes each new far jump back to its exact expected target.

1. At `0xc00b818`, the original loop's current-entry active check moves into a leaf hook at `0x4000`. For video tasks, it counts all nonzero active bytes in the helper's video vector at self+0x78. At 2 it returns through the original scheduler epilogue (`0xc00b85c`). Below 2 it skips an active current entry via the original iterator-advance instruction (`0xc00b80c`), or reaches the original readiness call (`0xc00b824`). Audio tasks replay the original return-if-active behavior.
2. At `0xc00be74`, immediately before the original active-byte store, the leaf admission hook at `0x4100` recounts the video queue. At 2, or if a reentrant preflight already activated this same task, it reaches the original false-return/canary/epilogue at `0xc00bf64`. Otherwise it performs the original active=true store, places state3 in w9, and resumes at the original state store `0xc00be80`.

The hooks make no calls and allocate no frame. They do not change SP, x19–x29, LR, any original readiness call, or original C++ call return PCs. Normal task completion/failure/cancellation still uses the original native code, clears active, removes the task, resolves its future and invokes the scheduler. The scheduler still starts at most one task per invocation and tail-calls the native starter, so it does not resume a stale vector iterator after a synchronous callback. Enqueue events and completion callbacks refill available slots; the patch does not add a busy loop or broaden dependency readiness.

The cave is 360 bytes of verified all-zero padding in executable, non-writable `__TEXT`, between the end of the Mach-O load commands (`0x30c8`) and first section (`0x254a8`). It does not replace a declared section, grow a segment, alter unwind metadata or add a loaded library. Before signing, every byte outside the declared patch ranges is compared against the original. After signing, patch bytes and the installed source hash are verified again. Signing changes the copied Mach-O signature data and the copied bundle seal.

## Bound and force-request semantics

The bound applies to ACTIVE entries in this helper's VIDEO queue under the existing single-mutator queue contract, starting from a valid state with no more than2 active entries. It is not a global cap on audio jobs, VideoToolbox sessions, encoder workers, unrelated effects or other helper instances. The original vector and byte flags have no cross-thread lock; this patch does not make concurrent mutation of them thread-safe.

The central admission hook also covers the native force/direct-start path: the only direct `doTask(task)` callers found in the original `__text` are scheduler tail-call `0xc00b880` and force call `0xc009dd0`. The only `doTask(task,sequence)` caller found is the asynchronous continuation at `0xc019a50`, after the initial active reservation. These are bounded native branch-reference results; arbitrary external function-pointer invocation is not proven absent.

At capacity, a force video request now remains pending. `exportCombination` enqueues the task and establishes its future before trying either scheduler or force start; its force call ignores the starter's return value. At the admission site the preflight temporary references have already been released and no per-file mutex has yet been taken. The existing false-return path performs the stack-canary check and normal register restoration without falsely completing the pending future. The active jobs' native `taskDone` callbacks call `doFirstTask` (`0xc00d98c`) and provide the retry. Force completion timing therefore changes deliberately, while the task's dependency checks and eventual native completion path remain intact. The active jobs must still actually finish or cancel for this retry to happen.

## Verification and runtime observation

`native_harness.c` executes the same assembled leaf bodies on the host ARM64 CPU. The build compares those instruction bytes with the app payload, excluding only the independently verified far-exit adapters. Exhaustive active masks and current entries test cap admission, skipping, same-task reentry, audio behavior and non-1 active bytes. Lifecycle model cases cover dependency-blocked heads, pending force requests, failure/cancel refill, duplicate active requests, synchronous completion/removal and two completion callbacks. This model checks the integration assumptions; it does not execute Jianying's C++ task engine.

For controlled runtime comparison, save the current project before any app switch, preserve originals and their caches, use independent disposable projects/cache roots with the same inputs, and cold-start each test separately. Keep the UI-only baseline and concurrency candidate at the same signing/UI settings. Record cache-job identities, launch/export/completion times, process footprint and output correctness. A 2-job observation needs TWO distinct compound identities with overlapping execution, corroborated by two distinct `LvveSubDraftHelper::doTask...runFunctor` worker stacks and/or their separate growing output families. A video and its alpha sibling are one job. The TaskCenter total processing count includes pending work and does not prove active concurrency. If overlap is not established, do not claim a two-job throughput measurement.

Validation should include native full export and decoding, cancellation with 2 active jobs, error completion, reopening the saved test project and checking media/cache associations. Compare rendered video/audio content as well as elapsed time. Stop the experiment on wrong output, unexpected repeated regeneration, crash, or sustained memory pressure; keep all such evidence. No pure-audio loudness modification is included in this variant.


## Cancellation boundary before runtime use

Two active jobs can expose shared helper cancellation state that was harmless
with one ordinary active job. A same-helper sibling must not be canceled,
failed, left pending forever, or have its completion future stranded when
one task is canceled. Native hook-model tests do not establish this vendor
engine behavior. Runtime acceptance must include this scenario before any
production recommendation. Stop on unexpected sibling cancellation or recovery
behavior; retain the official application and original cache state.

One native single-row cancellation plus later retry has now passed on the independent fixture: the canceled output disappeared, its sibling continued through 22 observed growth samples and completed, then the explicitly retried target regenerated and completed. This does not establish cancel-all, immediate overlapping retry, worker-exit acknowledgement, failure recovery or full content equivalence. An active reservation can clear before a renderer has stopped; two active entries is not a strict bound on all draining renderers. Together with the ABBA no-speedup result, the candidate remains experimental and serial remains the practical default.
