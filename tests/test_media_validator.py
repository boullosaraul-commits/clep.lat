#!/usr/bin/env python3
import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

import validar_media as vm


class MediaValidatorTests(unittest.TestCase):
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

    def _png(self, width=1200, height=1500, trailer=True):
        content = (
            b"\x89PNG\r\n\x1a\n"
            + b"\x00\x00\x00\x0dIHDR"
            + struct.pack(">II", width, height)
            + b"\x08\x02\x00\x00\x00"
            + b"\x00\x00\x00\x00"
        )
        if trailer:
            content += b"\x00\x00\x00\x00IEND\xaeB`\x82"
        return content

    def _svg(self, width=1200, height=1500, extra=""):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">{extra}<rect width="10" height="10"/></svg>'
        ).encode("utf-8")

    def _write(self, name="asset.png", content=None):
        if content is None:
            content = self._png()
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

    def test_valid_png_passes_full_validation(self):
        content = self._png(1200, 1500)
        _path, relative, digest = self._write(content=content)
        result = vm.validate_media(self._media(relative, digest))

        self.assertTrue(result.valid)
        self.assertEqual(result.status, vm.STATUS_VALID)
        self.assertEqual(result.content_sha256, digest)
        self.assertEqual(result.bytes_size, len(content))
        self.assertEqual(result.validation_version, vm.VALIDATION_VERSION)
        self.assertEqual(result.detected_type, "image/png")
        self.assertEqual((result.width, result.height), (1200, 1500))
        self.assertFalse(result.errors)

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
        outside.write_bytes(self._png())
        digest = hashlib.sha256(outside.read_bytes()).hexdigest()
        relative = outside.relative_to(self.root).as_posix()
        result = vm.validate_media(self._media(relative, digest))
        self.assertIn(vm.ERROR_PATH_INVALID, self.error_codes(result))

    def test_missing_file_is_rejected(self):
        result = vm.validate_media(self._media("data/editorial/media/missing.png", "a" * 64))
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

    def test_missing_expected_hash_is_rejected(self):
        _path, relative, _digest = self._write()
        result = vm.validate_media(self._media(relative, ""))
        self.assertIn(vm.ERROR_HASH_MISSING, self.error_codes(result))

    def test_malformed_expected_hash_is_rejected(self):
        _path, relative, _digest = self._write()
        result = vm.validate_media(self._media(relative, "not-a-sha256"))
        self.assertIn(vm.ERROR_HASH_INVALID, self.error_codes(result))

    def test_hash_mismatch_is_rejected_and_actual_hash_reported(self):
        _path, relative, digest = self._write(content=self._png())
        result = vm.validate_media(self._media(relative, "0" * 64))
        self.assertIn(vm.ERROR_HASH_MISMATCH, self.error_codes(result))
        self.assertEqual(result.content_sha256, digest)

    def test_hash_comparison_accepts_uppercase_expected_hash(self):
        _path, relative, digest = self._write()
        result = vm.validate_media(self._media(relative, digest.upper()))
        self.assertTrue(result.valid)

    def test_unknown_bytes_are_rejected_as_unsupported_format(self):
        _path, relative, digest = self._write("asset.bin", b"not an image")
        result = vm.validate_media(self._media(relative, digest, media_type="application/octet-stream"))
        self.assertIn(vm.ERROR_FORMAT_UNSUPPORTED, self.error_codes(result))

    def test_declared_type_must_match_detected_type(self):
        _path, relative, digest = self._write()
        result = vm.validate_media(self._media(relative, digest, media_type="image/jpeg"))
        self.assertIn(vm.ERROR_TYPE_MISMATCH, self.error_codes(result))

    def test_extension_must_match_detected_type(self):
        _path, relative, digest = self._write("asset.jpg", self._png())
        result = vm.validate_media(self._media(relative, digest, media_type="image/png"))
        self.assertIn(vm.ERROR_EXTENSION_MISMATCH, self.error_codes(result))

    def test_truncated_png_is_rejected(self):
        _path, relative, digest = self._write("asset.png", self._png(trailer=False))
        result = vm.validate_media(self._media(relative, digest))
        self.assertIn(vm.ERROR_RASTER_CORRUPT, self.error_codes(result))

    def test_small_remote_raster_is_rejected(self):
        _path, relative, digest = self._write("small.png", self._png(300, 300))
        result = vm.validate_media(self._media(relative, digest))
        self.assertIn(vm.ERROR_DIMENSIONS_TOO_SMALL, self.error_codes(result))

    def test_extreme_dimensions_are_rejected(self):
        _path, relative, digest = self._write("huge.png", self._png(13000, 1500))
        result = vm.validate_media(self._media(relative, digest))
        self.assertIn(vm.ERROR_DIMENSIONS_TOO_LARGE, self.error_codes(result))

    def test_valid_svg_card_passes(self):
        content = self._svg()
        _path, relative, digest = self._write("card.svg", content)
        result = vm.validate_media(
            self._media(
                relative,
                digest,
                media_type="image/svg+xml",
                media_method="deterministic_card",
            )
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.detected_type, "image/svg+xml")
        self.assertEqual((result.width, result.height), (1200, 1500))

    def test_svg_with_script_is_rejected(self):
        content = self._svg(extra="<script>alert(1)</script>")
        _path, relative, digest = self._write("unsafe.svg", content)
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/svg+xml", media_method="deterministic_card")
        )
        self.assertIn(vm.ERROR_SVG_UNSAFE, self.error_codes(result))

    def test_svg_with_remote_href_is_rejected(self):
        content = self._svg(extra='<image href="https://example.org/x.png"/>')
        _path, relative, digest = self._write("remote.svg", content)
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/svg+xml", media_method="deterministic_card")
        )
        self.assertIn(vm.ERROR_SVG_UNSAFE, self.error_codes(result))

    def test_svg_without_dimensions_or_viewbox_is_rejected(self):
        content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
        _path, relative, digest = self._write("nodims.svg", content)
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/svg+xml", media_method="deterministic_card")
        )
        self.assertIn(vm.ERROR_SVG_DIMENSIONS_MISSING, self.error_codes(result))

    def test_svg_can_use_viewbox_for_dimensions(self):
        content = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1500"></svg>'
        _path, relative, digest = self._write("viewbox.svg", content)
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/svg+xml", media_method="deterministic_chart")
        )
        self.assertTrue(result.valid)
        self.assertEqual((result.width, result.height), (1200, 1500))

    def test_chart_must_be_svg(self):
        _path, relative, digest = self._write("chart.png", self._png())
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/png", media_method="deterministic_chart")
        )
        self.assertIn(vm.ERROR_METHOD_TYPE_MISMATCH, self.error_codes(result))

    def test_landing_capture_must_be_png(self):
        content = self._svg()
        _path, relative, digest = self._write("capture.svg", content)
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/svg+xml", media_method="official_landing_capture")
        )
        self.assertIn(vm.ERROR_METHOD_TYPE_MISMATCH, self.error_codes(result))

    def test_landing_capture_requires_exact_dimensions(self):
        _path, relative, digest = self._write("capture.png", self._png(1200, 1400))
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/png", media_method="official_landing_capture")
        )
        self.assertIn(vm.ERROR_DIMENSIONS_TOO_SMALL, self.error_codes(result))

    def test_clep_card_requires_exact_dimensions(self):
        content = self._svg(width=1000, height=1000)
        _path, relative, digest = self._write("card.svg", content)
        result = vm.validate_media(
            self._media(relative, digest, media_type="image/svg+xml", media_method="deterministic_card")
        )
        self.assertIn(vm.ERROR_DIMENSIONS_TOO_SMALL, self.error_codes(result))


if __name__ == "__main__":
    unittest.main()
