# De propuesta a información pública

Procedimiento propuesto para ratificación CLEP. No crea aprobaciones por sí mismo.

1. Registrar en `decisiones.md` la propuesta, su alcance y cuestiones pendientes; deliberar en CLEP y conservar minuta o acta fechada.
2. Verificar pregunta, programa, responsables que acepten, capacidad y recursos, calendario, modalidad, sede o plataforma y condiciones de acceso. Confirmar permisos y aceptación de colaboraciones e invitados antes de nombrarlos.
3. Registrar el acuerdo y su evidencia. Una aprobación parcial no confirma los componentes pendientes; DEPENDENCIA EXTERNA no se resuelve con una expectativa.
4. Preparar una ficha pública desde los datos aprobados. Mantener el documento interno y enlazar desde él la decisión y el commit de publicación: no mover ni borrar la memoria deliberativa.
5. Crear manualmente la ruta correspondiente usando el encabezado, navegación, pie y metadatos de la plantilla institucional de portada/Qué hacemos. Las rutas previstas, **todavía inexistentes**, son `/actividades/circulo-monetario-2027/`, `/actividades/kalecki-2027/` y `/actividades/godley-20-30/`. El sitio estático admite esas carpetas sin nuevo sistema de rutas; no necesita placeholders públicos.
6. Revisar texto y enlaces, navegación móvil, canonical y og:url propios, accesibilidad y sitemap. Añadir la actividad a `/actividades/` y sitemap sólo al publicar. Crear marcado Event únicamente con datos confirmados y coherentes con el texto visible.
7. Commit separado con referencia a la decisión. Publicar mediante el despliegue existente de `dist/`; verificar el resultado y registrar enlace, versión y cambios posteriores.

No hay conversión automática de Markdown de `docs/` a HTML. Mantener `docs/` fuera de entradas del pipeline editorial, sus colas, anuncios y artefactos de despliegue. Si se introduce un generador, deberá preservar explícitamente esa exclusión. Un cambio de sede, fecha o estado requiere actualizar la ficha y conservar la decisión previa.
