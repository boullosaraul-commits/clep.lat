# Infraestructura editorial CLEP

Este directorio contiene el estado editorial estructurado de CLEP.

## Flujos

- `archivo_historico`: reedición gradual del archivo histórico. Máximo 6 publicaciones por día.
- `novedad`: publicaciones bibliográficas nuevas. No consume el cupo histórico.
- `recurso`: bases de datos, repositorios, observatorios, institutos y otros recursos. No consume el cupo histórico.
- `actividad_clep`: actividades propias de CLEP. No consume el cupo histórico.
- `publicacion_clep`: producción propia de CLEP. No consume el cupo histórico.

El límite de seis es un techo exclusivo para `archivo_historico`, no un límite general de publicaciones de CLEP.

Los secretos de Meta no deben almacenarse en este repositorio.
