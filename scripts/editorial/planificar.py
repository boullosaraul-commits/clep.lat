#!/usr/bin/env python3
"""Planificador determinista CLEP.

Sólo agenda entradas ya editorialmente listas. No escribe fichas, no traduce,
no verifica OA y no usa IA. Asigna fecha_programada/orden_dia respetando
programacion.json y deja estado PROGRAMADO.
"""
import csv,json,math
from datetime import datetime,timedelta,date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
Q=ROOT/"data/editorial/cola.csv"
CFG=ROOT/"data/editorial/programacion.json"

READY={"FICHA_LISTA","APROBADO"}
NON_TEXT={"actividad_clep","convocatoria","recurso","video","grafica","material_didactico","efemeride","anuncio_institucional"}

def historical_cap(backlog,days_left,rungs):
    if backlog<=0:return 0
    need=math.ceil(backlog/max(1,days_left))
    for r in sorted(rungs):
        if r>=need:return r
    return max(rungs)

def main():
    cfg=json.loads(CFG.read_text())
    tz=ZoneInfo(cfg["timezone"]); now=datetime.now(tz)
    tomorrow=now.date()+timedelta(days=1)
    with Q.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    slots=cfg["slots_preferentes"]
    newmax=cfg["contenido_actual"]["nuevos"]["maximo_diario_inicial"]
    ntmax=cfg["contenido_actual"]["no_textos"]["maximo_diario_inicial"]
    hist=[r for r in rows if r["flujo_editorial"]=="archivo_historico" and r["estado_editorial"] in READY and not r["fecha_programada"]]
    target=date.fromisoformat(cfg["archivo_historico"]["fecha_objetivo"])
    hcap=historical_cap(len(hist),(target-now.date()).days,cfg["archivo_historico"]["escalones_preferidos"])
    current=[r for r in rows if r["flujo_editorial"]!="archivo_historico" and r["estado_editorial"] in READY and not r["fecha_programada"]]
    nontext=[r for r in current if r["tipo_recurso"] in NON_TEXT][:ntmax]
    papers=[r for r in current if r["tipo_recurso"] not in NON_TEXT][:newmax]
    chosen=papers+nontext+hist[:hcap]
    chosen.sort(key=lambda r:(int(r["prioridad"] or 999),r["editorial_id"]))
    chosen=chosen[:len(slots)]
    if chosen:
        # Spread selected posts across the whole configured window.
        idx=[round(i*(len(slots)-1)/max(1,len(chosen)-1)) for i in range(len(chosen))]
    else: idx=[]
    for i,r in enumerate(chosen):
        dt=datetime.combine(tomorrow,datetime.strptime(slots[idx[i]],"%H:%M").time(),tzinfo=tz)
        r["fecha_programada"]=dt.isoformat(timespec="minutes")
        r["orden_dia"]=str(i+1); r["estado_editorial"]="PROGRAMADO"
        r["notas"]=(r["notas"]+" | Planificado automáticamente sin IA generativa.").strip(" |")
    with Q.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(f"Programados para {tomorrow}: {len(chosen)} (histórico máx {hcap})")

if __name__=="__main__":main()
