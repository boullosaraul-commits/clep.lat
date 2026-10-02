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
