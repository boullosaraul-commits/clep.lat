# Frontera legacy del pipeline editorial

Este documento acompaña `legacy_contract.json`. La regla es simple: el flujo productivo moderno no puede depender de reparaciones legacy ni crear nuevas excepciones silenciosas.

## Clasificación vigente

### Herramienta manual

`script/editorial/migrar_nep_legacy.py` queda fuera de todos los workflows automáticos. `--check` es sólo lectura y sirve como alarma de regresión; `--apply` es una reparación deliberada.

### Shims de compatibilidad

- `scripts/editorial/generar_ficha_paper.py`: no posee plantilla ni política; delega a `renderizar_texto.render_result` y no debe tener consumidores productivos nuevos.
- `scripts/editorial/promover_candidatos.py`: no escribe `FICHA_LISTA`; delega al orquestador `preparar_publicacion.main`.

### Excepción histórica

`recovery/historical_worker.py` es la única excepción que puede escribir directamente `FICHA_LISTA`, exclusivamente con `flujo_editorial=archivo_historico`. No puede planificar, publicar en Meta ni convertirse en una segunda autoridad editorial.

La excepción existe porque la recuperación conserva identidad y evidencia del post histórico (`post_original_id`, URL/fecha original y estado de retiro) que no pertenecen al flujo de novedades.

## Columnas legacy

Se conservan tres grupos distintos:

1. **Identidad histórica necesaria**: `post_original_id`, `post_original_url`, `fecha_original`, `original_retirado`, `fecha_retiro`. No son aliases; describen el objeto histórico.
2. **Aliases operativos temporales**: `flujo_editorial`, `estado_editorial`, `fecha_programada`, `orden_dia`, `post_nuevo_id`, `post_nuevo_url`, `meta_attempt_status`, `meta_attempted_at`. Se mantienen mientras existan lectores/escritores legacy en planificación y Meta.
3. **Provenance canónica nueva**: fingerprints de candidato/política/preparación y certificación física de media. Estos campos ya forman parte del contrato endurecido y no deben degradarse a aliases legacy.

## Regla de eliminación

Un alias operativo sólo puede borrarse cuando todos sus lectores y escritores hayan migrado al schema versionado y CI demuestre que no quedan referencias. No se elimina una columna sólo porque parezca redundante.

## Regresión

`tests/test_preparation_bypass.py` impide automáticamente:

- reintroducir `migrar_nep_legacy.py` en workflows;
- añadir escritores directos de `FICHA_LISTA`;
- ampliar la excepción histórica a otros estados;
- hacer que `generar_ficha_paper.py` vuelva a ser dependencia productiva;
- reintroducir filas NEP que necesiten reparación legacy.
