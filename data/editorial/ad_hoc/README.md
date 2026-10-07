# Entrada ad hoc desde chat

Este directorio es la frontera durable para solicitudes editoriales creadas desde ChatGPT u otra interfaz manual.

Cada solicitud es un archivo JSON independiente. El archivo es inmutable y trazable; `scripts/editorial/ingestar_ad_hoc.py` lo valida como candidato canónico schema v1 y lo adapta al `candidatos.csv` operacional que consume el pipeline actual.

## Mínimo

```json
{
  "title": "Título factual",
  "content_type": "PAPER",
  "access_url": "https://example.org/recurso"
}
```

`content_type` puede ser: `PAPER`, `BOOK`, `CHAPTER`, `REPORT`, `POLICY_BRIEF`, `SPECIAL_ISSUE`, `THESIS`, `EDITION_TRANSLATION`, `DATASET`, `CHART`, `EVENT`, `CALL`, `VIDEO` o `RESOURCE`.

`TEACHING_MATERIAL` e `INSTITUTIONAL` permanecen bloqueados hasta que exista un adaptador textual productivo específico.

Campos opcionales útiles: `authors`, `summary`, `summary_es`, `publication_year`, `language`, `venue`, `source_name`, `source_url`, `doi`, `area_clep`, `notes`, `indicator_or_dataset`, `geography`, `reference_period`, `value_or_change`, `organizer`, `date_or_deadline`, `speaker_or_organization`.

## Reglas

- la URL de acceso debe ser HTTPS;
- el `candidate_id` se deriva de forma determinista de título + URL si no se proporciona;
- la solicitud entra como `origin=CHAT`, `flow_type=AD_HOC` y `candidate_status=DISCOVERED`;
- **no** entra directamente como publicable: pasa por evaluación, acceso/OA, prioridad, preparación y verificación ordinarias;
- reingestar el mismo archivo es idempotente;
- un `candidate_id` ya existente con título o URL distintos falla en cerrado.

Ejemplo de nombre: `2026-10-07-paper-kalecki.json`.
