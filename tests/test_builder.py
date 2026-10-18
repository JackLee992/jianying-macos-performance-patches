import contextlib
import io
import os
from pathlib import Path
import plistlib
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jianying_patch as jp

class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'Official.app'
        self.output = self.root / 'Candidate.app'
        self.lib = self.source / jp.LIBRARY
        self.lib.parent.mkdir(parents=True)
        self.lib.write_bytes(bytes.fromhex('cffaedfe') + struct.pack('<I', 0x100000c) + bytes(range(56)))
        (self.source / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString': '11.6.0'}))
        (self.source / 'Contents/data').write_bytes(b'preserve this data')
        self.region = (32, self.lib.read_bytes()[32:36], b'EDIT')
        self.sha = patch.object(jp, 'SOURCE_SHA256', jp.digest(self.lib))
        self.regions = patch.object(jp, 'PATCHES', {'taskcenter': [self.region]})
        self.sha.start()
        self.regions.start()
        self.before = jp.inventory(self.source)
        self.signed = []

    def tearDown(self):
        self.sha.stop()
        self.regions.stop()
        self.tmp.cleanup()

    @staticmethod
    def copy(source, output):
        shutil.copytree(source, output, symlinks=True, dirs_exist_ok=True)

    def build(self, selection='taskcenter', copier=None, signer=None):
        return jp.build(self.source, self.output, selection, copier or self.copy,
                        signer or (lambda target: self.signed.append(target)))

    def test_plan_is_read_only(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = jp.main(['--source-app', str(self.source), '--output-app', str(self.output), '--patch', 'taskcenter'])
        self.assertEqual(code, 0)
        self.assertIn('read_only_plan_validated', stream.getvalue())
        self.assertFalse(self.output.exists())
        self.assertEqual(jp.inventory(self.source), self.before)

    def test_only_selected_bytes_change_and_source_stays_unchanged(self):
        result = self.build()
        self.assertTrue(result['source_inventory_unchanged'])
        self.assertEqual(jp.inventory(self.source), self.before)
        expected = bytearray(self.lib.read_bytes())
        expected[32:36] = b'EDIT'
        self.assertEqual((self.output / jp.LIBRARY).read_bytes(), expected)
        self.assertEqual(self.signed, [self.output])

    def test_control_is_copied_and_signed_without_semantic_patch(self):
        self.build('none')
        self.assertEqual(jp.inventory(self.output), self.before)
        self.assertEqual(self.signed, [self.output])

    def test_nested_same_and_existing_outputs_are_rejected(self):
        for output in [self.source, self.source / 'Nested.app', self.root]:
            with self.subTest(output=output), self.assertRaises(jp.Refusal):
                jp.plan(self.source, output, 'none')
        self.output.mkdir()
        sentinel = self.output / 'keep'
        sentinel.write_text('mine')
        with self.assertRaises(jp.Refusal):
            self.build()
        self.assertEqual(sentinel.read_text(), 'mine')

    def test_escape_symlinks_and_dangling_output_are_rejected(self):
        external = self.root / 'private'
        external.write_text('keep')
        (self.source / 'Contents/escape').symlink_to(external)
        with self.assertRaises(jp.Refusal):
            self.build()
        self.assertFalse(self.output.exists())
        (self.source / 'Contents/escape').unlink()
        self.output.symlink_to(self.root / 'missing.app')
        with self.assertRaises(jp.Refusal):
            self.build()

    def test_relative_internal_symlink_preserved(self):
        (self.source / 'Contents/link').symlink_to('data')
        self.build()
        self.assertTrue((self.output / 'Contents/link').is_symlink())
        self.assertEqual((self.output / 'Contents/link').read_bytes(), b'preserve this data')

    def test_changed_binary_version_architecture_and_expected_bytes_rejected(self):
        with patch.object(jp, 'SOURCE_SHA256', '0' * 64), self.assertRaises(jp.Refusal):
            self.build()
        with patch.object(jp, 'PATCHES', {'taskcenter': [(32, b'NOPE', b'EDIT')]}), self.assertRaises(jp.Refusal):
            self.build()
        with patch.object(jp, 'PATCHES', {'taskcenter': [self.region, self.region]}), self.assertRaises(jp.Refusal):
            self.build()
        data = self.lib.read_bytes()
        self.lib.write_bytes(data[:4] + struct.pack('<I', 7) + data[8:])
        with patch.object(jp, 'SOURCE_SHA256', jp.digest(self.lib)), self.assertRaises(jp.Refusal):
            self.build()
        self.lib.write_bytes(data)
        (self.source / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString': '99.0'}))
        with self.assertRaises(jp.Refusal):
            self.build()
        self.assertFalse(self.output.exists())

    def test_extra_copy_change_prevents_signing(self):
        def damaged_copy(source, output):
            self.copy(source, output)
            (output / 'Contents/data').write_bytes(b'corruption')
        with self.assertRaises(jp.Refusal):
            self.build(copier=damaged_copy)
        self.assertFalse(self.signed)
        self.assertEqual(jp.inventory(self.source), self.before)

    def test_hardlinked_copy_cannot_modify_source(self):
        def hardlinks(source, output):
            shutil.copytree(source, output, copy_function=os.link, dirs_exist_ok=True)
        with self.assertRaises(jp.Refusal):
            self.build(copier=hardlinks)
        self.assertFalse(self.signed)
        self.assertEqual(jp.inventory(self.source), self.before)

    def test_unplanned_library_byte_is_rejected(self):
        self.copy(self.source, self.output)
        target = self.output / jp.LIBRARY
        data = bytearray(target.read_bytes())
        data[32:36] = b'EDIT'
        data[-1] ^= 1
        target.write_bytes(data)
        with self.assertRaises(jp.Refusal):
            jp.assert_patch_only(self.lib, target, [self.region])

    def test_custom_experiment_regions_use_same_copy_safety_boundary(self):
        regions = [self.region, (40, self.lib.read_bytes()[40:44], b'MORE')]
        result = jp.build(self.source, self.output, 'custom-experiment', copier=self.copy,
                          signer=lambda target: self.signed.append(target), custom_regions=regions)
        data = (self.output / jp.LIBRARY).read_bytes()
        self.assertEqual(data[32:36], b'EDIT')
        self.assertEqual(data[40:44], b'MORE')
        self.assertEqual(len(result['semantic_regions']), 2)
        self.assertEqual(jp.inventory(self.source), self.before)

    def test_source_changes_during_signing_fail_final_integrity_check(self):
        def bad_signer(output):
            (self.source / 'Contents/data').write_bytes(b'external change')
        with self.assertRaises(jp.Refusal):
            self.build(signer=bad_signer)

if __name__ == '__main__':
    unittest.main()
