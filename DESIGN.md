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

The initial decision allowed isolated native testing. Subsequent local results below supersede that initial runtime-pending state; they do not establish general production compatibility.

### Runtime outcome and default policy

A matched application-derived-cache-cold ABBA test completed both long compounds and both native loudness operations. Serial baseline times were 267.928 and 267.809 seconds; candidate times were 268.667 and 269.104 seconds. Means were 267.8685 and 268.8855 seconds respectively. The candidate took 1.017 seconds longer (0.38%) in these observations: **no measured speedup**. Two observations per arm do not establish a universal regression. Each candidate run had 131 intervals with overlapping growth of two independent output groups, so the lack of speedup was not a failure to start overlapping work. See [EVIDENCE.md](EVIDENCE.md) for the fixture, trigger and measurement boundaries.

The practical default remains the official serial scheduler. The separate two-job builder remains an explicit experiment; it must not become an automatic operator-skill action, a default combined patch, or an advertised performance preset on this evidence. The task-center patch has a separate UI-refresh purpose and is not proof of encoding acceleration.

A later candidate run completed a native 1,255.233333-second export with 1080 x 1920, 30 fps H.264 video and 44.1 kHz AAC audio. Full audio/video decoding returned success. After saving, normal quit and reopening, four video/alpha cache paths, sizes and modification times were unchanged over the observation window, and both inspected compounds showed native normalization completed at -23 LUFS. This supports local export/reopen and cache-preservation observations, not full visual/audio equivalence, verification of every effect, or a migration benchmark. The roughly 2.202-second observed reopening of this small test draft is not a general project-opening performance result.

In a separate local cancel-one/later-retry exercise, the native task-row cancel action was followed by the targeted partial output disappearing by the next sample, approximately 0.826 seconds later. It remained absent until explicit retry. The sibling continued growing through 22 observations and finalized its video, alpha and loudness result. Retry created a fresh target output; its video finalized 133.587 seconds after retry and loudness 134.319 seconds after retry. Both final output groups then remained stable for more than 80 observations and both native loudness states completed at -23 LUFS. Turning the loudness checkbox off earlier had not cancelled the shared preparation with remaining consumers; that action must not be described as the successful task cancellation.

This validates observed output cancellation, sibling continuation and later retry for one local case. There was no worker-exit acknowledgement or proof that every internal task had stopped immediately. Successful later export does not establish independent cancellation of all task types or absence of stranded futures in every dependency state. Shared helper cancellation and completion-time `taskTryStop` behavior remain relevant to wider reliability testing. Unexpected sibling failure, indefinite pending state or repeated regeneration is a failed case, not something to conceal with a later successful retry.

Separate diagnostic profiles show the dominant rendering queues waiting in `TEVTEncodeUnit::processInputStream`'s mutex path in about 66.5% of single-job samples and 82.2% / 82.0% of two-job samples. Their dominant encoder queues spend about 98.8% versus 99.5% / 99.2% of samples in `VTCompressionSessionEncodeFrame`, principally CoreMedia semaphore waiting. This supports encoding-path backpressure propagating upstream. Neither the mutex owner nor its sharing scope was established; hardware/media-engine saturation was not proved. The two main-thread profiles did not show task-list-updater stacks. A new lock-removal or larger-concurrency patch is not justified by these observations.

## Audio-input candidate

The native loudness manager already analyzes an input file using its audio measurement path. A faster standalone audio meter does not demonstrate a faster application workflow.

The unresolved optimization is a normalization-specific way to obtain the rendered audio of a compound without waiting unnecessarily for its visual cache. Establish the precise request and completion chain before proposing an active patch. Preserve effective range, trimming, speed, mixing, volume, effects, channel layout, cache identity, cancellation, and ownership. Keep visual compound cache behavior unchanged. Do not substitute the original source file for a rendered compound or fake algorithm completion.

If no suitably scoped call site is established, ship the findings as research only. A missing safe candidate is an unresolved deliverable, not a successful audio optimization.

The native separate-audio workflow is distinct from a transparent binary patch. In one independent application-derived-cache-cold test, the native detachment command completed in under one second. Enabling normalization on the detached audio produced an approximately 15 MB `_audio.m4a` at 4.628 seconds and a loudness-result file at 5.252 seconds, with native -23 LUFS completion. No video/alpha cache output was observed. This establishes an audio-only preparation route for that case. The roughly 134-second direct-video normalization observation is a stage-specific comparison, not a matched repeated whole-workflow benchmark. Do not advertise a 26-fold final-export speedup; total detachment, preparation and final export costs require separate measurement.

The normalization-OFF control against normalization-OFF detached workflow did **not** pass strict audio equivalence. Both full native WAV exports reported 44.1 kHz, two-channel PCM s16le and equal 1,255.224308-second durations; decoded comparison at 48 kHz produced 60,250,767 frames for each. Nevertheless, relative RMS waveform error was 0.0106621, maximum absolute sample error 0.033785 and diagnostic fitted gain 0.999499. Reported channel layouts were unknown, so layout equivalence was also unestablished. Equal duration, channels and near-unity fitted gain do not override the waveform difference. A lossy intermediate is a hypothesis, not an established cause.

Decision: keep this explicit editing workflow at research/conditional-experiment status and do not recommend or apply it automatically. Locate the difference in the detached versus untouched portions; verify the intermediate codec and channel semantics; then compare corresponding normalization-ON outputs with the same target and representative trims, mixing, gains, fades, speed and effects. Confirm no duplicate audible tracks, cancellation/reopen behavior and dependency invalidation after an audio edit. A later ON/ON result must be reported alongside the failed OFF/OFF result rather than erasing it. Human listening is a separate acceptance step. If the user knowingly accepts a lossy or otherwise changed-signal workflow, label that tradeoff explicitly; it remains distinct from a semantics-preserving optimization. The transparent audio-input binary-patch status remains research only.

## Next architecture: preserve work through project recovery

The highest-value next deliverable is a portable project/cache inspection and recovery workflow, with serial task scheduling retained. Its objective is to prevent verified reusable work from being lost during migration, import, opening and repeated recovery. It is a proposed workflow, not an implemented opening-speed patch. The app's metadata migration, timeline parsing, media resolution, derived-cache validation and background task execution need separate evidence.

### Read-only inventory and stage diagnosis

Start with an explicit project root and application version. Produce a private local inventory of project metadata, timelines, subdrafts, associated local key files, source dependencies, derived video/alpha groups and loudness results. Use `lstat` and resolved paths to distinguish owned physical directories from shared symlink targets. Record sizes and modification times first; compute content hashes where needed to verify a snapshot or investigate a mismatch, rather than repeatedly reading all media by default. Do not decrypt opaque project data, upload it, or infer missing references from guessed schemas. Preserve unknown fields and mark opaque or incomplete dependency coverage explicitly.

Represent a cache group as its observed identity, output members, state, provenance and resolved storage ownership. States should distinguish absent, growing/incomplete, finalized/readable, native reuse observed, native invalidation observed and unknown. File existence, matching size, or a video without its required alpha sibling is not a cache-hit proof. Keep native input identity and editing semantics separate from an external file's checksum.

Record independently: request-to-visible/editor-ready, missing-resource resolution, background preparation-to-ready, and export-to-final-file. Classify a stall using the current native state plus bounded thread and file-progress observations. Do not count every background task as time spent parsing the project, or call an event-loop wait a deadlock. The first acceptance case should be an already saved project reopening without unnecessary regeneration; complex imported/migrated drafts require their own baseline.

### Coherent snapshots and controlled restoration

Create a coherent recovery point after native save and normal application shutdown. Snapshot the complete draft metadata set, including hidden sidecars, encrypted timeline data and its matching local key material, subdraft definitions and cache-reference metadata. Keep these private. Preserve owned valid caches and record shared-cache topology; copying a symlink does not create a backup of its target. A backup is incomplete until required referenced storage is either separately verified or deliberately materialized into a new owned copy without changing its original. Writable hardlinks must not connect a restored test copy to original metadata or caches.

Restore into a new explicitly owned destination, keeping the original intact. Preserve the internally coherent identity set; do not manually rewrite project IDs, cache hashes, algorithm status or encrypted fields to force a match. Resolve registration and media relinking through the available native import/open/recovery flow. If that flow refuses the duplicate identity, changes format or requires migration, record the condition and use the application's supported behavior; do not silently edit its global project registry. Avoid opening conflicting copies simultaneously.

Then validate native opening, missing-resource status, representative timeline positions and paired cache reuse. Confirm whether unchanged edits retain previously complete outputs and normalization state across save/reopen. Compare before/after ownership and cache inventories and observe whether new expensive work was scheduled. Cache preservation is a successful recovery result even if no lower-level computation becomes faster; quantify avoided rebuilding only in a matched, independently restored test.

### Work reduction and subsequent engine research

Only after observing repeated preparation of equivalent content should the workflow propose consolidation or narrower compound ranges. Compare effective source/time ranges, speed, transforms, cropping, mixed audio, gains, effects, algorithm state and output specifications. Identical source filenames or visually similar frames do not establish equivalent caches. Use native edits in a separate draft and validate the resulting output; do not alias arbitrary cache files or merge entries merely because names or hashes look related.

For encoding research, first establish session and mutex ownership, lock lifetime across VideoToolbox submission, and intermediate video/alpha pixel-format and conversion costs. Preserve frame ownership, order, backpressure, completion and cancellation. A native setting that reduces resolution or frame rate is a different workload and must not be marketed as an equivalent-quality optimization. No new engine patch is part of this plan without a proven scoped change and its own correctness and A/B evidence.

The portable implementation should therefore separate a read-only inspector, a reviewable snapshot/restore plan, a copy-only executor confined to new owned destinations, and a native-UI verification protocol. None should silently clear caches, alter application safety settings, or enable experimental binary patches. Public reports use sanitized case IDs and aggregated findings; private inventories and recovery keys stay local.

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
