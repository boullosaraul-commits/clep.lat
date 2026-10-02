#!/usr/bin/env python3
import csv
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLA = ROOT / "data" / "editorial" / "cola.csv"
LIMITE_ARCHIVO_DIARIO = 6

FLUJOS = {
    "archivo_historico",
    "novedad",
    "recurso",
    "actividad_clep",
    "publicacion_clep",
    "otro",
}

ESTADOS = {
    "IDENTIFICANDO",
    "OBRA_VERIFICADA",
    "EDICION_VERIFICADA",
    "OA_VERIFICADO",
    "FICHA_LISTA",
    "PROGRAMADO",
    "PUBLICADO",
    "ORIGINAL_RETIRADO",
    "DESCARTADO",
}

def main():
    with COLA.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    errores = []
    ids = Counter(r["editorial_id"] for r in rows if r.get("editorial_id"))
    for eid, n in ids.items():
        if n > 1:
            errores.append(f"editorial_id duplicado: {eid}")

    historicas = defaultdict(int)

    for n, r in enumerate(rows, start=2):
        flujo = r.get("flujo_editorial", "")
        estado = r.get("estado_editorial", "")
        fecha = r.get("fecha_programada", "")

        if flujo not in FLUJOS:
            errores.append(f"línea {n}: flujo inválido: {flujo}")
        if estado not in ESTADOS:
            errores.append(f"línea {n}: estado inválido: {estado}")

        if fecha:
            try:
                date.fromisoformat(fecha)
            except ValueError:
                errores.append(f"línea {n}: fecha_programada inválida: {fecha}")

        if (
            flujo == "archivo_historico"
            and estado in {"PROGRAMADO", "PUBLICADO", "ORIGINAL_RETIRADO"}
            and fecha
        ):
            historicas[fecha] += 1

        if (
            flujo == "archivo_historico"
            and r.get("original_retirado") == "1"
            and not r.get("post_nuevo_id")
        ):
            errores.append(
                f"línea {n}: original histórico retirado sin post nuevo"
            )

    for fecha, total in sorted(historicas.items()):
        if total > LIMITE_ARCHIVO_DIARIO:
            errores.append(
                f"{fecha}: {total} recuperaciones históricas; máximo = "
                f"{LIMITE_ARCHIVO_DIARIO}"
            )

    print("CLEP — VALIDACIÓN EDITORIAL")
    print("=" * 72)
    print(f"Registros: {len(rows)}")
    print(f"Máximo archivo histórico/día: {LIMITE_ARCHIVO_DIARIO}")

    if errores:
        print("\nERRORES")
        for e in errores:
            print(" -", e)
        return 1

    print("\nOK — cola válida.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
