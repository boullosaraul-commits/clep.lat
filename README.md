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
