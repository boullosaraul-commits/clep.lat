# Auditoría previa · 31 de octubre de 2026

Base inspeccionada: `d49c37bf4a4dabe62cc63a7f479e8b70082fc2b7` en main. Inventario completo: 154 archivos versionados. No había docs/ ni AGENTS.md. Raíces: .github/workflows, data/editorial, dist, recovery, scripts/editorial, tests y README.md. Se inspeccionaron README, todas las páginas institucionales, recursos compartidos, sitemap, robots, workflows y rutas de escritura de los scripts.

## Arquitectura y referencia institucional

Sitio estático sin generador ni dependencias frontend declaradas. `dist/` contiene 16 páginas indexables, 404 y recursos compartidos CSS/JS/favicon. Universidad Abierta tiene ocho áreas temáticas. README conserva la descripción alfa y menciona cuatro páginas curriculares, cifra ya desactualizada.

La portada (`c58d933`) incorpora Qué hacemos; esa página fue introducida en `d941627`. Ambas comparten wordmark tipográfico, topline con dominio, siete enlaces de navegación y pie completo. Se adoptan como referencia institucional, no como nueva identidad visual. Actividades, Comunidad y Publicaciones aún usan `.mark` (sin definición en el CSS actual), topline anterior y navegación sin Qué hacemos. Otras páginas usan wordmark actualizado, pero omiten Qué hacemos en cabecera/pie. 404 carece de botón móvil aunque su navegación se oculta en móvil.

Portada y Qué hacemos tienen canonical y Open Graph; otras páginas carecen de esos metadatos. Sitemap contiene las 16 rutas indexables existentes, sin propuestas 2027. Robots apunta al sitemap correcto. El menú móvil usa CSS a 650 px y JS para alternar `.open`/aria-expanded; falta relación aria-controls y cierre con Escape. Siete enlaces más marca pueden exigir menú antes de 650 px: se verificará el comportamiento conservando el diseño.

## Automatismos

Se revisaron los 12 workflows. Ingesta, traducción, planificación, preparación de sinopsis, publicación Facebook y recuperación histórica escriben datos editoriales/estado/media; los commits automatizados se limitan a esas rutas. CI y verificaciones no publican docs. No hay workflow de despliegue del sitio en el repositorio ni conversión docs → dist. El proveedor externo debe conservar `dist/` como raíz; su configuración no está acreditada por archivos de este repositorio. No se añaden iniciativas a colas ni se ejecutan operaciones Meta.

## Contenido que se conserva

Actividades ya describe un piloto del Tratado sobre el dinero. No se elimina, fecha, cancela ni sustituye: su relación con el círculo propuesto exige decisión. Publicaciones contiene una revista proyectada; no se convierte en revista operativa. Se conservarán íntegros los bloques main de todas las páginas, recursos y datos históricos/editoriales.

## Línea base de tests

Antes de modificar dist: `python -m unittest discover -s tests -p 'test_*.py'` ejecutó 257 tests: 252 correctos y 5 fallos en EditorialPriorityTests de test_editorial.py: bounded_recent_stream_can_supply_freshness, latin_america_does_not_imply_pluralism, outstanding_score_is_reachable, pluralist_non_latin_work_gets_pluralism_points y relevance_and_editorial_priority_are_separate. Todos devuelven puntuación 0 o eligibilidad fallida donde la prueba espera prioridad positiva. No se alterará esa lógica editorial ajena a esta tarea.
