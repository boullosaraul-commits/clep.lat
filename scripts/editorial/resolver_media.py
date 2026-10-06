#!/usr/bin/env python3
"""Autoridad pura de resolución de media editorial CLEP.

Este módulo decide qué media corresponde y produce un plan determinista.
No descarga, no captura, no renderiza archivos y no escribe al filesystem.
La adquisición/materialización pertenece a adquirir_media.py y la validación
material del asset a validar_media.py (Paso 5).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

RESOLVER_VERSION = 1
CHART_RENDERER_VERSION = 1
CARD_RENDERER_VERSION = 1
CAPTURE_POLICY_VERSION = 1

MEDIA_STATUS_RESOLVED = "RESOLVED"

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

OUTCOME_RESOLVED = "RESOLVED"
OUTCOME_MISSING = "MISSING"
OUTCOME_NOT_APPLICABLE = "NOT_APPLICABLE"
OUTCOME_INVALID_URL = "INVALID_URL"
OUTCOME_SOURCE_URL_INVALID = "SOURCE_URL_INVALID"
OUTCOME_RIGHTS_UNVERIFIED = "RIGHTS_UNVERIFIED"
OUTCOME_SOURCE_MISSING = "SOURCE_MISSING"
OUTCOME_ALT_TEXT_MISSING = "ALT_TEXT_MISSING"
OUTCOME_INVALID_DATA = "INVALID_DATA"
OUTCOME_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
OUTCOME_METADATA_MISSING = "METADATA_MISSING"
OUTCOME_METADATA_INVALID = "METADATA_INVALID"
OUTCOME_ACQUISITION_FAILED = "ACQUISITION_FAILED"

FALLBACK_OUTCOMES = {
    OUTCOME_MISSING,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_INVALID_URL,
    OUTCOME_SOURCE_URL_INVALID,
    OUTCOME_RIGHTS_UNVERIFIED,
    OUTCOME_SOURCE_MISSING,
    OUTCOME_ALT_TEXT_MISSING,
    OUTCOME_INVALID_DATA,
    OUTCOME_INSUFFICIENT_DATA,
    OUTCOME_METADATA_MISSING,
    OUTCOME_METADATA_INVALID,
    OUTCOME_ACQUISITION_FAILED,
}

ERROR_CANDIDATE_INVALID = "MEDIA_CANDIDATE_INVALID"
ERROR_RESOLUTION_FAILED = "MEDIA_RESOLUTION_FAILED"
ERROR_STRATEGY_ERROR = "MEDIA_STRATEGY_ERROR"
ERROR_METHOD_INVALID = "MEDIA_METHOD_INVALID"
ERROR_RIGHTS_UNVERIFIED = "MEDIA_RIGHTS_UNVERIFIED"
ERROR_LOCATION_MISSING = "MEDIA_LOCATION_MISSING"
ERROR_SOURCE_MISSING = "MEDIA_SOURCE_MISSING"
ERROR_ALT_TEXT_MISSING = "MEDIA_ALT_TEXT_MISSING"
ERROR_RESOLVER_VERSION_INVALID = "MEDIA_RESOLVER_VERSION_INVALID"
ERROR_FALLBACK_LEVEL_INVALID = "MEDIA_FALLBACK_LEVEL_INVALID"
ERROR_FINGERPRINT_MISSING = "MEDIA_FINGERPRINT_MISSING"

MEDIA_HIERARCHY: tuple[tuple[int, str], ...] = (
    (1, MEDIA_METHOD_OFFICIAL_IMAGE),
    (2, MEDIA_METHOD_EXPLICIT_COVER),
    (2, MEDIA_METHOD_EXPLICIT_THUMBNAIL),
    (3, MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE),
    (4, MEDIA_METHOD_DETERMINISTIC_CHART),
    (4, MEDIA_METHOD_DETERMINISTIC_CARD),
)

CARD_LABELS = {
    "paper": "PAPER ABIERTO · CLEP",
    "book": "LIBRO ABIERTO · CLEP",
    "chapter": "CAPÍTULO ABIERTO · CLEP",
    "report": "INFORME ABIERTO · CLEP",
    "policy_brief": "POLICY BRIEF · CLEP",
    "special_issue": "NÚMERO ESPECIAL · CLEP",
    "thesis": "TESIS ABIERTA · CLEP",
    "edition_translation": "NUEVA EDICIÓN / TRADUCCIÓN · CLEP",
    "dataset_grafica": "DATOS · CLEP",
    "convocatoria_evento": "AGENDA · CLEP",
    "video": "VIDEO · CLEP",
    "recurso": "RECURSO · CLEP",
}


@dataclass(frozen=True)
class MediaAttempt:
    level: int
    method: str
    selected: bool
    outcome: str
    reason: str = ""
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MediaResolutionError(ValueError):
    """Error estructurado del resolver; nunca implica retry automático."""

    def __init__(
        self,
        code: str,
        detail: str,
        field_name: str = "",
        attempts: tuple[MediaAttempt, ...] = (),
    ):
        self.code = code
        self.detail = detail
        self.field = field_name
        self.attempts = attempts
        super().__init__(f"{code}: {detail}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "detail": self.detail,
            "field": self.field,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


@dataclass(frozen=True)
class MediaResolution:
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
    acquisition_payload: dict[str, Any] = field(default_factory=dict)
    attempts: tuple[MediaAttempt, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data


@dataclass(frozen=True)
class StrategyResult:
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


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fingerprint(method: str, payload: dict[str, Any]) -> str:
    return _canonical_hash(
        {
            "resolver_version": RESOLVER_VERSION,
            "method": method,
            "payload": payload,
        }
    )


def _source_name(candidate: dict[str, Any]) -> str:
    return clean(
        candidate.get("official_source")
        or candidate.get("source_name")
        or candidate.get("source_id")
        or candidate.get("source_type")
    )


def _year(candidate: dict[str, Any]) -> str:
    value = clean(candidate.get("publication_year"))
    if re.fullmatch(r"(?:18|19|20)\d{2}", value):
        return value
    match = re.search(r"\b(?:18|19|20)\d{2}\b", clean(candidate.get("published_at")))
    return match.group(0) if match else ""


def _asset_path(candidate: dict[str, Any], mode: str, digest: str, suffix: str) -> str:
    candidate_id = clean(candidate.get("candidate_id"))
    stem = candidate_id or digest
    return f"data/editorial/media/{stem}-{mode}-{digest}.{suffix}"


def factual_alt_text(method: str, candidate: dict[str, Any], explicit_alt: str = "") -> str:
    title = clean(candidate.get("title") or candidate.get("indicator_or_dataset"))
    if method == MEDIA_METHOD_OFFICIAL_IMAGE:
        return clean(explicit_alt) or title
    if method == MEDIA_METHOD_EXPLICIT_COVER:
        return clean(explicit_alt) or (f"Portada: {title}" if title else "")
    if method == MEDIA_METHOD_EXPLICIT_THUMBNAIL:
        return clean(explicit_alt) or (f"Miniatura: {title}" if title else "")
    if method == MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE:
        return f"Captura de la página oficial: {title}" if title else ""
    if method == MEDIA_METHOD_DETERMINISTIC_CHART:
        return f"Gráfica CLEP: {title}" if title else ""
    if method == MEDIA_METHOD_DETERMINISTIC_CARD:
        return f"Tarjeta CLEP: {title}" if title else ""
    raise MediaResolutionError(ERROR_METHOD_INVALID, f"método no soportado: {method!r}", "media_method")


def validate_resolution(result: MediaResolution) -> MediaResolution:
    if result.media_status != MEDIA_STATUS_RESOLVED:
        raise MediaResolutionError(ERROR_RESOLUTION_FAILED, f"media_status inválido: {result.media_status!r}", "media_status", result.attempts)
    if result.media_method not in ALLOWED_MEDIA_METHODS:
        raise MediaResolutionError(ERROR_METHOD_INVALID, f"método no soportado: {result.media_method!r}", "media_method", result.attempts)
    if result.media_rights_status not in ALLOWED_RIGHTS_STATUS:
        raise MediaResolutionError(ERROR_RIGHTS_UNVERIFIED, f"estatus de derechos no permitido: {result.media_rights_status!r}", "media_rights_status", result.attempts)
    if not (result.media_path or result.media_url):
        raise MediaResolutionError(ERROR_LOCATION_MISSING, "la resolución requiere media_path o media_url", "media_path", result.attempts)
    if not result.media_source:
        raise MediaResolutionError(ERROR_SOURCE_MISSING, "la resolución requiere media_source", "media_source", result.attempts)
    if not result.alt_text:
        raise MediaResolutionError(ERROR_ALT_TEXT_MISSING, "la resolución requiere alt_text", "alt_text", result.attempts)
    if result.resolver_version != RESOLVER_VERSION:
        raise MediaResolutionError(ERROR_RESOLVER_VERSION_INVALID, f"resolver_version={result.resolver_version!r}; esperado={RESOLVER_VERSION}", "resolver_version", result.attempts)
    if result.fallback_level < 1:
        raise MediaResolutionError(ERROR_FALLBACK_LEVEL_INVALID, "fallback_level debe ser >= 1", "fallback_level", result.attempts)
    if not result.resolution_fingerprint:
        raise MediaResolutionError(ERROR_FINGERPRINT_MISSING, "la resolución requiere resolution_fingerprint", "resolution_fingerprint", result.attempts)
    return result


def _resolution(
    *,
    media_type: str,
    media_path: str,
    media_url: str,
    media_source: str,
    media_source_url: str,
    method: str,
    rights: str,
    alt_text: str,
    level: int,
    payload: dict[str, Any],
) -> MediaResolution:
    return MediaResolution(
        media_status=MEDIA_STATUS_RESOLVED,
        media_type=media_type,
        media_path=media_path,
        media_url=media_url,
        media_source=media_source,
        media_source_url=media_source_url,
        media_method=method,
        media_rights_status=rights,
        alt_text=alt_text,
        resolver_version=RESOLVER_VERSION,
        fallback_level=level,
        resolution_fingerprint=_fingerprint(method, payload),
        acquisition_payload=payload,
    )


def _resolve_official_image(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
    del attempts
    url = clean(candidate.get("official_image_url"))
    if not url:
        return StrategyResult(None, OUTCOME_MISSING, "official_image_url ausente")
    if not _is_https_url(url):
        return StrategyResult(None, OUTCOME_INVALID_URL, "official_image_url debe ser HTTPS", url)
    rights = clean(candidate.get("official_image_rights"))
    if rights != RIGHTS_VERIFIED:
        return StrategyResult(None, OUTCOME_RIGHTS_UNVERIFIED, "official_image_rights debe ser VERIFICADO", url)
    source = clean(candidate.get("official_image_source") or candidate.get("official_source") or candidate.get("source_name"))
    if not source:
        return StrategyResult(None, OUTCOME_SOURCE_MISSING, "imagen oficial sin provenance de fuente", url)
    source_url = clean(candidate.get("official_image_source_url") or url)
    if source_url and not _is_https_url(source_url):
        return StrategyResult(None, OUTCOME_SOURCE_URL_INVALID, "official_image_source_url debe ser HTTPS", url)
    alt_text = factual_alt_text(MEDIA_METHOD_OFFICIAL_IMAGE, candidate, clean(candidate.get("official_image_alt")))
    if not alt_text:
        return StrategyResult(None, OUTCOME_ALT_TEXT_MISSING, "imagen oficial sin alt factual ni título", url)
    media_type = clean(candidate.get("official_image_type") or "image")
    payload = {
        "kind": "remote_image",
        "url": url,
        "source": source,
        "source_url": source_url,
        "rights": rights,
        "alt_text": alt_text,
        "declared_media_type": media_type,
    }
    return StrategyResult(
        _resolution(
            media_type=media_type,
            media_path="",
            media_url=url,
            media_source=source,
            media_source_url=source_url,
            method=MEDIA_METHOD_OFFICIAL_IMAGE,
            rights=RIGHTS_VERIFIED,
            alt_text=alt_text,
            level=1,
            payload=payload,
        ),
        OUTCOME_RESOLVED,
        "imagen oficial explícita con derechos y provenance verificados",
        url,
    )


def _resolve_structured_asset(candidate: dict[str, Any], *, method: str, prefix: str) -> StrategyResult:
    url = clean(candidate.get(f"{prefix}_url"))
    if not url:
        return StrategyResult(None, OUTCOME_MISSING, f"{prefix}_url ausente")
    if not _is_https_url(url):
        return StrategyResult(None, OUTCOME_INVALID_URL, f"{prefix}_url debe ser HTTPS", url)
    rights = clean(candidate.get(f"{prefix}_rights"))
    if rights != RIGHTS_VERIFIED:
        return StrategyResult(None, OUTCOME_RIGHTS_UNVERIFIED, f"{prefix}_rights debe ser VERIFICADO", url)
    source = clean(candidate.get(f"{prefix}_source") or candidate.get("official_source") or candidate.get("source_name"))
    if not source:
        return StrategyResult(None, OUTCOME_SOURCE_MISSING, f"{prefix} sin provenance de fuente", url)
    source_url = clean(candidate.get(f"{prefix}_source_url") or url)
    if source_url and not _is_https_url(source_url):
        return StrategyResult(None, OUTCOME_SOURCE_URL_INVALID, f"{prefix}_source_url debe ser HTTPS", url)
    alt_text = factual_alt_text(method, candidate, clean(candidate.get(f"{prefix}_alt")))
    if not alt_text:
        return StrategyResult(None, OUTCOME_ALT_TEXT_MISSING, f"{prefix} sin alt factual ni título", url)
    media_type = clean(candidate.get(f"{prefix}_type") or "image")
    payload = {
        "kind": "remote_image",
        "url": url,
        "source": source,
        "source_url": source_url,
        "rights": rights,
        "alt_text": alt_text,
        "declared_media_type": media_type,
    }
    return StrategyResult(
        _resolution(
            media_type=media_type,
            media_path="",
            media_url=url,
            media_source=source,
            media_source_url=source_url,
            method=method,
            rights=RIGHTS_VERIFIED,
            alt_text=alt_text,
            level=2,
            payload=payload,
        ),
        OUTCOME_RESOLVED,
        f"{prefix} explícita con derechos y provenance verificados",
        url,
    )


def _resolve_explicit_cover(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
    del attempts
    return _resolve_structured_asset(candidate, method=MEDIA_METHOD_EXPLICIT_COVER, prefix="cover")


def _resolve_explicit_thumbnail(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
    del attempts
    return _resolve_structured_asset(candidate, method=MEDIA_METHOD_EXPLICIT_THUMBNAIL, prefix="thumbnail")


def _resolve_official_landing_capture(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
    del attempts
    url = clean(candidate.get("official_landing_url") or candidate.get("source_url") or candidate.get("access_url"))
    if not url:
        return StrategyResult(None, OUTCOME_MISSING, "landing oficial ausente")
    if not _is_https_url(url):
        return StrategyResult(None, OUTCOME_INVALID_URL, "landing oficial debe ser HTTPS", url)
    alt_text = factual_alt_text(MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE, candidate)
    if not alt_text:
        return StrategyResult(None, OUTCOME_ALT_TEXT_MISSING, "captura oficial requiere título factual", url)
    source = clean(candidate.get("official_landing_source") or candidate.get("official_source") or candidate.get("source_name") or urlparse(url).netloc)
    if not source:
        return StrategyResult(None, OUTCOME_SOURCE_MISSING, "landing oficial sin provenance de fuente", url)
    payload = {
        "kind": "landing_capture",
        "capture_policy_version": CAPTURE_POLICY_VERSION,
        "url": url,
        "source": source,
        "viewport": "1200x1500",
        "virtual_time_budget_ms": 5000,
        "alt_text": alt_text,
    }
    digest = _canonical_hash(payload)[:16]
    media_path = _asset_path(candidate, "landing", digest, "png")
    payload["media_path"] = media_path
    return StrategyResult(
        _resolution(
            media_type="image/png",
            media_path=media_path,
            media_url="",
            media_source=source,
            media_source_url=url,
            method=MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
            rights=RIGHTS_OFFICIAL_CAPTURE,
            alt_text=alt_text,
            level=3,
            payload=payload,
        ),
        OUTCOME_RESOLVED,
        "landing oficial HTTPS seleccionada para captura determinista",
        url,
    )


def _parse_points(candidate: dict[str, Any]) -> list[Any] | None:
    raw = candidate.get("data_points_json")
    if isinstance(raw, str):
        if not clean(raw):
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("data_points_json no es JSON válido")
        return parsed if isinstance(parsed, list) else []
    if isinstance(raw, list):
        return raw
    points = candidate.get("data_points")
    return points if isinstance(points, list) else None


def _resolve_deterministic_chart(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
    del attempts
    if clean(candidate.get("content_type")) != "dataset_grafica":
        return StrategyResult(None, OUTCOME_NOT_APPLICABLE, "content_type no es dataset_grafica")
    try:
        points = _parse_points(candidate)
    except ValueError as exc:
        return StrategyResult(None, OUTCOME_INVALID_DATA, str(exc))
    if points is None:
        return StrategyResult(None, OUTCOME_MISSING, "datos estructurados ausentes")
    if len(points) < 2:
        return StrategyResult(None, OUTCOME_INSUFFICIENT_DATA, "gráfica requiere al menos dos observaciones")
    title = clean(candidate.get("indicator_or_dataset") or candidate.get("title"))
    if not title:
        return StrategyResult(None, OUTCOME_METADATA_MISSING, "gráfica requiere indicador o título")
    source = _source_name(candidate)
    if not source:
        return StrategyResult(None, OUTCOME_SOURCE_MISSING, "gráfica requiere fuente verificada")
    source_url = clean(candidate.get("source_url") or candidate.get("access_url"))
    if source_url and not _is_https_url(source_url):
        source_url = ""
    alt_text = factual_alt_text(MEDIA_METHOD_DETERMINISTIC_CHART, candidate)
    payload = {
        "kind": "deterministic_chart",
        "renderer_version": CHART_RENDERER_VERSION,
        "title": title,
        "geography": clean(candidate.get("geography")),
        "source": source,
        "points": points,
        "alt_text": alt_text,
    }
    digest = _canonical_hash(payload)[:16]
    media_path = _asset_path(candidate, "chart", digest, "svg")
    payload["media_path"] = media_path
    return StrategyResult(
        _resolution(
            media_type="image/svg+xml",
            media_path=media_path,
            media_url="",
            media_source="CLEP deterministic chart",
            media_source_url=source_url,
            method=MEDIA_METHOD_DETERMINISTIC_CHART,
            rights=RIGHTS_OWN_DETERMINISTIC,
            alt_text=alt_text,
            level=4,
            payload=payload,
        ),
        OUTCOME_RESOLVED,
        "dataset con datos suficientes planificado como gráfica CLEP determinista",
        source_url,
    )


def _resolve_deterministic_card(candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]) -> StrategyResult:
    del attempts
    content_type = clean(candidate.get("content_type") or "recurso")
    title = clean(candidate.get("title") or candidate.get("indicator_or_dataset"))
    if not title:
        return StrategyResult(None, OUTCOME_METADATA_MISSING, "tarjeta CLEP requiere título factual")
    source = _source_name(candidate)
    if not source:
        return StrategyResult(None, OUTCOME_SOURCE_MISSING, "tarjeta CLEP requiere fuente verificada")
    label = CARD_LABELS.get(content_type, "CLEP")
    metadata = " · ".join(
        part
        for part in (
            clean(candidate.get("authors")),
            clean(candidate.get("geography")),
            _year(candidate),
        )
        if part
    )
    source_url = clean(candidate.get("source_url") or candidate.get("access_url"))
    if source_url and not _is_https_url(source_url):
        source_url = ""
    alt_text = factual_alt_text(MEDIA_METHOD_DETERMINISTIC_CARD, candidate)
    payload = {
        "kind": "deterministic_card",
        "renderer_version": CARD_RENDERER_VERSION,
        "label": label,
        "title": title,
        "meta": metadata,
        "source": source,
        "alt_text": alt_text,
    }
    digest = _canonical_hash(payload)[:16]
    media_path = _asset_path(candidate, "card", digest, "svg")
    payload["media_path"] = media_path
    return StrategyResult(
        _resolution(
            media_type="image/svg+xml",
            media_path=media_path,
            media_url="",
            media_source="CLEP deterministic card",
            media_source_url=source_url,
            method=MEDIA_METHOD_DETERMINISTIC_CARD,
            rights=RIGHTS_OWN_DETERMINISTIC,
            alt_text=alt_text,
            level=4,
            payload=payload,
        ),
        OUTCOME_RESOLVED,
        "fallback factual planificado como tarjeta CLEP determinista",
        source_url,
    )


STRATEGIES: dict[str, Strategy] = {
    MEDIA_METHOD_OFFICIAL_IMAGE: _resolve_official_image,
    MEDIA_METHOD_EXPLICIT_COVER: _resolve_explicit_cover,
    MEDIA_METHOD_EXPLICIT_THUMBNAIL: _resolve_explicit_thumbnail,
    MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE: _resolve_official_landing_capture,
    MEDIA_METHOD_DETERMINISTIC_CHART: _resolve_deterministic_chart,
    MEDIA_METHOD_DETERMINISTIC_CARD: _resolve_deterministic_card,
}


def resolve_media(
    candidate: dict[str, Any],
    rejected_methods: dict[str, str] | None = None,
) -> MediaResolution:
    """Decide una estrategia sin efectos laterales.

    `rejected_methods` permite informar fallos de adquisición ya observados.
    El caller no decide el siguiente fallback: el resolver vuelve a aplicar la
    jerarquía y registra esos métodos como ACQUISITION_FAILED.
    """
    if not isinstance(candidate, dict):
        raise MediaResolutionError(ERROR_CANDIDATE_INVALID, "candidate debe ser un diccionario", "candidate")
    rejected = dict(rejected_methods or {})
    unknown = set(rejected) - ALLOWED_MEDIA_METHODS
    if unknown:
        raise MediaResolutionError(
            ERROR_METHOD_INVALID,
            f"rejected_methods contiene métodos desconocidos: {sorted(unknown)!r}",
            "rejected_methods",
        )

    attempts: list[MediaAttempt] = []
    for level, method in MEDIA_HIERARCHY:
        if method in rejected:
            attempts.append(
                MediaAttempt(
                    level,
                    method,
                    False,
                    OUTCOME_ACQUISITION_FAILED,
                    clean(rejected[method]) or "adquisición fallida previamente",
                    "",
                )
            )
            continue

        strategy = STRATEGIES.get(method)
        if strategy is None:
            raise MediaResolutionError(ERROR_METHOD_INVALID, f"estrategia no registrada: {method}", "media_method", tuple(attempts))
        try:
            result = strategy(candidate, tuple(attempts))
        except MediaResolutionError:
            raise
        except Exception as exc:
            raise MediaResolutionError(
                ERROR_STRATEGY_ERROR,
                f"fallo interno en {method}: {type(exc).__name__}: {exc}",
                attempts=tuple(attempts),
            ) from exc

        if result.resolution is not None:
            if result.outcome != OUTCOME_RESOLVED:
                raise MediaResolutionError(
                    ERROR_STRATEGY_ERROR,
                    f"{method} devolvió resolución con outcome={result.outcome!r}",
                    attempts=tuple(attempts),
                )
            selected = MediaAttempt(level, method, True, OUTCOME_RESOLVED, result.reason, result.source_url)
            final = result.resolution
            return validate_resolution(
                MediaResolution(
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
                    acquisition_payload=dict(final.acquisition_payload),
                    attempts=tuple([*attempts, selected]),
                )
            )

        if result.outcome not in FALLBACK_OUTCOMES:
            raise MediaResolutionError(
                ERROR_STRATEGY_ERROR,
                f"{method} devolvió outcome desconocido/no recuperable: {result.outcome!r}",
                attempts=tuple(attempts),
            )
        attempts.append(MediaAttempt(level, method, False, result.outcome, result.reason, result.source_url))

    detail = "; ".join(f"L{attempt.level}:{attempt.method}={attempt.outcome}" for attempt in attempts)
    raise MediaResolutionError(
        ERROR_RESOLUTION_FAILED,
        "ninguna estrategia produjo una resolución" + (f" ({detail})" if detail else ""),
        attempts=tuple(attempts),
    )
