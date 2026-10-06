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
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from generar_grafica_clep import render as render_chart
from generar_tarjeta_clep import render as render_card

ROOT = Path(__file__).resolve().parents[2]
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


class MediaResolutionError(ValueError):
    """Error estructurado y fail-closed de resolución de media."""

    def __init__(self, code: str, detail: str, field_name: str = ""):
        self.code = code
        self.detail = detail
        self.field = field_name
        super().__init__(f"{code}: {detail}")


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
    return StrategyResult(
        MediaResolution(
            MEDIA_STATUS_RESOLVED,
            media_type,
            "",
            url,
            source,
            source_url,
            MEDIA_METHOD_OFFICIAL_IMAGE,
            RIGHTS_VERIFIED,
            alt_text,
            RESOLVER_VERSION,
            1,
            _fingerprint(MEDIA_METHOD_OFFICIAL_IMAGE, payload),
        ),
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
    url = clean(candidate.get(f"{prefix}_url"))
    if not url:
        return StrategyResult(None, "MISSING", f"{prefix}_url ausente")
    if not _is_https_url(url):
        return StrategyResult(None, "INVALID_URL", f"{prefix}_url debe ser HTTPS", url)

    rights = clean(candidate.get(f"{prefix}_rights"))
    if rights != RIGHTS_VERIFIED:
        return StrategyResult(None, "RIGHTS_UNVERIFIED", f"{prefix}_rights debe ser VERIFICADO", url)

    source = clean(
        candidate.get(f"{prefix}_source")
        or candidate.get("official_source")
        or candidate.get("source_name")
    )
    if not source:
        return StrategyResult(None, "SOURCE_MISSING", f"{prefix} sin provenance de fuente", url)

    source_url = clean(candidate.get(f"{prefix}_source_url") or url)
    if source_url and not _is_https_url(source_url):
        return StrategyResult(None, "SOURCE_URL_INVALID", f"{prefix}_source_url debe ser HTTPS", url)

    title = clean(candidate.get("title") or candidate.get("indicator_or_dataset"))
    alt_text = clean(candidate.get(f"{prefix}_alt")) or (f"{default_label}: {title}" if title else "")
    if not alt_text:
        return StrategyResult(None, "ALT_TEXT_MISSING", f"{prefix} sin alt_text factual ni título", url)

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
        MediaResolution(
            MEDIA_STATUS_RESOLVED,
            media_type,
            "",
            url,
            source,
            source_url,
            method,
            RIGHTS_VERIFIED,
            alt_text,
            RESOLVER_VERSION,
            2,
            _fingerprint(method, payload),
        ),
        "RESOLVED",
        f"{prefix} explícita con derechos y provenance verificados",
        url,
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
    del attempts
    url = clean(
        candidate.get("official_landing_url")
        or candidate.get("source_url")
        or candidate.get("access_url")
    )
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
        MediaResolution(
            MEDIA_STATUS_RESOLVED,
            "image/png",
            media_path,
            "",
            source,
            url,
            MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE,
            RIGHTS_OFFICIAL_CAPTURE,
            alt_text,
            RESOLVER_VERSION,
            3,
            _fingerprint(MEDIA_METHOD_OFFICIAL_LANDING_CAPTURE, payload),
        ),
        "RESOLVED",
        "landing oficial HTTPS seleccionada para captura determinista",
        url,
    )


def _resolve_deterministic_chart(
    candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]
) -> StrategyResult:
    del attempts
    content_type = clean(candidate.get("content_type"))
    if content_type != "dataset_grafica":
        return StrategyResult(None, "NOT_APPLICABLE", "content_type no es dataset_grafica")

    raw = candidate.get("data_points_json")
    if isinstance(raw, str):
        if not clean(raw):
            return StrategyResult(None, "MISSING", "data_points_json ausente")
        try:
            points = json.loads(raw)
        except Exception:
            return StrategyResult(None, "INVALID_DATA", "data_points_json no es JSON válido")
    elif isinstance(raw, list):
        points = raw
    else:
        points = candidate.get("data_points")
        if not isinstance(points, list):
            return StrategyResult(None, "MISSING", "datos estructurados ausentes")

    if len(points) < 2:
        return StrategyResult(None, "INSUFFICIENT_DATA", "gráfica requiere al menos dos observaciones")

    title = clean(candidate.get("indicator_or_dataset") or candidate.get("title"))
    if not title:
        return StrategyResult(None, "METADATA_MISSING", "gráfica requiere indicador o título")
    source = _source_name(candidate)
    if not source:
        return StrategyResult(None, "SOURCE_MISSING", "gráfica requiere fuente verificada")

    chart_input = {
        "title": title,
        "geography": clean(candidate.get("geography")),
        "source": source,
        "points": points,
    }
    try:
        svg = render_chart(chart_input)
    except Exception as exc:
        return StrategyResult(None, "INVALID_DATA", f"datos no renderizables: {exc}")

    svg_sha256 = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    svg_digest = svg_sha256[:16]
    candidate_id = clean(candidate.get("candidate_id"))
    stem = candidate_id or svg_digest
    media_path = f"data/editorial/media/{stem}-chart-{svg_digest}.svg"
    out = ROOT / media_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")

    source_url = clean(candidate.get("source_url") or candidate.get("access_url"))
    if source_url and not _is_https_url(source_url):
        source_url = ""
    alt_text = f"Gráfica CLEP: {title}"
    payload = {
        "content_type": content_type,
        "title": title,
        "geography": chart_input["geography"],
        "source": source,
        "points": points,
        "svg_sha256": svg_sha256,
        "media_path": media_path,
    }
    return StrategyResult(
        MediaResolution(
            MEDIA_STATUS_RESOLVED,
            "image/svg+xml",
            media_path,
            "",
            "CLEP deterministic chart",
            source_url,
            MEDIA_METHOD_DETERMINISTIC_CHART,
            RIGHTS_OWN_DETERMINISTIC,
            alt_text,
            RESOLVER_VERSION,
            4,
            _fingerprint(MEDIA_METHOD_DETERMINISTIC_CHART, payload),
        ),
        "RESOLVED",
        "dataset con datos suficientes renderizado como gráfica CLEP determinista",
        source_url,
    )


def _resolve_deterministic_card(
    candidate: dict[str, Any], attempts: tuple[MediaAttempt, ...]
) -> StrategyResult:
    """Fallback universal factual y determinista."""
    del attempts
    content_type = clean(candidate.get("content_type") or "recurso")
    title = clean(candidate.get("title") or candidate.get("indicator_or_dataset"))
    if not title:
        return StrategyResult(None, "METADATA_MISSING", "tarjeta CLEP requiere título factual")

    source = _source_name(candidate)
    if not source:
        return StrategyResult(None, "SOURCE_MISSING", "tarjeta CLEP requiere fuente verificada")

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
    card_input = {
        "label": label,
        "title": title,
        "meta": metadata,
        "source": source,
    }
    try:
        svg = render_card(card_input)
    except Exception as exc:
        return StrategyResult(None, "METADATA_INVALID", f"tarjeta no renderizable: {exc}")

    svg_sha256 = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    svg_digest = svg_sha256[:16]
    candidate_id = clean(candidate.get("candidate_id"))
    stem = candidate_id or svg_digest
    media_path = f"data/editorial/media/{stem}-card-{svg_digest}.svg"
    out = ROOT / media_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")

    source_url = clean(candidate.get("source_url") or candidate.get("access_url"))
    if source_url and not _is_https_url(source_url):
        source_url = ""
    alt_text = f"Tarjeta CLEP: {title}"
    payload = {
        "content_type": content_type,
        "label": label,
        "title": title,
        "meta": metadata,
        "source": source,
        "svg_sha256": svg_sha256,
        "media_path": media_path,
    }
    return StrategyResult(
        MediaResolution(
            MEDIA_STATUS_RESOLVED,
            "image/svg+xml",
            media_path,
            "",
            "CLEP deterministic card",
            source_url,
            MEDIA_METHOD_DETERMINISTIC_CARD,
            RIGHTS_OWN_DETERMINISTIC,
            alt_text,
            RESOLVER_VERSION,
            4,
            _fingerprint(MEDIA_METHOD_DETERMINISTIC_CARD, payload),
        ),
        "RESOLVED",
        "fallback factual renderizado como tarjeta CLEP determinista",
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


def resolve_media(candidate: dict[str, Any]) -> MediaResolution:
    """Evalúa las fuentes en orden estricto y devuelve la primera resolución válida."""
    if not isinstance(candidate, dict):
        raise MediaResolutionError(
            "MEDIA_CANDIDATE_INVALID",
            "candidate debe ser un diccionario",
            "candidate",
        )

    attempts: list[MediaAttempt] = []
    for level, method in MEDIA_HIERARCHY:
        result = STRATEGIES[method](candidate, tuple(attempts))
        if result.resolution is not None:
            selected_attempt = MediaAttempt(
                level,
                method,
                True,
                result.outcome or "RESOLVED",
                result.reason,
                result.source_url,
            )
            final = result.resolution
            return validate_resolution(
                MediaResolution(
                    final.media_status,
                    final.media_type,
                    final.media_path,
                    final.media_url,
                    final.media_source,
                    final.media_source_url,
                    method,
                    final.media_rights_status,
                    final.alt_text,
                    RESOLVER_VERSION,
                    level,
                    final.resolution_fingerprint,
                    tuple([*attempts, selected_attempt]),
                )
            )

        attempts.append(
            MediaAttempt(
                level,
                method,
                False,
                result.outcome or "SKIPPED",
                result.reason,
                result.source_url,
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
