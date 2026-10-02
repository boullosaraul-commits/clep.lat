# Infraestructura editorial CLEP

Este directorio contiene el estado editorial estructurado de CLEP.

## Flujos

- `archivo_historico`: recuperación y reedición gradual del archivo.
- `novedad`: publicaciones bibliográficas nuevas.
- `recurso`: bases de datos, repositorios, observatorios, institutos y otros recursos.
- `actividad_clep`: actividades propias de CLEP.
- `publicacion_clep`: producción propia de CLEP.
- contenido no textual: actividades, convocatorias, recursos, videos, gráficas, materiales didácticos, efemérides y anuncios institucionales.

## Política diaria de transición

La capacidad inicial es independiente por bloque:

- hasta **6 históricos/día**;
- hasta **6 nuevos/día**;
- hasta **4 no-textos/día**.

Por tanto, el máximo potencial inicial es 16 publicaciones diarias. Son techos, no cuotas: no se publica para rellenar espacios.

El archivo histórico debe desaparecer como flujo extraordinario en aproximadamente cuatro meses. Su ritmo preferido sigue los escalones:

`6 → 4 → 3 → 2 → 1 → 0`

La transición no se fija sólo por calendario. El planificador debe considerar el backlog recuperable restante y la fecha objetivo, manteniendo o recuperando un escalón superior si reducirlo impediría terminar a tiempo.

Cada slot liberado por la reducción del archivo queda disponible para los flujos actuales, especialmente novedades y no-textos. El contenido actual tiene prioridad editorial.

## Programación

- zona horaria: `America/Mexico_City`;
- ventana ordinaria: 07:00–23:30;
- separación base mínima: 60 minutos;
- distribución a lo largo de todo el día;
- la configuración canónica vive en `data/editorial/programacion.json`.

## Cadena

`fuente → detección → evaluación → verificación → ficha → cola → programación Meta → Facebook`

Detectar un registro no equivale a aprobarlo. La aparición en RePEc/NEP tampoco demuestra acceso abierto legítimo.

## Seguridad

Los secretos de Meta no deben almacenarse en el repositorio. El workflow de Facebook usa GitHub Actions Secrets (`CLEP_FB_TOKEN` y `CLEP_FB_PAGE_ID`).


## Política de no uso de IA generativa

El pipeline editorial de CLEP no utiliza IA generativa para producir contenido editorial.

**Prohibido en producción**
- resúmenes mediante LLM;
- traducciones mediante LLM;
- reescritura generativa;
- imágenes generadas;
- selección o ranking de candidatos mediante LLM.

**Permitido**
- parsing y extracción deterministas;
- recuperación de metadatos;
- puntuación mediante reglas explícitas;
- capturas automatizadas de páginas web;
- composición tipográfica determinista (HTML/CSS, SVG o equivalente);
- activos oficiales cuya procedencia y condiciones de uso hayan sido verificadas;
- texto escrito o aprobado por una persona.

Principio de reproducibilidad: dada la misma entrada, la misma versión del código y las mismas fuentes externas, el pipeline debe producir la misma salida editorial.

### Activo visual para PAPER ABIERTO

Orden de preferencia:
1. captura real de la landing page oficial del trabajo o repositorio;
2. portada/thumbnail oficial cuando su uso sea adecuado y verificable;
3. tarjeta tipográfica CLEP generada determinísticamente a partir de metadatos;
4. publicación sin imagen si no existe un activo verificable.

Una captura de pantalla o una tarjeta construida mediante reglas de maquetación no se considera contenido generado por IA.
