#!/usr/bin/env python3
"""Autoridad única de renderizado textual editorial CLEP.

Contrato:
- sin IA generativa;
- misma entrada + misma plantilla => misma salida;
- no inventa resúmenes, interpretación ni transiciones;
- separa fuente, traducción, descripción editorial y post final;
- falla cerrado ante tipo desconocido, metadata insuficiente o provenance inválido.

`render(kind, data) -> str` se conserva por compatibilidad. Consumidores nuevos
deben preferir `render_result(kind, data)` para obtener texto + provenance.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from traduccion_textual import TranslationError, TranslationRecord, validate_translation

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "data/editorial/plantillas.json"
CFG = ROOT / "data/editorial/programacion.json"

TEXT_METHOD = "deterministic_template"
TEXT_STATUS = "VERIFIED"
FACTUAL_FALLBACK_VERSION = 1


class TextRenderError(ValueError):
    """Error textual estructurado y fail-closed."""

    def __init__(self, code: str, detail: str, field: str = ""):
        self.code = code
        self.detail = detail
        self.field = field
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class TextRenderResult:
    content_type: str
    source_summary: str
    source_summary_es: str
    editorial_description: str
    post_text: str
    text_method: str
    text_template: str
    text_template_version: int
    text_status: str
    translation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _configs() -> tuple[dict[str, Any], dict[str, Any]]:
    templates = json.loads(TPL.read_text(encoding="utf-8"))
    program = json.loads(CFG.read_text(encoding="utf-8"))
    return templates, program["text_policy"]


def supported_content_types() -> tuple[str, ...]:
    templates, _ = _configs()
    return tuple(sorted(templates.get("textos_cortos", {})))


def _source_summary(data: dict[str, Any]) -> str:
    for key in ("source_summary", "summary", "abstract", "description"):
        value = clean(data.get(key))
        if value:
            return value
    return ""


def _source_summary_es(data: dict[str, Any]) -> str:
    for key in ("source_summary_es", "summary_es", "abstract_es", "description_es"):
        value = clean(data.get(key))
        if value:
            return value
    return ""


def _validated_translation(data: dict[str, Any], translated: str) -> TranslationRecord | None:
    if not translated:
        return None
    try:
        return validate_translation(translated, data)
    except TranslationError as exc:
        raise TextRenderError(exc.code, exc.detail, exc.field) from None


def factual_fallback(kind: str, data: dict[str, Any]) -> str:
    """Descripción factual mínima; nunca intenta resumir una obra."""
    d = {k: clean(v) for k, v in data.items()}
    title = d.get("title") or d.get("indicator_or_dataset")
    author = (
        d.get("authors")
        or d.get("authors_or_editors")
        or d.get("authors_or_institution")
        or d.get("speaker_or_organization")
        or d.get("organizer")
        or d.get("source")
        or d.get("official_source")
    )
    year = d.get("year") or d.get("reference_period") or d.get("date_or_deadline")
    source = d.get("source_or_series") or d.get("container_title") or d.get("institution") or d.get("journal")
    access = d.get("access_url")
    if not title or not access:
        missing = [name for name, value in (("title", title), ("access_url", access)) if not value]
        raise TextRenderError(
            "INSUFFICIENT_METADATA",
            "fallback factual requiere " + ", ".join(missing),
            missing[0],
        )
    bits = [f"{kind}: {title}"]
    if author:
        bits.append(author)
    if year:
        bits.append(year)
    if source:
        bits.append(source)
    bits.append(access)
    return " · ".join(bits)


def _editorial_description(kind: str, data: dict[str, Any], source: str, translated: str) -> str:
    # Jerarquía congelada: fuente oficial en español > traducción trazable > metadata factual.
    source_language = clean(data.get("source_language")).lower()
    if source and source_language in {"", "es", "spa", "spanish", "español"}:
        return source
    if translated:
        return translated
    return factual_fallback(kind, data)


def _render_template(kind: str, data: dict[str, Any]) -> tuple[str, str, int]:
    templates, policy = _configs()
    spec = templates.get("textos_cortos", {}).get(kind)
    if not spec:
        raise TextRenderError("TEMPLATE_MISSING", f"tipo sin plantilla: {kind}", "content_type")

    d = {k: clean(v) for k, v in data.items()}
    missing = [k for k in spec.get("required", []) if not d.get(k)]
    if missing:
        raise TextRenderError(
            "INSUFFICIENT_METADATA",
            "faltan metadatos obligatorios: " + ", ".join(missing),
            missing[0],
        )
    d.setdefault("date_label", "Fecha")
    try:
        body = spec["template"].format_map(d)
    except KeyError as exc:
        raise TextRenderError(
            "TEMPLATE_FIELD_MISSING",
            f"falta campo de plantilla: {exc.args[0]}",
            str(exc.args[0]),
        ) from None

    body = body.replace("\\\\n", "\n")
    text = (spec["label"] + "\n\n" + body).strip()
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if "\\\\n" in text:
        raise TextRenderError("TEMPLATE_ESCAPE_ERROR", "plantilla contiene saltos escapados literalmente")
    if len(text) > int(policy["max_chars"]):
        raise TextRenderError(
            "TEXT_OVERFLOW",
            f"texto excede máximo: {len(text)} > {policy['max_chars']}",
        )
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > int(policy["max_paragraphs"]):
        raise TextRenderError(
            "TEXT_TOO_MANY_PARAGRAPHS",
            f"demasiados párrafos: {len(paragraphs)} > {policy['max_paragraphs']}",
        )

    template_version = int(spec.get("version") or templates.get("version") or 1)
    template_id = clean(spec.get("id") or f"textos_cortos.{kind}")
    return text, template_id, template_version


def render_result(kind: str, data: dict[str, Any]) -> TextRenderResult:
    kind = clean(kind).lower()
    if not kind:
        raise TextRenderError("CONTENT_TYPE_MISSING", "content_type vacío", "content_type")

    source = _source_summary(data)
    translated = _source_summary_es(data)
    translation = _validated_translation(data, translated)
    description = _editorial_description(kind, data, source, translated)
    post_text, template_id, template_version = _render_template(kind, data)

    return TextRenderResult(
        content_type=kind,
        source_summary=source,
        source_summary_es=translated,
        editorial_description=description,
        post_text=post_text,
        text_method=TEXT_METHOD,
        text_template=template_id,
        text_template_version=template_version,
        text_status=TEXT_STATUS,
        translation=translation.to_dict() if translation else {"present": False},
    )


def render(kind: str, data: dict[str, Any]) -> str:
    """API legacy compatible: devuelve sólo el post final."""
    return render_result(kind, data).post_text


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("uso: renderizar_texto.py TIPO archivo.json")
    data = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(render_result(sys.argv[1], data).to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
