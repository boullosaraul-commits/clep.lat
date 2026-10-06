#!/usr/bin/env python3
"""Autoridad única de resolución de media editorial CLEP.

Principios:
- una candidatura produce como máximo una resolución activa;
- toda resolución debe ser trazable y determinista;
- la jerarquía de fuentes es explícita y estable;
- resolución no equivale a validación física del archivo;
- la validación material del asset pertenece a validar_media.py (Paso 5).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

RESOLVER_VERSION = 1

MEDIA_STATUS_RESOLVED = "RESOLVED"
MEDIA_STATUS_FAILED = "FAILED"

MEDIA_METHOD_OFFICIAL_IMAGE = "official_image"
MEDIA_METHOD_EXPLICIT_COVER = "explicit_cover"
MEDIA_METHOD_EXPLICIT_THUMBNAIL = "explicit_thumbnail"
MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE = "official_landing_capture"
MEDIA_METHOD_DETERMINISTIC_CHART = "deterministic_chart"
MEDIA_METHOD_DETERMINISTIC_CARD = "deterministic_card"

ALLOWED_MEDIA_METHODS = {
    MEDIA_METHOD_OFFICIAL_IMAGE,
    MEDIA_METHOD_EXPLICIT_COVER,
    MEDIA_METHOD_EXPLICIT_THUMBNAIL,
    MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
    MEDIA_METHOD_DETERMINISTIC_CHART,
    MEDIA_METHOD_DETERMINISTIC_CARD,
}

RIGHTS_VERIFIED = "VERIFICADO"
RIGHTS_OFFICIAL_CAPTURE = "CAPTURA_LANDING_OFICIAL"
RIGHTS_OWN_DETERMINISTIC = "PROPIO_DETERMINISTA"

ALLOWED_RIGHTS_STATUS = {
    RIGHTS_VERIFIED,
    RIGHTS_OFFICIAL_CAPTURE,
    RIGHTS_OWN_DETERMINISTIC,
}

# Jerarquía congelada del Paso 4. Los niveles son parte del contrato de
# provenance: cambiar el orden requiere incrementar RESOLVER_VERSION.
MEDIA_HIERARCHY: tuple[tuple[int, str], ...] = (
    (1, MEDIA_METHOD_OFFICIAL_IMAGE),
    (2, MEDIA_METHOD_EXPLICIT_COVER),
    (2, MEDIA_METHOD_EXPLICIT_THUMBNAIL),
    (3, MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE),
    (4, MEDIA_METHOD_DETERMINISTIC_CHART),
    (4, MEDIA_METHOD_DETERMINISTIC_CARD),
)


class MediaResolutionError(ValueError):
    """Error estructurado y fail-closed de resolución de media."""

    def __init__(self, code: str, detail: str, field_name: str = ""):
        self.code = code
        self.detail = detail
        self.field = field_name
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class MediaAttempt:
    """Traza de una fuente evaluada durante la resolución."""

    level: int
    method: str
    selected: bool
    outcome: str
    reason: str = ""
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MediaResolution:
    """Resultado canónico de resolve_media(candidate)."""

    media_status: str
    media_type: str
    media_path: str
    media_url: str
    media_source: str
    media_source_url: str
    media_method: str
    media_rights_status: str
    alt_text: str
    resolver_version: int
    fallback_level: int
    resolution_fingerprint: str
    attempts: tuple[MediaAttempt, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data


@dataclass(frozen=True)
class StrategyResult:
    """Resultado interno de una estrategia antes de validar la resolución final."""

    resolution: MediaResolution | None
    outcome: str
    reason: str = ""
    source_url: str = ""


Strategy = Callable[[dict[str, Any], tuple[MediaAttempt, ...]], StrategyResult]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def _fingerprint(method: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "resolver_version": RESOLVER_VERSION,
            "method": method,
            "payload": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_resolution(result: MediaResolution) -> MediaResolution:
    """Valida sólo el contrato lógico, no el archivo físico."""
    if result.media_status != MEDIA_STATUS_RESOLVED:
        raise MediaResolutionError(
            "MEDIA_RESOLUTION_FAILED",
            f"media_status inválido para una resolución activa: {result.media_status!r}",
            "media_status",
        )
    if result.media_method not in ALLOWED_MEDIA_METHODS:
        raise MediaResolutionError(
            "MEDIA_METHOD_INVALID",
            f"método no soportado: {result.media_method!r}",
            "media_method",
        )
    if result.media_rights_status not in ALLOWED_RIGHTS_STATUS:
        raise MediaResolutionError(
            "MEDIA_RIGHTS_UNVERIFIED",
            f"estatus de derechos no permitido: {result.media_rights_status!r}",
            "media_rights_status",
        )
    if not (result.media_path or result.media_url):
        raise MediaResolutionError(
            "MEDIA_LOCATION_MISSING",
            "la resolución requiere media_path o media_url",
            "media_path",
        )
    if not result.media_source:
        raise MediaResolutionError(
            "MEDIA_SOURCE_MISSING",
            "la resolución requiere media_source",
            "media_source",
        )
    if not result.alt_text:
        raise MediaResolutionError(
            "MEDIA_ALT_TEXT_MISSING",
            "la resolución requiere alt_text",
            "alt_text",
        )
    if result.resolver_version != RESOLVER_VERSION:
        raise MediaResolutionError(
            "MEDIA_RESOLVER_VERSION_INVALID",
            f"resolver_version={result.resolver_version!r}; esperado={RESOLVER_VERSION}",
            "resolver_version",
        )
    if result.fallback_level < 1:
        raise MediaResolutionError(
            "MEDIA_FALLBACK_LEVEL_INVALID",
            "fallback_level debe ser >= 1",
            "fallback_level",
        )
    if not result.resolution_fingerprint:
        raise MediaResolutionError(
            "MEDIA_FINGERPRINT_MISSING",
            "la resolución requiere resolution_fingerprint",
            "resolution_fingerprint",
        )
    return result


def _resolve_official_image(
    candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]
) -> StrategyResult:
    """Resuelve una imagen oficial explícita sin descargarla ni validarla físicamente."""
    del attempts
    url = clean(candidate.get("official_image_url"))
    if not url:
        return StrategyResult(None, "MISSING", "official_image_url ausente")
    if not _is_https_url(url):
        return StrategyResult(None, "INVALID_URL", "official_image_url debe ser HTTPS", url)

    rights = clean(candidate.get("official_image_rights"))
    if rights != RIGHTS_VERIFIED:
        return StrategyResult(None, "RIGHTS_UNVERIFIED", "official_image_rights debe ser VERIFICADO", url)

    source = clean(
        candidate.get("official_image_source")
        or candidate.get("official_source")
        or candidate.get("source_name")
    )
    if not source:
        return StrategyResult(None, "SOURCE_MISSING", "imagen oficial sin provenance de fuente", url)

    source_url = clean(candidate.get("official_image_source_url") or url)
    if source_url and not _is_https_url(source_url):
        return StrategyResult(None, "SOURCE_URL_INVALID", "official_image_source_url debe ser HTTPS", url)

    alt_text = clean(candidate.get("official_image_alt") or candidate.get("title"))
    if not alt_text:
        return StrategyResult(None, "ALT_TEXT_MISSING", "imagen oficial sin alt_text factual ni título", url)

    media_type = clean(candidate.get("official_image_type") or "image")
    payload = {
        "official_image_url": url,
        "official_image_source": source,
        "official_image_source_url": source_url,
        "official_image_rights": rights,
        "official_image_alt": alt_text,
        "official_image_type": media_type,
    }
    resolution = MediaResolution(
        media_status=MEDIA_STATUS_RESOLVED,
        media_type=media_type,
        media_path="",
        media_url=url,
        media_source=source,
        media_source_url=source_url,
        media_method=MEDIA_METHOD_OFFICIAL_IMAGE,
        media_rights_status=RIGHTS_VERIFIED,
        alt_text=alt_text,
        resolver_version=RESOLVER_VERSION,
        fallback_level=1,
        resolution_fingerprint=_fingerprint(MEDIA_METHOD_OFFICIAL_IMAGE, payload),
    )
    return StrategyResult(
        resolution,
        "RESOLVED",
        "imagen oficial explícita con derechos y provenance verificados",
        url,
    )


def _resolve_structured_asset(
    candidate: dict[str, Any],
    *,
    method: str,
    prefix: str,
    default_label: str,
) -> StrategyResult:
    """Resuelve cover/thumbnail sólo desde metadata estructurada explícita."""
    url = clean(candidate.get(f"{prefix}_url"))
    if not url:
        return StrategyResult(None, "MISSING", f"{prefix}_url ausente")
    if not _is_https_url(url):
        return StrategyResult(None, "INVALID_URL", f"{prefix}_url debe ser HTTPS", url)

    rights = clean(candidate.get(f"{prefix}_rights"))
    if rights != RIGHTS_VERIFIED:
        return StrategyResult(
            None,
            "RIGHTS_UNVERIFIED",
            f"{prefix}_rights debe ser VERIFICADO",
            url,
        )

    source = clean(
        candidate.get(f"{prefix}_source")
        or candidate.get("official_source")
        or candidate.get("source_name")
    )
    if not source:
        return StrategyResult(None, "SOURCE_MISSING", f"{prefix} sin provenance de fuente", url)

    source_url = clean(candidate.get(f"{prefix}_source_url") or url)
    if source_url and not _is_https_url(source_url):
        return StrategyResult(
            None,
            "SOURCE_URL_INVALID",
            f"{prefix}_source_url debe ser HTTPS",
            url,
        )

    title = clean(candidate.get("title") or candidate.get("indicator_or_dataset"))
    alt_text = clean(candidate.get(f"{prefix}_alt"))
    if not alt_text and title:
        alt_text = f"{default_label}: {title}"
    if not alt_text:
        return StrategyResult(
            None,
            "ALT_TEXT_MISSING",
            f"{prefix} sin alt_text factual ni título",
            url,
        )

    media_type = clean(candidate.get(f"{prefix}_type") or "image")
    payload = {
        f"{prefix}_url": url,
        f"{prefix}_source": source,
        f"{prefix}_source_url": source_url,
        f"{prefix}_rights": rights,
        f"{prefix}_alt": alt_text,
        f"{prefix}_type": media_type,
    }
    return StrategyResult(
        resolution=MediaResolution(
            media_status=MEDIA_STATUS_RESOLVED,
            media_type=media_type,
            media_path="",
            media_url=url,
            media_source=source,
            media_source_url=source_url,
            media_method=method,
            media_rights_status=RIGHTS_VERIFIED,
            alt_text=alt_text,
            resolver_version=RESOLVER_VERSION,
            fallback_level=2,
            resolution_fingerprint=_fingerprint(method, payload),
        ),
        outcome="RESOLVED",
        reason=f"{prefix} explícita con derechos y provenance verificados",
        source_url=url,
    )


def _resolve_explicit_cover(
    candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]
) -> StrategyResult:
    del attempts
    return _resolve_structured_asset(
        candidate,
        method=MEDIA_METHOD_EXPLICIT_COVER,
        prefix="cover",
        default_label="Portada",
    )


def _resolve_explicit_thumbnail(
    candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]
) -> StrategyResult:
    del attempts
    return _resolve_structured_asset(
        candidate,
        method=MEDIA_METHOD_EXPLICIT_THUMBNAIL,
        prefix="thumbnail",
        default_label="Miniatura",
    )


def _resolve_official_landing_capture(
    candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]
) -> StrategyResult:
    """Planifica una captura determinista de la landing oficial.

    Esta estrategia no ejecuta Chrome ni afirma que el PNG exista. Sólo decide
    que la landing oficial es la fuente seleccionada y fija de forma estable el
    destino esperado. La materialización y la validación física ocurren fuera
    de esta decisión editorial.
    """
    del attempts
    url = clean(candidate.get("official_landing_url") or candidate.get("source_url") or candidate.get("access_url"))
    if not url:
        return StrategyResult(None, "MISSING", "landing oficial ausente")
    if not _is_https_url(url):
        return StrategyResult(None, "INVALID_URL", "landing oficial debe ser HTTPS", url)

    title = clean(candidate.get("title") or candidate.get("indicator_or_dataset"))
    if not title:
        return StrategyResult(None, "ALT_TEXT_MISSING", "captura oficial requiere título factual", url)

    source = clean(
        candidate.get("official_landing_source")
        or candidate.get("official_source")
        or candidate.get("source_name")
        or urlparse(url).netloc
    )
    if not source:
        return StrategyResult(None, "SOURCE_MISSING", "landing oficial sin provenance de fuente", url)

    candidate_id = clean(candidate.get("candidate_id"))
    url_digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    stem = candidate_id or url_digest
    media_path = f"data/editorial/media/{stem}-landing-{url_digest}.png"
    alt_text = f"Captura de la página oficial: {title}"
    payload = {
        "official_landing_url": url,
        "official_landing_source": source,
        "candidate_id": candidate_id,
        "viewport": "1200x1500",
        "virtual_time_budget_ms": 5000,
        "media_path": media_path,
        "alt_text": alt_text,
    }
    return StrategyResult(
        resolution=MediaResolution(
            media_status=MEDIA_STATUS_RESOLVED,
            media_type="image/png",
            media_path=media_path,
            media_url="",
            media_source=source,
            media_source_url=url,
            media_method=MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
            media_rights_status=RIGHTS_OFFICIAL_CAPTURE,
            alt_text=alt_text,
            resolver_version=RESOLVER_VERSION,
            fallback_level=3,
            resolution_fingerprint=_fingerprint(MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE, payload),
        ),
        outcome="RESOLVED",
        reason="landing oficial HTTPS seleccionada para captura determinista",
        source_url=url,
    )


def _not_implemented(method: str) -> Strategy:
    """Placeholder explícito para estrategias aún pendientes de 4.7–4.8."""

    def strategy(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
        del candidate, attempts
        return StrategyResult(
            resolution=None,
            outcome="NOT_IMPLEMENTED",
            reason=f"estrategia {method} pendiente de implementación",
        )

    return strategy


STRATEGIES: dict[str, Strategy] = {
    method: _not_implemented(method) for _, method in MEDIA_HIERARCHY
}
STRATEGIES[MEDIA_METHOD_OFFICIAL_IMAGE] = _resolve_official_image
STRATEGIES[MEDIA_METHOD_EXPLICIT_COVER] = _resolve_explicit_cover
STRATEGIES[MEDIA_METHOD_EXPLICIT_THUMBNAIL] = _resolve_explicit_thumbnail
STRATEGIES[MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE] = _resolve_official_landing_capture


def resolve_media(candidate: dict[str, Any]) -> MediaResolution:
    """Evalúa las fuentes en orden estricto y devuelve la primera resolución válida.

    Una estrategia inferior sólo puede ejecutarse si todas las superiores no
    produjeron una resolución. Cada evaluación queda registrada en `attempts`.
    """
    if not isinstance(candidate, dict):
        raise MediaResolutionError(
            "MEDIA_CANDIDATE_INVALID",
            "candidate debe ser un diccionario",
            "candidate",
        )

    attempts: list[MediaAttempt] = []
    for level, method in MEDIA_HIERARCHY:
        strategy = STRATEGIES[method]
        result = strategy(candidate, tuple(attempts))
        if result.resolution is not None:
            selected_attempt = MediaAttempt(
                level=level,
                method=method,
                selected=True,
                outcome=result.outcome or "RESOLVED",
                reason=result.reason,
                source_url=result.source_url,
            )
            final = result.resolution
            final = MediaResolution(
                media_status=final.media_status,
                media_type=final.media_type,
                media_path=final.media_path,
                media_url=final.media_url,
                media_source=final.media_source,
                media_source_url=final.media_source_url,
                media_method=method,
                media_rights_status=final.media_rights_status,
                alt_text=final.alt_text,
                resolver_version=RESOLVER_VERSION,
                fallback_level=level,
                resolution_fingerprint=final.resolution_fingerprint,
                attempts=tuple([*attempts, selected_attempt]),
            )
            return validate_resolution(final)

        attempts.append(
            MediaAttempt(
                level=level,
                method=method,
                selected=False,
                outcome=result.outcome or "SKIPPED",
                reason=result.reason,
                source_url=result.source_url,
            )
        )

    detail = "; ".join(
        f"L{attempt.level}:{attempt.method}={attempt.outcome}"
        for attempt in attempts
    )
    raise MediaResolutionError(
        "MEDIA_RESOLUTION_FAILED",
        "ninguna estrategia produjo una resolución" + (f" ({detail})" if detail else ""),
    )
