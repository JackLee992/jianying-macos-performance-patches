# Version-locked macOS performance experiments

This repository contains independently written patch tooling and research for Jianying 11.6.0 on macOS ARM64. Each patch has its own evidence status. Inclusion in the repository does not establish correctness, safety for production, or a performance improvement.

## Baseline and patch isolation

- Preserve the installed application, its vendor signature, original projects, source media, and existing derived caches.
- Build only a separate application copy. Keep the official application available for rollback.
- Lock the original `Contents/Frameworks/libVECreator.dylib` to SHA-256 `6a7854189fe4b4c5e9b74441122ce62ce637c10780287fe6079b2e13d293ac33`; validate architecture, expected instruction bytes, and all insertion regions before writing.
- The narrow task-center experiment replaces the completion callback tail branch at file offset `0x5f4df0c`, bytes `289bff17`, with `c0035fd6` (`ret`). Other refresh paths remain. Completion rows can remain stale until reopening the popup.
- Compare a copied, ad-hoc-signed application containing that task-center patch against an identically prepared copy with one additional experimental patch. Test concurrency and audio-input changes separately before testing any combination.
- Local task-center smoke and export observations do not prove faster rendering. A configuration workaround for a remembered export directory is separate from the machine-code patch.

## Two-task scheduler candidate

The original ordinary helper starts at most one new task per invocation and returns upon encountering an active queue entry. This is not proof of a global application-wide maximum of one: audio and video queues differ, and direct callers exist.

A candidate should preserve the existing dependency check, active-state transitions, native work dispatch, cancellation, task completion, queue ownership, and future lifetime. Count active entries across the complete video queue before admitting another task; skip existing active entries when looking for an eligible task. Keep the audio queue unchanged. One new start per invocation is sufficient for the first experiment; enqueue and completion callbacks must provide the opportunities to fill available slots.

Prefer leaf-only ARM64 detours that return to original code before any native call. Preserve the original stack frame, callee-saved registers, unwind behavior, stack canary, and return contract. Do not call potentially throwing C++ functions from a new unregistered unwind frame. Every branch destination, overwritten instruction, code-cave boundary, and executable mapping needs verification.

A central admission hook can cover direct callers and reentrant callbacks only after proving that a rejected start leaves its queued task and future valid and that later completion-driven scheduling can retry it. It must not report cancellation, failure, or successful completion for a deferred task. Its return path must not skip cleanup. An unlocked active-count check is not a cross-thread synchronization guarantee; establish the execution-thread assumption or retain that limitation explicitly.

Required pre-runtime cases: empty queue; one and two active tasks; active entries later in the queue; blocked dependencies before ready tasks; duplicate requests; audio requests; direct caller behavior; synchronous completion; cancellation and failure. Static or emulated tests validate control-flow invariants, not native application reliability.

### Candidate review, 2026-10-18

The constructed candidate uses leaf detours at `0xc00b818` and `0xc00be74`, with a 360-byte payload at `0x4000` in verified zero-filled executable header padding. Review confirmed intended original return destinations, no new call frame or native calls in the cave, preserved original readiness and tail-call paths, and admission before the active-state store. Capacity deferral returns through the original stack-canary check and epilogue without completing or removing the queued task. The inspected direct caller ignores the return value; completion of an active task drives the next scheduling attempt.

The native ARM64 hook harness passed 14,377 checks on a review rerun. These combine actual hook instructions and a modeled lifecycle; they do not execute the vendor engine's lifecycle. Both copied libraries matched their signed manifest hashes and patch bytes, the candidate passed deep strict signature verification, and the original library hash remained unchanged.

Decision: proceed to isolated native testing. Production acceptance and speedup remain unestablished. In particular, the helper's shared cancellation state and completion-time `taskTryStop` behavior require testing with two real tasks. A sibling task stalling or being cancelled unexpectedly is a candidate failure, even if the active-count harness passes.

## Audio-input candidate

The native loudness manager already analyzes an input file using its audio measurement path. A faster standalone audio meter does not demonstrate a faster application workflow.

The unresolved optimization is a normalization-specific way to obtain the rendered audio of a compound without waiting unnecessarily for its visual cache. Establish the precise request and completion chain before proposing an active patch. Preserve effective range, trimming, speed, mixing, volume, effects, channel layout, cache identity, cancellation, and ownership. Keep visual compound cache behavior unchanged. Do not substitute the original source file for a rendered compound or fake algorithm completion.

If no suitably scoped call site is established, ship the findings as research only. A missing safe candidate is an unresolved deliverable, not a successful audio optimization.

## Application-derived-cache A/B procedure

1. Save the current project and verify a metadata snapshot before normal application shutdown. Record and preserve symlinks and existing caches.
2. Construct a separate native benchmark project with two independent long compounds and matching source media, ranges, effects, timeline settings, and normalization settings. A compound's video and alpha outputs are one job, not two jobs.
3. Give the benchmark its own physical `Resources`, combination-cache, and loudness directories. Read-only source media may be shared. Reject any cache mutation whose resolved path reaches an original project or a symlink target outside the benchmark-owned root.
4. Save and reopen the fixture natively to validate it, then freeze the stopped fixture. Before every trial restore that same fixture into the same canonical benchmark path and rotate benchmark-owned derived-cache directories into trial archives. Do not recursively purge original projects or global caches.
5. Verify that all relevant derived outputs are absent and that native tasks do not reuse external or global loudness results. If misses cannot be established, label cache state unknown or warm. A new folder name alone does not change internal cache identities.
6. Run baseline/candidate/candidate/baseline with a fresh derived-cache reset for each trial. A single baseline/candidate pair is preliminary. Keep popup visibility, local output folder, export settings, source location, and application preparation consistent.
7. Time the same native trigger through both jobs completing with finalized readable outputs. Record per-job starts and completions, elapsed time, memory footprint, CPU and thermal observations, errors, and cache-hit evidence.
8. Prove concurrent work using distinct task identities or overlapping monotonic output growth from distinct compound output groups. UI task rows alone, or video and alpha files from one compound, do not establish two independent active jobs.

Here, cold means application-derived-cache cold. OS page cache is uncontrolled and must be disclosed. Fresh independent projects and preserved source media avoid destructive system-wide cache purges.

## Acceptance and reporting

- Confirm the loaded library matches the intended candidate and verify the installed application remains unchanged.
- Verify native completion, cancellation, retry, save, reopen, and export behavior. Fully decode produced audio and video and compare duration, dimensions, stream structure, and sampled pictures with the control.
- For an audio-input candidate, compare native loudness parameters and decoded audio behavior against the control with representative trim, mixing, and speed changes. Matching one loudness number alone does not prove audio equivalence; sampled picture checks do not prove complete visual equivalence.
- Report all trial times, not just the fastest result. Compute observed speedup from comparable runs and state the small sample size. If there is no improvement or a regression, report it directly.
- Maintain separate status fields for research, offline construction, static verification, runtime smoke tests, cancellation/recovery, controlled A/B, and export validation. Do not collapse them into one success label.
- Never infer a twofold speedup from a concurrency limit of two. Do not claim universal reliability from one local fixture.

## Portable public tooling

The builder accepts explicit source-app, destination-app, and patch-selection arguments. It refuses in-place modification, destinations inside the source bundle, existing destinations, incompatible binaries, overlapping patch regions, and symlink escapes. Validate the complete patch plan before copying or writing. Support a regular-copy fallback when clone copying is unavailable. Compare pre-signing changes against an exact allowlist, then sign only the copied modified components and bundle while preserving existing signature metadata and entitlements. Verify the resulting copy and recheck source hashes. Signing necessarily changes signature data; report semantic patch changes separately.

The builder must not launch applications, terminate processes, alter TCC, weaken OS protections, or silently modify user preferences. Rollback consists of quitting the candidate and reopening the preserved official application. Project/cache compatibility and backups remain necessary even when the application copy is disposable.

Publish only independently written scripts, manifests, assembly, tests, sanitized evidence summaries, and documentation. Exclude vendor bundles/libraries, media, projects, keys, account identifiers, preference files, raw logs, raw private paths, and bulk disassembly. Stage files by explicit allowlist and inspect the staged tree before publishing. License only original repository material; the repository grants no rights to the vendor application.
