#!/usr/bin/env python3
"""Capa de efectos laterales para media editorial CLEP.

`resolver_media.py` decide. Este módulo materializa esa decisión:
- descarga assets remotos explícitos;
- captura una landing oficial;
- renderiza gráfica/tarjeta deterministas.

No decide qué fuente tiene prioridad y no certifica que el asset sea publicable.
La validación material pertenece a `validar_media.py` (Paso 5).
"""
from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from capturar_landing import capture
from generar_grafica_clep import render as render_chart
from generar_tarjeta_clep import render as render_card
from resolver_media import (
    MEDIA_METHOD_DETERMINISTIC_CARD,
    MEDIA_METHOD_DETERMINISTIC_CHART,
    MEDIA_METHOD_EXPLICIT_COVER,
    MEDIA_METHOD_EXPLICIT_THUMBNAIL,
    MEDIA_METHOD_OFFICIAL_IMAGE,
    MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
    MediaResolution,
)

ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = ROOT / "data/editorial/media"
UA = "CLEP-editorial/3.0 (+https://clep.lat)"
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024

# Sólo estos fallos significan que una fuente concreta no pudo materializarse
# y permiten pedir al resolver el siguiente fallback. Errores de contrato,
# rutas, colisiones o métodos desconocidos siguen siendo fail-closed.
FALLBACK_ACQUISITION_ERRORS = {
    "MEDIA_DOWNLOAD_FAILED",
    "MEDIA_DOWNLOAD_TOO_LARGE",
    "MEDIA_CAPTURE_BROWSER_MISSING",
    "MEDIA_CAPTURE_FAILED",
    "MEDIA_VISUAL_INVALID",
    "MEDIA_VISUAL_UNCERTAIN",
    "MEDIA_RENDER_FAILED",
}


class MediaAcquisitionError(RuntimeError):
    def __init__(self, code: str, detail: str, field_name: str = ""):
        self.code = code
        self.detail = detail
        self.field = field_name
        super().__init__(f"{code}: {detail}")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail, "field": self.field}


def is_fallback_acquisition_error(error: MediaAcquisitionError) -> bool:
    """Indica si el fallo afecta a la fuente y admite el siguiente fallback."""
    return error.code in FALLBACK_ACQUISITION_ERRORS


@dataclass(frozen=True)
class AcquiredMedia:
    media_path: str
    media_type_declared: str
    acquisition_method: str
    resolution_fingerprint: str
    content_sha256: str
    bytes_written: int
    reused_existing: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_target(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise MediaAcquisitionError(
            "MEDIA_ACQUISITION_PATH_INVALID",
            f"ruta no permitida: {relative_path!r}",
            "media_path",
        )
    target = (ROOT / relative).resolve()
    media_root = MEDIA_ROOT.resolve()
    if media_root not in target.parents:
        raise MediaAcquisitionError(
            "MEDIA_ACQUISITION_PATH_INVALID",
            f"ruta fuera de media root: {relative_path!r}",
            "media_path",
        )
    return target


def _write_bytes_once(relative_path: str, content: bytes) -> tuple[str, int, bool]:
    target = _safe_target(relative_path)
    digest = hashlib.sha256(content).hexdigest()
    if target.exists():
        try:
            current = target.read_bytes()
        except OSError as exc:
            raise MediaAcquisitionError(
                "MEDIA_ASSET_CONFLICT",
                f"no se pudo leer asset existente {relative_path}: {exc}",
                "media_path",
            ) from exc
        if current != content:
            raise MediaAcquisitionError(
                "MEDIA_ASSET_CONFLICT",
                f"asset existente no coincide con el contenido esperado: {relative_path}",
                "media_path",
            )
        return digest, len(content), True
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return digest, len(content), False


def _remote_target(resolution: MediaResolution, content_type: str, content: bytes) -> str:
    suffixes = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    suffix = suffixes.get(content_type.split(";", 1)[0].strip().lower(), "bin")
    digest = resolution.resolution_fingerprint[:16]
    return f"data/editorial/media/remote-{digest}-{hashlib.sha256(content).hexdigest()[:16]}.{suffix}"


def _download_remote(resolution: MediaResolution) -> AcquiredMedia:
    url = resolution.media_url
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise MediaAcquisitionError(
            "MEDIA_ACQUISITION_URL_INVALID",
            "asset remoto requiere URL HTTPS",
            "media_url",
        )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "image/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = str(response.headers.get("Content-Type") or "application/octet-stream")
            content = response.read(MAX_DOWNLOAD_BYTES + 1)
    except Exception as exc:
        raise MediaAcquisitionError(
            "MEDIA_DOWNLOAD_FAILED",
            f"descarga falló: {type(exc).__name__}: {exc}",
            "media_url",
        ) from exc
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise MediaAcquisitionError(
            "MEDIA_DOWNLOAD_TOO_LARGE",
            f"descarga excede {MAX_DOWNLOAD_BYTES} bytes",
            "media_url",
        )
    target = _remote_target(resolution, content_type, content)
    sha256, size, reused = _write_bytes_once(target, content)
    return AcquiredMedia(
        media_path=target,
        media_type_declared=content_type,
        acquisition_method=resolution.media_method,
        resolution_fingerprint=resolution.resolution_fingerprint,
        content_sha256=sha256,
        bytes_written=size,
        reused_existing=reused,
    )


def _capture_landing(resolution: MediaResolution) -> AcquiredMedia:
    payload = resolution.acquisition_payload
    url = str(payload.get("url") or resolution.media_source_url or "").strip()
    relative_path = str(payload.get("media_path") or resolution.media_path or "").strip()
    if not url or not relative_path:
        raise MediaAcquisitionError(
            "MEDIA_CAPTURE_PLAN_INVALID",
            "captura requiere url y media_path",
        )
    _safe_target(relative_path)
    if os.getenv("CLEP_SCREENSHOT_LIMIT") == "0":
        raise MediaAcquisitionError("MEDIA_CAPTURE_FAILED", "captura deshabilitada en esta ejecución")
    try:
        width, height = map(int, payload["viewport"].split("x"))
        content, check, evidence = capture(url, payload["title"], width, height)
    except Exception as exc:
        raise MediaAcquisitionError("MEDIA_CAPTURE_FAILED", f"navegación fallida: {type(exc).__name__}") from exc
    if not check.valid:
        raise MediaAcquisitionError(f"MEDIA_VISUAL_{check.status}", f"{check.reason}; {evidence}")
    # Vincular la evidencia al contenido exacto. Una captura nueva nunca hereda
    # la aprobación de un archivo que ya exista para el mismo plan.
    digest = hashlib.sha256(content).hexdigest()
    target = Path(relative_path)
    relative_path = str(target.with_name(f"{target.stem}-{digest[:16]}.png"))
    sha256, size, reused = _write_bytes_once(relative_path, content)
    return AcquiredMedia(relative_path, "image/png", resolution.media_method,
                         resolution.resolution_fingerprint, sha256, size, reused)


def _render_chart(resolution: MediaResolution) -> AcquiredMedia:
    payload = resolution.acquisition_payload
    relative_path = str(payload.get("media_path") or resolution.media_path or "").strip()
    chart_input = {
        "title": payload.get("title"),
        "geography": payload.get("geography"),
        "source": payload.get("source"),
        "points": payload.get("points"),
        "unit": payload.get("unit"),
        "source_snapshot": payload.get("source_snapshot"),
        "series": payload.get("series"),
    }
    try:
        svg = render_chart(chart_input)
    except Exception as exc:
        raise MediaAcquisitionError(
            "MEDIA_RENDER_FAILED",
            f"gráfica no renderizable: {type(exc).__name__}: {exc}",
        ) from exc
    content = svg.encode("utf-8")
    sha256, size, reused = _write_bytes_once(relative_path, content)
    return AcquiredMedia(
        media_path=relative_path,
        media_type_declared="image/svg+xml",
        acquisition_method=resolution.media_method,
        resolution_fingerprint=resolution.resolution_fingerprint,
        content_sha256=sha256,
        bytes_written=size,
        reused_existing=reused,
    )


def _render_card(resolution: MediaResolution) -> AcquiredMedia:
    payload = resolution.acquisition_payload
    relative_path = str(payload.get("media_path") or resolution.media_path or "").strip()
    card_input = {
        "synopsis": payload.get("synopsis"),
        "synopsis_method": payload.get("synopsis_method"),
        "label": payload.get("label"),
        "series": payload.get("series"),
        "title": payload.get("title"),
        "meta": payload.get("meta"),
        "source": payload.get("source"),
    }
    try:
        svg = render_card(card_input)
    except Exception as exc:
        raise MediaAcquisitionError(
            "MEDIA_RENDER_FAILED",
            f"tarjeta no renderizable: {type(exc).__name__}: {exc}",
        ) from exc
    content = svg.encode("utf-8")
    sha256, size, reused = _write_bytes_once(relative_path, content)
    return AcquiredMedia(
        media_path=relative_path,
        media_type_declared="image/svg+xml",
        acquisition_method=resolution.media_method,
        resolution_fingerprint=resolution.resolution_fingerprint,
        content_sha256=sha256,
        bytes_written=size,
        reused_existing=reused,
    )


def acquire_media(resolution: MediaResolution) -> AcquiredMedia:
    """Materializa una resolución ya tomada; nunca cambia la prioridad editorial."""
    method = resolution.media_method
    if method in {
        MEDIA_METHOD_OFFICIAL_IMAGE,
        MEDIA_METHOD_EXPLICIT_COVER,
        MEDIA_METHOD_EXPLICIT_THUMBNAIL,
    }:
        return _download_remote(resolution)
    if method == MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE:
        return _capture_landing(resolution)
    if method == MEDIA_METHOD_DETERMINISTIC_CHART:
        return _render_chart(resolution)
    if method == MEDIA_METHOD_DETERMINISTIC_CARD:
        return _render_card(resolution)
    raise MediaAcquisitionError(
        "MEDIA_ACQUISITION_METHOD_INVALID",
        f"método no soportado: {method!r}",
        "media_method",
    )
