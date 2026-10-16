# CLEP · Alfa 0.1

Paquete estático para una primera versión pública del Colectivo Latinoamericano de Economía Pluralista.

## Contenido

- `dist/`: sitio listo para desplegar como sitio estático.
- Inicio, manifiesto, comunidad, actividades, Universidad Abierta, cuatro páginas curriculares, publicaciones y participación.
- CSS, JavaScript, favicon, `robots.txt` y `sitemap.xml`.

## Vista local

Desde esta carpeta:

```sh
python3 -m http.server 8000 --directory dist
```

Abre `http://localhost:8000`.

## Despliegue

Publica el contenido de `dist/` como raíz de un sitio estático (por ejemplo, Cloudflare Pages). Las rutas están preparadas para el dominio raíz `clep.lat`.

## Nota editorial

La agenda, la Universidad Abierta y el catálogo de publicaciones se presentan como infraestructura en desarrollo. El sitio no inventa actividades confirmadas, cursos disponibles ni cargos o grupos institucionales.

## Paper synopses

`sinopsis_papers.py` adds a Spanish editorial synopsis derived only from the retrieved abstract. It records the source hash, exact supporting excerpts, model and method. A synopsis is not presented as the authors' original abstract or as a reading of the full paper. Spanish extracts remain explicitly labelled as extracts.

The daily and ingest workflows run synthesis before preparation. The dedicated `paper-synopsis.yml` workflow can also refresh unpublished content without making Meta calls. Configure the repository Actions secret `OPENAI_API_KEY` to enable ongoing model synthesis; optional variable `CLEP_SYNOPSIS_MODEL` defaults to `gpt-4.1-mini`. Each execution attempts at most 12 eligible papers. Existing source-matching results are reused, changed sources invalidate them, and API failures do not discard other candidates. Without the secret, the job reports that model synthesis is inactive and uses only source-checked initial synopses or usable Spanish abstracts.

Cards for papers with a synopsis use a turquoise editorial layout containing the title, authors, source and a synopsis excerpt. Existing published Meta posts are preserved. This update does not automatically edit their text or replace their images.
