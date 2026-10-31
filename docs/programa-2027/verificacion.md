# Verificación de implementación · 31 de octubre de 2026

## Alcance final

Se usa la plantilla institucional de portada/Qué hacemos en las 17 páginas HTML: topline, wordmark, siete enlaces en cabecera y pie, etiquetas de navegación y botón móvil relacionado con aria-controls. Se completan canonical y Open Graph en las páginas indexables. 404 conserva noindex y no recibe canonical de página válida. CSS mantiene identidad, colores y composición; adelanta el menú colapsado a 1100 px para acomodar los siete enlaces y añade foco visible. JS cierra con Escape (devolviendo foco), al navegar y al cambiar de breakpoint.

No hay páginas nuevas en dist, cambios de rutas, modificaciones de sitemap ni eventos 2027. Los 17 bloques main son idénticos, byte por byte, a la base auditada. No se elimina ningún archivo versionado ni contenido histórico/editorial. README corrige el recuento de áreas y enlaza al espacio de planificación.

## Comprobaciones

| Comprobación | Resultado |
| --- | --- |
| 384 referencias locales href/src, incluidos fragmentos | Correctas, sin destinos rotos |
| 16 rutas indexables, canonical y og:url | Coinciden exactamente con sitemap |
| Cabecera, pie y relaciones aria | Presentes en las 17 páginas |
| Propuestas 2027 en dist o sitemap | Ausentes |
| Comparación de los 17 bloques main con d49c37b | Idénticos |
| `node --check dist/assets/js/site.js` | Correcto |
| Prueba aislada de eventos JS | Apertura/cierre, Escape/foco, navegación y breakpoint correctos |
| `python -m compileall -q scripts recovery tests` | Correcto |
| `python -m unittest discover -s tests -p 'test_*.py'` | 257 tests, 252 correctos, mismos 5 fallos previos documentados en auditoría |
| text_renderer_e2e.py | Correcto |
| media_resolution_e2e.py | Correcto |
| preparation_e2e.py | Correcto |
| multiformat_preparation_e2e.py | Correcto |
| quarantine_adhoc_e2e.py | Correcto |
| editorial_e2e.py | Correcto; Meta simulado, sin publicaciones reales |
| `python scripts/editorial/verificar_cola.py` | 0 errores, 0 advertencias |
| `git diff --check` | Correcto |
| Revisión workflows | No escriben docs ni dist; no se modifican automatismos |

## Límites y pendientes técnicos

Vista previa servida por el servicio de Sites; portada y Actividades inspeccionadas en navegador a 1363 px, sin desbordamiento horizontal de cabecera. La API de este navegador no expone ajuste de viewport; no se afirma prueba visual móvil completada. Se revisaron las reglas responsive y la interacción del menú mediante prueba aislada, pero queda revisar visualmente en un dispositivo/ancho móvil. No se ejecutaron smoke tests con credenciales o publicaciones reales en Meta.

La configuración del proveedor que despliega clep.lat no está versionada aquí. El push de main acredita entrega del código, no por sí solo que el proveedor haya terminado de desplegar. Debe mantener dist como raíz y excluir docs. No se crea otra instancia de hosting ni se altera el proveedor existente.

## Pendientes para CLEP

Revisar documento maestro y briefing; acordar mecanismo de decisión y responsabilidades; delimitar círculo monetario y su relación con el piloto del Tratado; elegir escala y eventualmente fecha de Kalecki; evaluar viabilidad y fecha propuesta de Godley; ratificar el procedimiento de publicación. Mantener abierto 2027-II. Validar compromisos externos después de la reunión antes de anunciarlos.
