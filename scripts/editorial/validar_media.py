#!/usr/bin/env python3
"""Validador físico determinista de media editorial CLEP.

Tanda A del Paso 5 (5.1–5.4):
- contrato estructurado de validación;
- confinamiento de rutas dentro de data/editorial/media;
- existencia, archivo regular y tamaño;
- integridad SHA-256 contra el hash registrado por adquisición.

Este módulo no decide qué media usar, no hace red, no repara assets y no
activa fallbacks. La detección de formato, raster/SVG y dimensiones pertenece
a las siguientes tandas del Paso 5.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = (ROOT / "data/editorial/media").resolve()
VALIDATION_VERSION = 1
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

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


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
) -> MediaValidationResult:
    return MediaValidationResult(
        status=STATUS_INVALID if errors else STATUS_VALID,
        media_path=_clean(media.get("media_path")),
        declared_type=_clean(media.get("media_type") or media.get("media_type_declared")),
        detected_type="",
        content_sha256=content_sha256,
        bytes_size=bytes_size,
        width=None,
        height=None,
        validation_version=VALIDATION_VERSION,
        resolution_fingerprint=_clean(
            media.get("media_resolution_fingerprint")
            or media.get("resolution_fingerprint")
        ),
        media_method=_clean(media.get("media_method") or media.get("acquisition_method")),
        checks=tuple(checks),
        errors=tuple(errors),
    )


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


def validate_media(media: Mapping[str, Any]) -> MediaValidationResult:
    """Valida integridad material básica sin efectos laterales.

    Los fallos esperables del asset devuelven `status=INVALID` y errores
    estructurados. La función nunca corrige, mueve, reemplaza ni elimina el
    archivo inspeccionado.
    """
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
        checks.append(
            MediaValidationCheck(
                "size",
                CHECK_FAIL,
                f"{stat_size} bytes exceden máximo {MAX_MEDIA_BYTES}",
            )
        )
        errors.append(
            _issue(
                ERROR_FILE_TOO_LARGE,
                f"asset excede máximo de {MAX_MEDIA_BYTES} bytes",
                "media_path",
            )
        )
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
        actual_hash, actual_size = _sha256_file(target)
    except OSError as exc:
        checks.append(MediaValidationCheck("sha256", CHECK_FAIL, f"lectura falló: {exc}"))
        errors.append(_issue(ERROR_FILE_READ_FAILED, f"no se pudieron leer bytes del asset: {exc}", "media_path"))
        return _result(media, checks=checks, errors=errors, bytes_size=stat_size)

    if actual_size != stat_size:
        checks.append(
            MediaValidationCheck(
                "size_consistency",
                CHECK_FAIL,
                f"stat={stat_size}, leído={actual_size}",
            )
        )
        errors.append(
            _issue(
                ERROR_FILE_READ_FAILED,
                "el tamaño cambió durante la validación",
                "media_path",
            )
        )
        return _result(
            media,
            checks=checks,
            errors=errors,
            content_sha256=actual_hash,
            bytes_size=actual_size,
        )

    checks.append(MediaValidationCheck("size_consistency", CHECK_PASS, f"{actual_size} bytes"))

    if actual_hash.lower() != expected_hash.lower():
        checks.append(MediaValidationCheck("sha256", CHECK_FAIL, "hash real distinto del registrado"))
        errors.append(
            _issue(
                ERROR_HASH_MISMATCH,
                f"esperado={expected_hash.lower()} actual={actual_hash}",
                "media_content_sha256",
            )
        )
        return _result(
            media,
            checks=checks,
            errors=errors,
            content_sha256=actual_hash,
            bytes_size=actual_size,
        )

    checks.append(MediaValidationCheck("sha256", CHECK_PASS, actual_hash))
    return _result(
        media,
        checks=checks,
        errors=errors,
        content_sha256=actual_hash,
        bytes_size=actual_size,
    )
