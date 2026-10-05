#!/usr/bin/env python3
"""Reserva de forma durable una sola publicación para un intento Meta.

Debe ejecutarse y COMMITTEARSE antes de llamar a Meta. Así, si el runner cae
después de que Meta acepte una publicación pero antes de guardar su ID, la fila
queda IN_FLIGHT y futuras ejecuciones no la reintentan automáticamente.

Escribe el editorial_id reservado en el archivo indicado por --output.
Exit 3 = no hay nada nuevo que reservar.
"""
import argparse,csv,os
from datetime import datetime
from pathlib import Path

from editorial_rules import check_meta_reservable

ROOT=Path(__file__).resolve().parents[2]
COLA=Path(os.getenv("CLEP_QUEUE_PATH",str(ROOT/"data/editorial/cola.csv"))).resolve()

def pri(r):
    try:p=int(r.get("prioridad") or 999)
    except Exception:p=999
    return (r.get("fecha_programada") or "",r.get("orden_dia") or "",p,r.get("editorial_id") or "")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="/tmp/clep_meta_attempt_id")
    args=ap.parse_args()
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    candidates=[r for r in rows if check_meta_reservable(r)]
    candidates.sort(key=pri)
    if not candidates:
        Path(args.output).unlink(missing_ok=True)
        print("No hay publicaciones nuevas para reservar.")
        raise SystemExit(3)
    r=candidates[0]
    r["meta_attempt_status"]="IN_FLIGHT"
    r["meta_attempted_at"]=datetime.now().astimezone().isoformat(timespec="seconds")
    r["notas"]=((r.get("notas") or "")+" | intento Meta reservado de forma durable").strip(" |")
    with COLA.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    Path(args.output).write_text(r["editorial_id"]+"\n",encoding="utf-8")
    print(f"Reservado: {r['editorial_id']}")

if __name__=="__main__":main()
