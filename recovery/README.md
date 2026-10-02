# Recuperación del archivo histórico de CLEP

Este directorio convierte la recuperación local de Facebook y la reconstrucción bibliográfica en una parte reproducible del repositorio.

## Estado de referencia — 2026-10-02

### Attachments de Facebook

- publicaciones maestras: 1,974
- publicaciones sin `message`: 1,048
- consultas completadas: 1,048
- errores pendientes: 0
- posts con attachments: 1,040
- posts sin attachments: 8
- attachments/subattachments: 1,434
- URLs recuperadas: 4,278

Tipos principales: 966 `photo`, 192 `share`, 185 `native_templates`, 80 `album`, 8 `video_inline`, 3 `cover_photo`.

Los archivos locales producidos por la corrida son `attachments_posts.json`, `attachments_flat.csv`, `urls_attachments.csv`, `errores_attachments.csv` y `checkpoint.json`.

### Recuperación bibliográfica Crossref v2

Entrada: 561 fichas, 556 con título.

Última corrida:
- completados totales: 495
- pendientes: 61
- candidatos Crossref guardados: 28,697
- 61 fallos HTTP 429 en la corrida

Los HTTP 429 son fallos recuperables de rate limiting; no deben interpretarse como ausencia bibliográfica.

## Regla de arquitectura

El repositorio debe contener **código, configuración, esquemas, documentación y resultados editoriales normalizados**. Los dumps voluminosos, cachés de API, binarios e imágenes descargadas no se versionan directamente en Git.

Los datos recuperados deben conservar identificadores estables y procedencia suficiente para regenerar los resultados.

## Migración desde el trabajo local

Scripts locales a incorporar conservando su lógica exacta:
- `descargar_clep.py`
- `extraer_clep_attachments.py`
- `clep_recuperacion/preparar_recuperacion.py`
- `clep_recuperacion/extraer_fichas.py`
- `clep_recuperacion/clasificar_recursos.py`
- `clep_recuperacion/recuperar_bibliografia_v2.py`
- `clep_recuperacion/evaluar_bibliografia_completa_v31.py`

No se reescriben desde memoria: se importan desde los archivos locales para preservar el comportamiento ya probado.

## Destino editorial

Los resultados verificados desembocan en `data/editorial/cola.csv` con `flujo_editorial=archivo_historico`. La campaña está anclada del 2026-10-02 al 2027-02-02 y usa escalones 6 → 4 → 3 → 2 → 1 → 0.
