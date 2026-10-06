#!/usr/bin/env python3
"""Contrato de traducción textual CLEP.

Este módulo NO genera traducciones. Recibe una traducción producida por un
motor automático no generativo y valida su provenance antes de que pueda ser
consumida por el renderer editorial.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class TranslationError(ValueError):
    def __init__(self, code: str, detail: str, field: str = ""):
        self.code = code
        self.detail = detail
        self.field = field
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class TranslationRecord:
    text: str
    status: str
    method: str
    engine: str
    engine_version: str
    source_language: str
    target_language: str
    disclosure: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def validate_translation(text: str, metadata: dict[str, Any]) -> TranslationRecord:
    translated = clean(text)
    if not translated:
        raise TranslationError("TRANSLATION_TEXT_MISSING", "traducción vacía", "source_summary_es")

    values = {
        "status": clean(metadata.get("translation_status")),
        "method": clean(metadata.get("translation_method")),
        "engine": clean(metadata.get("translation_engine")),
        "engine_version": clean(metadata.get("translation_engine_version")),
        "source_language": clean(metadata.get("source_language")),
        "target_language": clean(metadata.get("target_language") or "es"),
        "disclosure": clean(metadata.get("translation_disclosure") or metadata.get("translation_label")),
    }
    required = ("status", "method", "engine", "source_language", "target_language", "disclosure")
    missing = [field for field in required if not values[field]]
    if missing:
        raise TranslationError(
            "TRANSLATION_PROVENANCE_MISSING",
            "traducción presente sin provenance completo: " + ", ".join(missing),
            missing[0],
        )

    if values["status"].upper() not in {"VERIFIED", "COMPLETED"}:
        raise TranslationError(
            "TRANSLATION_NOT_VERIFIED",
            f"translation_status={values['status']!r}",
            "translation_status",
        )

    forbidden = ("generative", "llm", "gpt", "gemini", "claude")
    method_engine = (values["method"] + " " + values["engine"]).lower()
    if any(token in method_engine for token in forbidden):
        raise TranslationError(
            "GENERATIVE_TRANSLATION_FORBIDDEN",
            "CLEP sólo admite traducción automática no generativa en este flujo",
            "translation_method",
        )

    return TranslationRecord(text=translated, **values)
