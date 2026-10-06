#!/usr/bin/env python3
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import validar_media as vm


class CoreMediaValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.media_root = self.root / "data/editorial/media"
        self.media_root.mkdir(parents=True)

        self.old_root = vm.ROOT
        self.old_media_root = vm.MEDIA_ROOT
        vm.ROOT = self.root
        vm.MEDIA_ROOT = self.media_root.resolve()
        self.addCleanup(self._restore_roots)

    def _restore_roots(self):
        vm.ROOT = self.old_root
        vm.MEDIA_ROOT = self.old_media_root

    def _write(self, name="asset.bin", content=b"valid media bytes"):
        path = self.media_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        relative = path.relative_to(self.root).as_posix()
        digest = hashlib.sha256(content).hexdigest()
        return path, relative, digest

    def _media(self, relative, digest, **extra):
        data = {
            "media_path": relative,
            "media_type": "image/png",
            "media_method": "official_image",
            "media_content_sha256": digest,
            "media_resolution_fingerprint": "f" * 64,
        }
        data.update(extra)
        return data

    def error_codes(self, result):
        return {error.code for error in result.errors}

    def test_valid_file_passes_core_integrity(self):
        _path, relative, digest = self._write()
        result = vm.validate_media(self._media(relative, digest))

        self.assertTrue(result.valid)
        self.assertEqual(result.status, vm.STATUS_VALID)
        self.assertEqual(result.content_sha256, digest)
        self.assertEqual(result.bytes_size, len(b"valid media bytes"))
        self.assertEqual(result.validation_version, vm.VALIDATION_VERSION)
        self.assertEqual(result.detected_type, "")
        self.assertIsNone(result.width)
        self.assertIsNone(result.height)
        self.assertFalse(result.errors)
        self.assertEqual(result.checks[-1].name, "sha256")
        self.assertEqual(result.checks[-1].status, vm.CHECK_PASS)

    def test_same_file_same_result(self):
        _path, relative, digest = self._write()
        media = self._media(relative, digest)
        self.assertEqual(vm.validate_media(media), vm.validate_media(media))

    def test_non_mapping_input_fails_closed(self):
        result = vm.validate_media(None)
        self.assertFalse(result.valid)
        self.assertIn(vm.ERROR_INPUT_INVALID, self.error_codes(result))

    def test_missing_media_path_fails_closed(self):
        result = vm.validate_media({"media_content_sha256": "a" * 64})
        self.assertIn(vm.ERROR_PATH_MISSING, self.error_codes(result))

    def test_absolute_path_is_rejected(self):
        path, _relative, digest = self._write()
        result = vm.validate_media(self._media(str(path.resolve()), digest))
        self.assertIn(vm.ERROR_PATH_INVALID, self.error_codes(result))

    def test_parent_traversal_is_rejected(self):
        result = vm.validate_media(self._media("data/editorial/media/../escape.png", "a" * 64))
        self.assertIn(vm.ERROR_PATH_INVALID, self.error_codes(result))

    def test_path_outside_media_root_is_rejected(self):
        outside = self.root / "elsewhere/asset.png"
        outside.parent.mkdir(parents=True)
        outside.write_bytes(b"x")
        digest = hashlib.sha256(b"x").hexdigest()
        relative = outside.relative_to(self.root).as_posix()
        result = vm.validate_media(self._media(relative, digest))
        self.assertIn(vm.ERROR_PATH_INVALID, self.error_codes(result))

    def test_missing_file_is_rejected(self):
        result = vm.validate_media(
            self._media("data/editorial/media/missing.png", "a" * 64)
        )
        self.assertIn(vm.ERROR_FILE_MISSING, self.error_codes(result))

    def test_directory_is_not_a_regular_file(self):
        directory = self.media_root / "directory"
        directory.mkdir()
        relative = directory.relative_to(self.root).as_posix()
        result = vm.validate_media(self._media(relative, "a" * 64))
        self.assertIn(vm.ERROR_FILE_NOT_REGULAR, self.error_codes(result))

    def test_empty_file_is_rejected(self):
        path = self.media_root / "empty.png"
        path.write_bytes(b"")
        relative = path.relative_to(self.root).as_posix()
        result = vm.validate_media(self._media(relative, hashlib.sha256(b"").hexdigest()))
        self.assertIn(vm.ERROR_FILE_EMPTY, self.error_codes(result))

    def test_file_over_maximum_is_rejected_without_hashing(self):
        path = self.media_root / "large.bin"
        with path.open("wb") as handle:
            handle.truncate(vm.MAX_MEDIA_BYTES + 1)
        relative = path.relative_to(self.root).as_posix()
        result = vm.validate_media(self._media(relative, "a" * 64))
        self.assertIn(vm.ERROR_FILE_TOO_LARGE, self.error_codes(result))
        self.assertEqual(result.bytes_size, vm.MAX_MEDIA_BYTES + 1)

    def test_missing_expected_hash_is_rejected(self):
        _path, relative, _digest = self._write()
        result = vm.validate_media(self._media(relative, ""))
        self.assertIn(vm.ERROR_HASH_MISSING, self.error_codes(result))

    def test_malformed_expected_hash_is_rejected(self):
        _path, relative, _digest = self._write()
        result = vm.validate_media(self._media(relative, "not-a-sha256"))
        self.assertIn(vm.ERROR_HASH_INVALID, self.error_codes(result))

    def test_hash_mismatch_is_rejected_and_actual_hash_reported(self):
        _path, relative, digest = self._write(content=b"original")
        result = vm.validate_media(self._media(relative, "0" * 64))
        self.assertIn(vm.ERROR_HASH_MISMATCH, self.error_codes(result))
        self.assertEqual(result.content_sha256, digest)

    def test_hash_comparison_accepts_uppercase_expected_hash(self):
        _path, relative, digest = self._write()
        result = vm.validate_media(self._media(relative, digest.upper()))
        self.assertTrue(result.valid)
        self.assertEqual(result.content_sha256, digest)


if __name__ == "__main__":
    unittest.main()
