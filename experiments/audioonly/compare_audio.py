#!/usr/bin/env python3
"""Compare two native audio exports without modifying either input.

Requires ffmpeg and ffprobe on PATH. Decode to float PCM at a common 48 kHz
for comparison; preserve channel count and require equal reported layouts.
No sample alignment or gain correction is used to declare equivalence.
"""
import argparse
import array
import json
import math
import pathlib
import subprocess
import sys
import tempfile


def probe(path):
    response = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_streams",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    streams = json.loads(response.stdout)["streams"]
    if len(streams) != 1:
        raise ValueError("Expected a first audio stream in each input")
    s = streams[0]
    return {k: s.get(k) for k in (
        "codec_name", "channels", "channel_layout", "sample_rate", "duration"
    )}


def decoder(path, error_log):
    return subprocess.Popen([
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
        "-vn", "-sn", "-dn", "-ar", "48000", "-c:a", "pcm_f32le",
        "-f", "f32le", "pipe:1",
    ], stdout=subprocess.PIPE, stderr=error_log)


def compare(reference, candidate, tolerance):
    profiles = [probe(reference), probe(candidate)]
    if profiles[0]["channels"] != profiles[1]["channels"]:
        return {"equivalent": False, "reason": "different_channel_counts", "streams": profiles}
    channels = profiles[0]["channels"]
    if not channels or not isinstance(channels, int):
        raise ValueError("Unknown channel count")
    layouts = [s["channel_layout"] for s in profiles]
    layouts_known_equal = bool(layouts[0]) and layouts[0] == layouts[1]
    if layouts[0] and layouts[1] and layouts[0] != layouts[1]:
        return {"equivalent": False, "reason": "different_channel_layouts", "streams": profiles}
    # A corrupt stream can produce more diagnostics than a pipe can hold.
    # Give each child its own temporary file, drain PCM normally, and retain
    # only a bounded diagnostic tail in the eventual error message.
    error_logs = [tempfile.TemporaryFile(), tempfile.TemporaryFile()]
    processes = []
    count_x = count_y = paired = 0
    xx = yy = xy = difference_squared = maximum_error = 0.0
    finite = True
    try:
        for path, error_log in zip((reference, candidate), error_logs):
            processes.append(decoder(path, error_log))
        while True:
            blocks = [p.stdout.read(4 * channels * 8192) for p in processes]
            if not any(blocks):
                break
            if any(len(block) % (4 * channels) for block in blocks):
                raise ValueError("Truncated decoded PCM frame")
            values = []
            for block in blocks:
                samples = array.array("f")
                samples.frombytes(block)
                if sys.byteorder != "little":
                    samples.byteswap()
                values.append(samples)
            count_x += len(values[0])
            count_y += len(values[1])
            for x, y in zip(*values):
                if not math.isfinite(x) or not math.isfinite(y):
                    finite = False
                    continue
                xx += x * x
                yy += y * y
                xy += x * y
                error = x - y
                difference_squared += error * error
                maximum_error = max(maximum_error, abs(error))
                paired += 1
        statuses = [p.wait() for p in processes]
        if any(statuses):
            errors = []
            for error_log in error_logs:
                size = error_log.seek(0, 2)
                error_log.seek(max(0, size - 8192))
                errors.append(error_log.read(8192).decode(errors="replace"))
            raise RuntimeError("Audio decode failed (last 8192 bytes per decoder): " + " | ".join(errors))
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            if p.stdout is not None:
                p.stdout.close()
        for error_log in error_logs:
            error_log.close()
    relative_error = math.sqrt(difference_squared / max(xx, 1e-24))
    gain = xy / xx if xx else None
    fitted_residual = math.sqrt(max(0.0, yy - xy * xy / xx) / max(xx, 1e-24)) if xx else None
    equivalent = finite and paired > 0 and count_x == count_y and layouts_known_equal and relative_error <= tolerance
    return {
        "kind": "native_export_audio_pcm_comparison",
        "equivalent": equivalent,
        "streams": profiles,
        "layout_known_equal": layouts_known_equal,
        "decoded_sample_rate": 48000,
        "reference_frames": count_x // channels,
        "candidate_frames": count_y // channels,
        "paired_scalar_samples": paired,
        "all_samples_finite": finite,
        "relative_rms_error": relative_error,
        "maximum_absolute_sample_error": maximum_error,
        "required_relative_error": tolerance,
        "diagnostic_candidate_gain": gain,
        "diagnostic_gain_fitted_relative_error": fitted_residual,
        "acceptance_uses_gain_or_time_alignment": False,
        "human_listening_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=pathlib.Path)
    parser.add_argument("candidate", type=pathlib.Path)
    parser.add_argument("--max-relative-error", type=float, default=1e-5)
    args = parser.parse_args()
    if not math.isfinite(args.max_relative_error) or args.max_relative_error < 0:
        parser.error("Tolerance must be finite and non-negative")
    result = compare(args.reference, args.candidate, args.max_relative_error)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["equivalent"] else 2)


if __name__ == "__main__":
    main()
