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

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

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


def _not_implemented(method: str) -> Strategy:
    """Placeholder explícito para estrategias aún pendientes de 4.4–4.8."""

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
