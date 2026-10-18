# Normalization-specific audio source optimization

Status: **research only; no native behavior patch produced or activated**.
The transparent optimization requested by the user is not implemented by
changing an output filename or by timing an external loudness meter.

## Target and bounded observations

Investigated target: Jianying Pro 11.6.0, ARM64, `libVECreator.dylib`, SHA-256
`6a7854189fe4b4c5e9b74441122ce62ce637c10780287fe6079b2e13d293ac33`.
Addresses below are unslid VM addresses. The supplied checker validates the
Mach-O mapping, source hash, and eight relevant instructions without editing
anything. No installed app, project, preference, or existing cache was changed.

1. `AudioAlgorithmParamProvider::getAlgorithmParams` calls
   `SegmentAlgorithmOverlayHelper::initAudioContext` at `0xb743b28`.
2. The latter calls `makeDefaultAlgorithmParam<SegmentVideo>` at `0xb7681d8`.
   That default copies an existing `MaterialVideo` path when available. For a
   non-integrated compound with an empty material path, its fallback calls
   `LvveSubDraftHelper::makeOutputPath` at `0xb767c80`; the boolean is derived
   from the segment type, so a normal video compound selects the video path.
   This function constructs a filename. It does not enqueue a render.
3. `SegmentAlgorithmCollector::canBeScheduled` checks
   `VideoAlgHelper::needExportVideoCombination(segment, false)` at
   `0xb75e454`, conditional on `enable_combination_pre_export_optimize`.
   The check gates the collector before its audio group can be scheduled.
   No normalization-specific algorithm type guard occurs around this check.
4. `SegmentAlgorithmLoudnessNorm::arrangeNode` creates a `LoudnessNode` and
   supplies its input. It does not itself construct a video export node.
   `LoudnessManager::GetLoudnessParamFromVE` selects an audio track at
   `0xbf15f34`, creates `lvve::LoudnessManager` at `0xbf16004`, and invokes
   its native scan interface. The measurement stage is already audio focused.
5. The separate `LvveSubDraftHelper::exportAudioCombination` entry exists at
   `0xc00a5cc`. Native automatic updates to an actual `SegmentAudio` compound
   use the helper's audio queue. Its existence is not proof that changing a
   video compound's normalization input will automatically use that queue.

These are static observations. They do not establish current server flags,
which route every test project takes at runtime, or an achieved speedup.

## Why the simple patches are invalid

- Replacing the default video-cache filename with the audio-cache filename
  leaves audio generation, readiness, completion, and cancellation absent.
  The meter would receive a missing file or stale cache.
- Bypassing `canBeScheduled` affects the whole compound collector, including
  video and other audio algorithms. It can expose consumers to absent caches.
- A raw source file is not generally equivalent to a compound's audio. Nested
  tracks, timing, speed, volume, fades, effects, channel selection, and mixing
  can change the measured signal.
- Marking an algorithm completed or reusing another input's cache key would
  conceal a semantic error and is not an optimization.

## Requirements for a transparent native patch

The patch must select only the normalization consumer, enqueue the native
compound audio export, and retain a valid asynchronous dependency until its
future resolves. It must preserve cancellation, failed-export propagation,
segment revision identity, cache-key/range mapping, track/channel selection,
and the exact signal presented to the original meter. Native precombine may
remove or transform outer effects for later application; equivalence must
therefore be measured before claiming that the helper's audio export matches
the previous normalization input. The ordinary visual cache route must remain
available for playback and final video export.

## Testable native workflow experiment

The independent-project `分离音频` operation is a separate workflow candidate,
not this missing transparent binary patch. `canSeparateAudio` at `0x3bf6dec`
checks for a video segment with audio and has no explicit compound exclusion
in the bounded function. See `AUDIO_BENCH_PROTOCOL.md`.

In one native cold-derived-cache test this menu created an audio clip in under
one observed second. Enabling normalization on it finalized only an audio
combination file at 4.628 seconds and a loudness record at 5.252 seconds, with
no video/alpha outputs. The native UI reported the -23 LUFS target completed.
This establishes this fixture's audio-only route; it is not a transparent
patch, a repeated audio A/B trial or a final-video-export benchmark.

The semantic gate did not pass. With normalization OFF in both arms, full
native WAV exports before/after detaching the first compound had equal PCM16
44.1 kHz two-channel durations (1255.224308 seconds), but the comparator found
relative RMS sample difference 0.0106621 and maximum absolute error 0.0337854.
Neither WAV declared channel layout. Diagnostic fitted gain 0.999499 does not
erase the sample difference. Intermediate encoding is a possible explanation,
not an established cause. No alignment, gain correction or looser threshold
was used to force acceptance.

An original-rate 44.1 kHz PCM check localized all differences to the detached
first compound: its relative RMS error was 0.01568135 and maximum difference
1,122 PCM16 LSB. Every sample in the untouched second portion was bit-identical.
The whole-file original-rate relative error 0.01066240 agrees with the 48 kHz
comparison, ruling out comparator resampling as the explanation for this
observed difference. Encoding/effect-transfer causes remain unestablished.

Keep this workflow experimental. Normalized-output comparison, actual channel
mapping, trim/speed/fade/gain/effect/mix semantics, human listening, final video
correctness and repeated whole-workflow timing remain gates. Do not silently
detach audio in another user's project or claim a roughly 26x final-export
speedup from the separate preparation-stage observations.

## Public packaging boundary

The checker and this report contain no original media, project data, cache
contents, app binaries, account information, or machine-specific home paths.
Raw disassembly and local runtime files should stay in the private lab.


## Comparator failure handling

`compare_audio.py` keeps each decoder's diagnostics in a separate temporary
file while streaming PCM. A corrupt stream cannot block PCM draining by
filling an unread stderr pipe. On decode failure only the final 8,192 bytes
per decoder are included in the error; temporary files are closed and removed,
and inputs are never rewritten. A subprocess regression emits more than
2 MB of corrupt-frame diagnostics before stdout and must fail promptly.
