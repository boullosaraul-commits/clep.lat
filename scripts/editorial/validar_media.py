#!/usr/bin/env python3
"""Validador físico determinista de media editorial CLEP.

Paso 5, tandas A+B (5.1–5.9):
- contrato estructurado de validación;
- confinamiento de rutas dentro de data/editorial/media;
- existencia, archivo regular y tamaño;
- integridad SHA-256 contra el hash registrado por adquisición;
- detección real de formato;
- validación raster y SVG;
- coherencia método ↔ tipo;
- dimensiones editoriales mínimas/máximas.

Este módulo no decide qué media usar, no hace red, no repara assets y no
activa fallbacks. Sólo certifica o rechaza material ya adquirido.
"""
from __future__ import annotations

import hashlib
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = (ROOT / "data/editorial/media").resolve()
VALIDATION_VERSION = 2
MAX_MEDIA_BYTES = 12 * 1024 * 1024

STATUS_VALID = "VALID"
STATUS_INVALID = "INVALID"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_NOT_RUN = "NOT_RUN"

ERROR_INPUT_INVALID = "MEDIA_VALIDATION_INPUT_INVALID"
ERROR_PATH_MISSING = "MEDIA_PATH_MISSING"
ERROR_PATH_INVALID = "MEDIA_PATH_INVALID"
ERROR_FILE_MISSING = "MEDIA_FILE_MISSING"
ERROR_FILE_NOT_REGULAR = "MEDIA_FILE_NOT_REGULAR"
ERROR_FILE_EMPTY = "MEDIA_FILE_EMPTY"
ERROR_FILE_TOO_LARGE = "MEDIA_FILE_TOO_LARGE"
ERROR_FILE_STAT_FAILED = "MEDIA_FILE_STAT_FAILED"
ERROR_FILE_READ_FAILED = "MEDIA_FILE_READ_FAILED"
ERROR_HASH_MISSING = "MEDIA_HASH_MISSING"
ERROR_HASH_INVALID = "MEDIA_HASH_INVALID"
ERROR_HASH_MISMATCH = "MEDIA_HASH_MISMATCH"
ERROR_FORMAT_UNSUPPORTED = "MEDIA_FORMAT_UNSUPPORTED"
ERROR_TYPE_MISMATCH = "MEDIA_TYPE_MISMATCH"
ERROR_EXTENSION_MISMATCH = "MEDIA_EXTENSION_MISMATCH"
ERROR_RASTER_CORRUPT = "MEDIA_RASTER_CORRUPT"
ERROR_DIMENSIONS_TOO_SMALL = "MEDIA_DIMENSIONS_TOO_SMALL"
ERROR_DIMENSIONS_TOO_LARGE = "MEDIA_DIMENSIONS_TOO_LARGE"
ERROR_SVG_INVALID = "MEDIA_SVG_INVALID"
ERROR_SVG_UNSAFE = "MEDIA_SVG_UNSAFE"
ERROR_SVG_DIMENSIONS_MISSING = "MEDIA_SVG_DIMENSIONS_MISSING"
ERROR_METHOD_TYPE_MISMATCH = "MEDIA_METHOD_TYPE_MISMATCH"

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_DIMENSION_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)")

SUPPORTED_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
RASTER_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

MIN_RASTER_WIDTH = 600
MIN_RASTER_HEIGHT = 600
MAX_PIXEL_DIMENSION = 12000
CLEP_OWN_WIDTH = 1200
CLEP_OWN_HEIGHT = 1500
CAPTURE_WIDTH = 1200
CAPTURE_HEIGHT = 1500

METHOD_OFFICIAL_IMAGE = "official_image"
METHOD_EXPLICIT_COVER = "explicit_cover"
METHOD_EXPLICIT_THUMBNAIL = "explicit_thumbnail"
METHOD_OFFICIAL_LANDING_CAPTURE = "official_landing_capture"
METHOD_DETERMINISTIC_CHART = "deterministic_chart"
METHOD_DETERMINISTIC_CARD = "deterministic_card"

REMOTE_RASTER_METHODS = {
    METHOD_OFFICIAL_IMAGE,
    METHOD_EXPLICIT_COVER,
    METHOD_EXPLICIT_THUMBNAIL,
}

UNSAFE_SVG_TAGS = {"script", "foreignObject", "iframe", "object", "embed"}
URL_ATTRS = {"href", "{http://www.w3.org/1999/xlink}href"}


@dataclass(frozen=True)
class MediaValidationCheck:
    name: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MediaValidationIssue:
    code: str
    detail: str
    field: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MediaValidationResult:
    status: str
    media_path: str
    declared_type: str
    detected_type: str
    content_sha256: str
    bytes_size: int
    width: int | None
    height: int | None
    validation_version: int
    resolution_fingerprint: str
    media_method: str
    checks: tuple[MediaValidationCheck, ...] = field(default_factory=tuple)
    errors: tuple[MediaValidationIssue, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return self.status == STATUS_VALID

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checks"] = [check.to_dict() for check in self.checks]
        data["errors"] = [error.to_dict() for error in self.errors]
        return data


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _issue(code: str, detail: str, field_name: str = "") -> MediaValidationIssue:
    return MediaValidationIssue(code=code, detail=detail, field=field_name)


def _result(
    media: Mapping[str, Any],
    *,
    checks: list[MediaValidationCheck],
    errors: list[MediaValidationIssue],
    content_sha256: str = "",
    bytes_size: int = 0,
    detected_type: str = "",
    width: int | None = None,
    height: int | None = None,
) -> MediaValidationResult:
    return MediaValidationResult(
        status=STATUS_INVALID if errors else STATUS_VALID,
        media_path=_clean(media.get("media_path")),
        declared_type=_normalize_media_type(
            _clean(media.get("media_type") or media.get("media_type_declared"))
        ),
        detected_type=detected_type,
        content_sha256=content_sha256,
        bytes_size=bytes_size,
        width=width,
        height=height,
        validation_version=VALIDATION_VERSION,
        resolution_fingerprint=_clean(
            media.get("media_resolution_fingerprint")
            or media.get("resolution_fingerprint")
        ),
        media_method=_clean(media.get("media_method") or media.get("acquisition_method")),
        checks=tuple(checks),
        errors=tuple(errors),
    )


def _normalize_media_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


def _safe_target(relative_path: str) -> Path:
    """Resuelve una ruta sólo si queda realmente confinada en MEDIA_ROOT."""
    relative = Path(relative_path)
    if not relative_path or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("ruta vacía, absoluta o con traversal")

    target = (ROOT / relative).resolve()
    if target == MEDIA_ROOT or MEDIA_ROOT not in target.parents:
        raise ValueError("ruta fuera de data/editorial/media")
    return target


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            count += len(chunk)
    return digest.hexdigest(), count


def _detect_type(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    head = content[:4096].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return ""
        if re.search(r"<\s*svg\b", text, re.IGNORECASE):
            return "image/svg+xml"
    return ""


def _png_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 24 or content[12:16] != b"IHDR":
        raise ValueError("PNG sin IHDR válido")
    width, height = struct.unpack(">II", content[16:24])
    if not content.endswith(b"IEND\xaeB`\x82"):
        raise ValueError("PNG truncado o sin IEND")
    return width, height


def _gif_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 10 or not content.startswith((b"GIF87a", b"GIF89a")):
        raise ValueError("GIF inválido")
    width, height = struct.unpack("<HH", content[6:10])
    if not content.endswith(b";"):
        raise ValueError("GIF truncado")
    return width, height


def _jpeg_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 4 or not content.startswith(b"\xff\xd8") or not content.endswith(b"\xff\xd9"):
        raise ValueError("JPEG truncado o inválido")
    pos = 2
    while pos + 4 <= len(content):
        if content[pos] != 0xFF:
            pos += 1
            continue
        while pos < len(content) and content[pos] == 0xFF:
            pos += 1
        if pos >= len(content):
            break
        marker = content[pos]
        pos += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(content):
            break
        seg_len = struct.unpack(">H", content[pos:pos + 2])[0]
        if seg_len < 2 or pos + seg_len > len(content):
            raise ValueError("segmento JPEG inválido")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if seg_len < 7:
                raise ValueError("SOF JPEG inválido")
            height, width = struct.unpack(">HH", content[pos + 3:pos + 7])
            return width, height
        pos += seg_len
    raise ValueError("JPEG sin segmento SOF")


def _webp_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 30 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        raise ValueError("WebP inválido")
    kind = content[12:16]
    if kind == b"VP8X":
        width = 1 + int.from_bytes(content[24:27], "little")
        height = 1 + int.from_bytes(content[27:30], "little")
        return width, height
    if kind == b"VP8 ":
        if len(content) < 30 or content[23:26] != b"\x9d\x01\x2a":
            raise ValueError("VP8 inválido")
        width = struct.unpack("<H", content[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", content[28:30])[0] & 0x3FFF
        return width, height
    if kind == b"VP8L":
        if len(content) < 25 or content[20] != 0x2F:
            raise ValueError("VP8L inválido")
        bits = int.from_bytes(content[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    raise ValueError("subtipo WebP no soportado")


def _raster_dimensions(content: bytes, media_type: str) -> tuple[int, int]:
    if media_type == "image/png":
        return _png_dimensions(content)
    if media_type == "image/jpeg":
        return _jpeg_dimensions(content)
    if media_type == "image/gif":
        return _gif_dimensions(content)
    if media_type == "image/webp":
        return _webp_dimensions(content)
    raise ValueError(f"tipo raster no soportado: {media_type}")


def _svg_dimension(value: str | None) -> int | None:
    if not value:
        return None
    match = _DIMENSION_RE.match(value)
    if not match:
        return None
    number = float(match.group(1))
    if number <= 0:
        return None
    return int(round(number))


def _svg_validate(content: bytes) -> tuple[int, int]:
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"XML SVG inválido: {exc}") from exc

    local_root = root.tag.rsplit("}", 1)[-1]
    if local_root != "svg":
        raise ValueError("raíz XML no es <svg>")

    for element in root.iter():
        local_tag = element.tag.rsplit("}", 1)[-1]
        if local_tag in UNSAFE_SVG_TAGS:
            raise PermissionError(f"elemento SVG no permitido: {local_tag}")
        for attr, raw in element.attrib.items():
            attr_local = attr.rsplit("}", 1)[-1]
            value = str(raw or "").strip()
            if attr in URL_ATTRS or attr_local == "href":
                lowered = value.lower()
                if lowered.startswith(("http://", "https://", "//", "javascript:", "data:text/html")):
                    raise PermissionError(f"referencia externa/no segura en {attr_local}")
            if attr_local == "style" and re.search(r"url\s*\(\s*['\"]?(?:https?:|//|javascript:)", value, re.IGNORECASE):
                raise PermissionError("URL externa/no segura en style")

    width = _svg_dimension(root.attrib.get("width"))
    height = _svg_dimension(root.attrib.get("height"))
    viewbox = _clean(root.attrib.get("viewBox"))
    if (width is None or height is None) and viewbox:
        try:
            parts = [float(x) for x in re.split(r"[ ,]+", viewbox) if x]
        except ValueError as exc:
            raise ValueError("viewBox SVG inválido") from exc
        if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
            raise ValueError("viewBox SVG inválido")
        width = width or int(round(parts[2]))
        height = height or int(round(parts[3]))
    if width is None or height is None:
        raise LookupError("SVG sin dimensiones ni viewBox utilizable")
    return width, height


def _expected_extension(media_type: str) -> set[str]:
    if media_type == "image/jpeg":
        return JPEG_EXTENSIONS
    suffix = SUPPORTED_TYPES.get(media_type)
    return {suffix} if suffix else set()


def _method_type_allowed(method: str, media_type: str) -> bool:
    if method in REMOTE_RASTER_METHODS:
        return media_type in RASTER_TYPES
    if method == METHOD_OFFICIAL_LANDING_CAPTURE:
        return media_type == "image/png"
    if method in {METHOD_DETERMINISTIC_CHART, METHOD_DETERMINISTIC_CARD}:
        return media_type == "image/svg+xml"
    return True


def _dimensions_allowed(method: str, media_type: str, width: int, height: int) -> tuple[bool, str]:
    if width <= 0 or height <= 0:
        return False, "dimensiones no positivas"
    if width > MAX_PIXEL_DIMENSION or height > MAX_PIXEL_DIMENSION:
        return False, f"dimensiones exceden {MAX_PIXEL_DIMENSION}px"
    if method in {METHOD_DETERMINISTIC_CHART, METHOD_DETERMINISTIC_CARD}:
        if (width, height) != (CLEP_OWN_WIDTH, CLEP_OWN_HEIGHT):
            return False, f"asset CLEP propio debe ser {CLEP_OWN_WIDTH}x{CLEP_OWN_HEIGHT}"
        return True, "dimensiones CLEP propias válidas"
    if method == METHOD_OFFICIAL_LANDING_CAPTURE:
        if (width, height) != (CAPTURE_WIDTH, CAPTURE_HEIGHT):
            return False, f"captura oficial debe ser {CAPTURE_WIDTH}x{CAPTURE_HEIGHT}"
        return True, "dimensiones de captura válidas"
    if media_type in RASTER_TYPES:
        if width < MIN_RASTER_WIDTH or height < MIN_RASTER_HEIGHT:
            return False, f"raster menor a {MIN_RASTER_WIDTH}x{MIN_RASTER_HEIGHT}"
    return True, "dimensiones válidas"


def validate_media(media: Mapping[str, Any]) -> MediaValidationResult:
    """Certifica integridad, formato, seguridad y dimensiones sin side effects."""
    if not isinstance(media, Mapping):
        empty: dict[str, Any] = {}
        return _result(
            empty,
            checks=[MediaValidationCheck("input", CHECK_FAIL, "entrada no es un mapping")],
            errors=[_issue(ERROR_INPUT_INVALID, "media debe ser un mapping", "media")],
        )

    checks: list[MediaValidationCheck] = []
    errors: list[MediaValidationIssue] = []
    relative_path = _clean(media.get("media_path"))

    if not relative_path:
        checks.append(MediaValidationCheck("path_safe", CHECK_FAIL, "media_path ausente"))
        errors.append(_issue(ERROR_PATH_MISSING, "media_path es obligatorio", "media_path"))
        return _result(media, checks=checks, errors=errors)

    try:
        target = _safe_target(relative_path)
    except (OSError, ValueError) as exc:
        checks.append(MediaValidationCheck("path_safe", CHECK_FAIL, str(exc)))
        errors.append(_issue(ERROR_PATH_INVALID, str(exc), "media_path"))
        return _result(media, checks=checks, errors=errors)

    checks.append(MediaValidationCheck("path_safe", CHECK_PASS, relative_path))

    if not target.exists():
        checks.append(MediaValidationCheck("exists", CHECK_FAIL, "archivo no existe"))
        errors.append(_issue(ERROR_FILE_MISSING, f"asset no encontrado: {relative_path}", "media_path"))
        return _result(media, checks=checks, errors=errors)
    checks.append(MediaValidationCheck("exists", CHECK_PASS, "archivo existe"))

    if not target.is_file():
        checks.append(MediaValidationCheck("regular_file", CHECK_FAIL, "target no es archivo regular"))
        errors.append(_issue(ERROR_FILE_NOT_REGULAR, f"target no es archivo regular: {relative_path}", "media_path"))
        return _result(media, checks=checks, errors=errors)
    checks.append(MediaValidationCheck("regular_file", CHECK_PASS, "archivo regular"))

    try:
        stat_size = target.stat().st_size
    except OSError as exc:
        checks.append(MediaValidationCheck("size", CHECK_FAIL, f"stat falló: {exc}"))
        errors.append(_issue(ERROR_FILE_STAT_FAILED, f"no se pudo leer tamaño: {exc}", "media_path"))
        return _result(media, checks=checks, errors=errors)

    if stat_size <= 0:
        checks.append(MediaValidationCheck("size", CHECK_FAIL, "archivo vacío"))
        errors.append(_issue(ERROR_FILE_EMPTY, "asset tiene 0 bytes", "media_path"))
        return _result(media, checks=checks, errors=errors, bytes_size=max(0, stat_size))
    if stat_size > MAX_MEDIA_BYTES:
        checks.append(MediaValidationCheck("size", CHECK_FAIL, f"{stat_size} bytes exceden máximo {MAX_MEDIA_BYTES}"))
        errors.append(_issue(ERROR_FILE_TOO_LARGE, f"asset excede máximo de {MAX_MEDIA_BYTES} bytes", "media_path"))
        return _result(media, checks=checks, errors=errors, bytes_size=stat_size)
    checks.append(MediaValidationCheck("size", CHECK_PASS, f"{stat_size} bytes"))

    expected_hash = _clean(media.get("media_content_sha256") or media.get("content_sha256"))
    if not expected_hash:
        checks.append(MediaValidationCheck("sha256", CHECK_FAIL, "hash esperado ausente"))
        errors.append(_issue(ERROR_HASH_MISSING, "media_content_sha256 es obligatorio", "media_content_sha256"))
        return _result(media, checks=checks, errors=errors, bytes_size=stat_size)
    if not _SHA256_RE.fullmatch(expected_hash):
        checks.append(MediaValidationCheck("sha256", CHECK_FAIL, "hash esperado no es SHA-256 hexadecimal"))
        errors.append(_issue(ERROR_HASH_INVALID, "media_content_sha256 debe tener 64 caracteres hexadecimales", "media_content_sha256"))
        return _result(media, checks=checks, errors=errors, bytes_size=stat_size)

    try:
        content = target.read_bytes()
    except OSError as exc:
        checks.append(MediaValidationCheck("sha256", CHECK_FAIL, f"lectura falló: {exc}"))
        errors.append(_issue(ERROR_FILE_READ_FAILED, f"no se pudieron leer bytes del asset: {exc}", "media_path"))
        return _result(media, checks=checks, errors=errors, bytes_size=stat_size)

    actual_size = len(content)
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_size != stat_size:
        checks.append(MediaValidationCheck("size_consistency", CHECK_FAIL, f"stat={stat_size}, leído={actual_size}"))
        errors.append(_issue(ERROR_FILE_READ_FAILED, "el tamaño cambió durante la validación", "media_path"))
        return _result(media, checks=checks, errors=errors, content_sha256=actual_hash, bytes_size=actual_size)
    checks.append(MediaValidationCheck("size_consistency", CHECK_PASS, f"{actual_size} bytes"))

    if actual_hash.lower() != expected_hash.lower():
        checks.append(MediaValidationCheck("sha256", CHECK_FAIL, "hash real distinto del registrado"))
        errors.append(_issue(ERROR_HASH_MISMATCH, f"esperado={expected_hash.lower()} actual={actual_hash}", "media_content_sha256"))
        return _result(media, checks=checks, errors=errors, content_sha256=actual_hash, bytes_size=actual_size)
    checks.append(MediaValidationCheck("sha256", CHECK_PASS, actual_hash))

    detected_type = _detect_type(content)
    if not detected_type:
        checks.append(MediaValidationCheck("format", CHECK_FAIL, "formato no soportado o no reconocible"))
        errors.append(_issue(ERROR_FORMAT_UNSUPPORTED, "asset no es PNG/JPEG/WebP/GIF/SVG reconocido", "media_path"))
        return _result(media, checks=checks, errors=errors, content_sha256=actual_hash, bytes_size=actual_size)
    checks.append(MediaValidationCheck("format", CHECK_PASS, detected_type))

    declared_type = _normalize_media_type(_clean(media.get("media_type") or media.get("media_type_declared")))
    if not declared_type:
        checks.append(MediaValidationCheck("declared_type", CHECK_FAIL, "media_type declarado ausente"))
        errors.append(_issue(ERROR_TYPE_MISMATCH, "media_type declarado es obligatorio", "media_type"))
    elif declared_type != detected_type:
        checks.append(MediaValidationCheck("declared_type", CHECK_FAIL, f"declarado={declared_type} detectado={detected_type}"))
        errors.append(_issue(ERROR_TYPE_MISMATCH, f"tipo declarado {declared_type} no coincide con detectado {detected_type}", "media_type"))
    else:
        checks.append(MediaValidationCheck("declared_type", CHECK_PASS, declared_type))

    suffix = target.suffix.lower()
    expected_exts = _expected_extension(detected_type)
    if suffix not in expected_exts:
        checks.append(MediaValidationCheck("extension", CHECK_FAIL, f"extensión {suffix or '<vacía>'} incompatible con {detected_type}"))
        errors.append(_issue(ERROR_EXTENSION_MISMATCH, f"extensión {suffix or '<vacía>'} incompatible con {detected_type}", "media_path"))
    else:
        checks.append(MediaValidationCheck("extension", CHECK_PASS, suffix))

    width: int | None = None
    height: int | None = None
    if detected_type in RASTER_TYPES:
        try:
            width, height = _raster_dimensions(content, detected_type)
        except ValueError as exc:
            checks.append(MediaValidationCheck("raster", CHECK_FAIL, str(exc)))
            errors.append(_issue(ERROR_RASTER_CORRUPT, str(exc), "media_path"))
        else:
            checks.append(MediaValidationCheck("raster", CHECK_PASS, f"{width}x{height}"))
    elif detected_type == "image/svg+xml":
        try:
            width, height = _svg_validate(content)
        except PermissionError as exc:
            checks.append(MediaValidationCheck("svg", CHECK_FAIL, str(exc)))
            errors.append(_issue(ERROR_SVG_UNSAFE, str(exc), "media_path"))
        except LookupError as exc:
            checks.append(MediaValidationCheck("svg", CHECK_FAIL, str(exc)))
            errors.append(_issue(ERROR_SVG_DIMENSIONS_MISSING, str(exc), "media_path"))
        except ValueError as exc:
            checks.append(MediaValidationCheck("svg", CHECK_FAIL, str(exc)))
            errors.append(_issue(ERROR_SVG_INVALID, str(exc), "media_path"))
        else:
            checks.append(MediaValidationCheck("svg", CHECK_PASS, f"{width}x{height}"))

    method = _clean(media.get("media_method") or media.get("acquisition_method"))
    if method and not _method_type_allowed(method, detected_type):
        checks.append(MediaValidationCheck("method_type", CHECK_FAIL, f"{method} no admite {detected_type}"))
        errors.append(_issue(ERROR_METHOD_TYPE_MISMATCH, f"método {method} incompatible con {detected_type}", "media_method"))
    else:
        checks.append(MediaValidationCheck("method_type", CHECK_PASS, f"{method or '<sin método>'} ↔ {detected_type}"))

    if width is not None and height is not None:
        allowed, detail = _dimensions_allowed(method, detected_type, width, height)
        if not allowed:
            code = ERROR_DIMENSIONS_TOO_LARGE if width > MAX_PIXEL_DIMENSION or height > MAX_PIXEL_DIMENSION else ERROR_DIMENSIONS_TOO_SMALL
            checks.append(MediaValidationCheck("dimensions", CHECK_FAIL, detail))
            errors.append(_issue(code, detail, "media_path"))
        else:
            checks.append(MediaValidationCheck("dimensions", CHECK_PASS, detail))

    return _result(
        media,
        checks=checks,
        errors=errors,
        content_sha256=actual_hash,
        bytes_size=actual_size,
        detected_type=detected_type,
        width=width,
        height=height,
    )
