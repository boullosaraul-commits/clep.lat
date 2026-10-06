#!/usr/bin/env python3
"""E2E textual multiformato: candidato -> adaptador de preparación -> renderer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/editorial"))

from preparar_publicacion import meta_for, text_context
from renderizar_texto import render_result, supported_content_types


def candidate(kind):
    base = {
        "candidate_id": f"CAND-TEXT-{kind.upper()}",
        "content_type": kind,
        "title": f"Título de prueba {kind}",
        "authors": "A. Autora; B. Autor",
        "publication_year": "2026",
        "published_at": "2026-10-05",
        "access_url": f"https://example.org/{kind}",
        "source_url": f"https://example.org/{kind}",
        "source_name": "Fuente de prueba",
        "venue": "Serie de prueba",
        "language": "es",
        "summary": f"Descripción oficial en español para {kind}.",
    }
    if kind == "dataset_grafica":
        base.update({"indicator_or_dataset":"Tasa de empleo","geography":"México","reference_period":"2026","value_or_change":"61.2%"})
    elif kind == "convocatoria_evento":
        base.update({"organizer":"CLEP","date_or_deadline":"2026-10-20"})
    elif kind == "video":
        base.update({"speaker_or_organization":"A. Economista"})
    elif kind == "recurso":
        pass
    elif kind == "edition_translation":
        base["notes"] = "edition_event=revision | edition_number=2nd"
    return base


def main():
    kinds = set(supported_content_types())
    expected = {
        "paper","book","chapter","report","policy_brief","special_issue","thesis",
        "edition_translation","dataset_grafica","convocatoria_evento","video","recurso",
    }
    assert kinds == expected, (kinds, expected)

    outputs = {}
    for kind in sorted(kinds):
        row = candidate(kind)
        meta = meta_for(kind, row)
        meta.update(text_context(row))
        result = render_result(kind, meta)
        assert result.content_type == kind, result
        assert result.text_method == "deterministic_template", result
        assert result.text_status == "VERIFIED", result
        assert result.text_template, result
        assert result.text_template_version >= 1, result
        assert result.post_text, result
        assert result.editorial_description == row["summary"], result
        assert result.translation["present"] is False, result
        outputs[kind] = result.post_text

    # Determinismo cruzando otra vez exactamente las mismas entradas.
    for kind in sorted(kinds):
        row = candidate(kind)
        meta = meta_for(kind, row)
        meta.update(text_context(row))
        assert render_result(kind, meta).post_text == outputs[kind]

    # Flujo traducido: la descripción editorial usa sólo traducción con provenance.
    row = candidate("paper")
    row.update({
        "language":"en",
        "source_language":"en",
        "summary":"Official English abstract.",
        "summary_es":"Resumen traducido automáticamente.",
        "translation_status":"VERIFIED",
        "translation_method":"machine_translation",
        "translation_engine":"argos-translate",
        "translation_engine_version":"1.9",
        "translation_disclosure":"ES · Traducción automática",
    })
    meta = meta_for("paper", row)
    meta.update(text_context(row))
    translated = render_result("paper", meta)
    assert translated.editorial_description == "Resumen traducido automáticamente.", translated
    assert translated.translation["present"] is True, translated
    assert translated.translation["engine"] == "argos-translate", translated

    print(f"TEXT E2E OK: {len(kinds)} formatos + traducción trazable.")


if __name__ == "__main__":
    main()
