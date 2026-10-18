"""Exercise decoder pipe behavior with a real diagnostic-flooding child process."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'experiments/audioonly/compare_audio.py'

@unittest.skipUnless(os.name == 'posix', 'Executable fixture wrappers use POSIX shebangs')
class AudioComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='audio-pipe-regression-')
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.wrapper('ffprobe', '''import json
print(json.dumps({'streams': [{'codec_name': 'pcm_f32le', 'channels': 2,
                               'channel_layout': 'stereo', 'sample_rate': '48000'}]}))
''')
        self.wrapper('ffmpeg', '''import os
from pathlib import Path
import struct
import sys
payload = Path(sys.argv[sys.argv.index('-i') + 1]).read_bytes()
if payload == b'malformed-stream':
    # More than any normal pipe capacity, before producing stdout. A reader
    # draining stdout while leaving stderr=PIPE unread deadlocks here.
    chunk = b'corrupt audio frame; ' * 4096
    for _ in range(32):
        os.write(2, chunk)
    sys.exit(7)
scale = 0.5 if payload == b'half-gain' else 1.0
sys.stdout.buffer.write(struct.pack('<32f', *([0.25 * scale, -0.25 * scale] * 16)))
''')
        self.environment = dict(os.environ)
        self.environment['PATH'] = str(self.bin) + os.pathsep + self.environment.get('PATH', '')

    def tearDown(self):
        self.tmp.cleanup()

    def wrapper(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def compare(self, left, right):
        return subprocess.run([sys.executable, str(SCRIPT), str(left), str(right)],
                              env=self.environment, capture_output=True, text=True, timeout=8)

    def test_malformed_input_large_stderr_fails_promptly_and_keeps_inputs(self):
        source = self.root / 'malformed.audio'
        source.write_bytes(b'malformed-stream')
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = self.compare(source, source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Audio decode failed', result.stderr)
        self.assertIn('corrupt audio frame', result.stderr)
        self.assertLess(len(result.stderr), 25000, 'Diagnostic output must remain bounded')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_identical_audio_passes_and_gain_change_is_not_equivalence(self):
        reference, changed = self.root / 'reference.audio', self.root / 'changed.audio'
        reference.write_bytes(b'original')
        changed.write_bytes(b'half-gain')
        same = self.compare(reference, reference)
        different = self.compare(reference, changed)
        self.assertEqual(same.returncode, 0, same.stderr)
        self.assertTrue(json.loads(same.stdout)['equivalent'])
        self.assertEqual(different.returncode, 2, different.stderr)
        report = json.loads(different.stdout)
        self.assertFalse(report['equivalent'])
        self.assertFalse(report['acceptance_uses_gain_or_time_alignment'])
        self.assertAlmostEqual(report['diagnostic_candidate_gain'], 0.5)

if __name__ == '__main__':
    unittest.main()
