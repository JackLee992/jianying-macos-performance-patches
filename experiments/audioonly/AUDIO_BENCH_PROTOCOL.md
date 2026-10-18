# Native detached-audio cold-cache experiment

This characterizes an explicit editing workflow. It does not demonstrate an
implemented transparent audio-only normalization patch.

## Safe setup

Use only independently created test drafts and their fresh cache namespace.
Never delete, rename, or invalidate caches of an original project. Save the
active project before every quit or restart and retain the saved core files.
Use the same app/UI patch in control and experiment so the two-job scheduler
is not accidentally included in the audio comparison.

Start with a 30-second compound, then use the long compound. The meaningful
fixture includes two overlapping audio tracks, a trim, non-unit speed,
unequal track gains, a fade, and one local audio effect. Do not use cloud-only
effects. Record exact sample rate/channel layout and expected timeline length.

## Native operation to inspect

1. In the independent draft, select the video compound and open its native
   context menu. If available, invoke `分离音频` using its observed menu item.
   Do not invent a shortcut or bypass a disabled native control.
2. Record the created audio segment's start/duration, volume, speed, fades,
   effects, channel selection, and linkage to its video. Confirm whether the
   original video is muted by the native operation; otherwise the experiment
   would double the audio.
3. Determine whether the new segment is an audio compound retaining the draft
   reference or a regular file-based extraction from `_video.mp4`. A command
   that first waits for video precombine has not removed the cold-cache cost.
4. With normalization OFF, export audio from both the original compound control
   and the native detached-audio variant to lossless WAV in fresh output folders.
   Compare PCM length, channel layout, sample alignment, and waveform. Use
   `compare_audio.py` for a streaming difference check. A gain fit is diagnostic;
   it cannot turn a changed gain into an equivalence pass.
5. Only after equivalence passes, enable the same native target loudness on the
   corresponding original-video and detached-audio segment in fresh independent
   cold drafts. Keep the original video's audio muted in the detached variant.
6. Measure from the user action to completed audio preparation/normalization,
   and separately to final video export. Include detachment/preparation cost in
   the total. Record files generated, native task states, CPU/memory, and errors.
7. Repeat with reversed run order and fresh project cache namespaces. Compare
   medians only when at least three successful comparable runs exist.

## Fail and limitation conditions

- If detachment is disabled or requires the original video cache first, record
  the workflow as unavailable or no cold-cache benefit. Do not fabricate an
  audio material or edit encrypted draft data to force it.
- If the native split leaves live audio/render dependencies on the visual
  compound, report them. Audio-only normalization speed does not by itself
  prove that final export is faster.
- Check cancellation, reopening a saved draft, cache reuse after reopening,
  cache invalidation after an inner audio edit, and final export. A lower
  task duration without these checks is only a throughput observation.
- PCM or timeline mismatches stop the equivalence claim even if loudness LUFS
  is similar. Listen to beginning/end, overlaps, fades, speed changes, and
  effects as a separate human acceptance step.
