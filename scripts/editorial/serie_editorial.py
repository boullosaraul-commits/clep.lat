"""Clasificación de la ficha y del activo a partir de su función editorial."""

from urllib.parse import urlsplit

RECOMMENDATIONS = "Recomendaciones CLEP"
PUBLICATIONS = "Publicaciones CLEP"
ACTIVITIES = "Actividades CLEP"
EXTERNAL_TYPES = {
    "paper", "book", "chapter", "report", "policy_brief", "special_issue",
    "thesis", "edition_translation", "dataset_grafica", "video", "recurso",
}


def editorial_series(row, kind):
    explicit = str(row.get("editorial_series") or "").strip()
    if kind == "convocatoria_evento" or explicit == ACTIVITIES or row.get("flujo_editorial") == "actividad_clep":
        return ACTIVITIES
    if explicit == PUBLICATIONS or row.get("source_type") == "clep_original" or row.get("flujo_editorial") == "publicacion_clep":
        return PUBLICATIONS
    # CLEP es fuente de la ficha institucional, incluso si la obra tiene autores externos.
    source = str(row.get("source_url") or row.get("access_url") or "")
    if urlsplit(source).hostname in {"clep.lat", "www.clep.lat"}:
        return PUBLICATIONS
    return RECOMMENDATIONS if kind in EXTERNAL_TYPES else ""
