# Sanitized local evidence, 2026-10-18

Scope: one local macOS ARM64 Jianying 11.6.0 investigation. Raw logs, application binaries, media, drafts, account information and private paths are intentionally excluded.

- A native sample contained 1,326 of 1,597 main-thread samples (83%) under `TaskCenterViewModel::updateTaskList(bool)`, with 10.4 GB physical footprint. This identifies sampled UI work, not the unique initiating callback or a vendor-confirmed universal defect.
- The four-byte candidate skipped the delayed completion callback's final task-list refresh. A separate copied, ad-hoc-signed app loaded its patched library. One 300-second compound completed pre-rendering and normalization; a later 905-sample main-thread capture contained zero updater-stack occurrences. Workload and timing differed from the initial sample: this is smoke evidence, not a causal A/B comparison.
- After choosing an accessible local export directory through the native application UI, the copied app exported an approximately 247.97-second H.264/AAC film at 1080×1920, 30 fps. Full native audio/video decoding passed; 12 sampled pictures had low-resolution mean absolute differences of 0–0.860 / 255 against the official-app export. This is not full-frame equivalence or human audio review. Native cancellation returned to the editor and left no aborted final output. The saved project reopened; long-term reliability remains unknown.
- The initial blocked export stack ended in directory enumeration/open. Official and copied export-code regions were identical. A native output-directory change resolved the local symptom; the underlying OS access-stall cause was not established.
- Fifteen observed long compound output groups completed at 141–144-second intervals, mean 142 seconds. Each represented about 627.9 seconds of content. This was historical activity across a working project, not a verified list of tasks required by one cold export. A short final timeline can still reference much longer compounds.
- A short 8 GiB SSD test measured about 797 MB/s sequential read and 446 MB/s average write, with late write windows around 330–360 MB/s. This was approximately 34 seconds of I/O, not a sustained thermal or health test. Results do not generalize to other drives or prove all runtime I/O was fast.
- Pure-audio FFmpeg loudness measurement of two approximately 628-second sources took about 2.05 and 2.06 seconds. It bypassed the application's compound effects, mixing, caching and scheduler. It is not an end-to-end Jianying optimization result.

No controlled same-fixture, application-derived-cache-cold baseline/candidate/candidate/baseline trial has been completed. No rendering speedup, safe concurrency key, general audio-only-input patch or universal hardware recommendation is claimed.


## Portable experiment integration

The public two-job builder's read-only plan passed against the exact source hash and verified all original hook sites plus executable zero padding. Its compiled ARM64 leaf-hook harness passed 14,377 checks, including its bounded lifecycle model. No application was built or launched by this packaging verification. These checks do not execute the vendor C++ engine or establish sibling-cancellation behavior, cross-thread safety, exports, or speedup.

The public read-only audio-route checker matched all eight instruction sites and expected branch targets on the same source. The PCM comparison utility accepted identical generated stereo WAV audio and rejected a half-gain variant; fitted gain remained diagnostic. This verifies utility behavior, not the native detached-audio workflow or a transparent audio-only normalization patch.

The public main CLI also built a real copied taskcenter app locally: full copy verification, the exact four-byte semantic diff, ad-hoc signatures and strict verification passed; the source application's inventory remained unchanged. This specific generated copy was not launched. The malformed-decoder regression emits over 2 MB to stderr before stdout and returns a bounded failure rather than hanging; 14 utility tests passed on two local Python installations.
