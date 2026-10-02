#!/usr/bin/env python3
"""Planificador determinista CLEP.

Máximos independientes:
- hasta 6 novedades textuales/día;
- hasta 4 piezas no-texto/día;
- hasta 6 recuperaciones históricas/día inicialmente.

La fecha objetivo histórica es sólo referencia de ritmo: nunca apaga la
campaña. Sólo agenda filas con texto e imagen ya certificados.
"""
import csv,json,math
from datetime import datetime,timedelta,date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
Q=ROOT/"data/editorial/cola.csv"
CFG=ROOT/"data/editorial/programacion.json"

READY={"FICHA_LISTA","APROBADO"}
NON_TEXT={"actividad_clep","convocatoria","convocatoria_evento","recurso","video","grafica","dataset_grafica","material_didactico","efemeride","anuncio_institucional"}

def certified(r):
    return (r.get("text_status")=="VERIFICADO" and bool((r.get("ficha_es") or "").strip())
            and r.get("media_rights_status") in {"VERIFICADO","PROPIO_DETERMINISTA"}
            and bool((r.get("media_path") or r.get("media_url") or "").strip()))

def priority(r):
    try:p=int(r.get("prioridad") or 999)
    except Exception:p=999
    return (p,r.get("editorial_id") or "")

def editorial_index_10(r):
    """Índice editorial determinista 0–10 derivado de pertinencia 0–100.
    No representa calidad académica."""
    raw=""
    notes=(r.get("notas") or "")
    m=__import__("re").search(r"(?:indice_editorial|relevance_score)\s*[=:]\s*(\d+(?:\.\d+)?)",notes,re.I)
    if m: raw=m.group(1)
    # Las filas de cola no conservan relevance_score como columna; para DOAB la
    # prioridad se deriva del candidato y puede incorporarse a notas. Si no está,
    # no cuenta como sobresaliente: comportamiento conservador.
    try:
        x=float(raw)
        return x/10 if x>10 else x
    except Exception:return 0.0

def is_doab(r):
    text=" ".join([r.get("oa_fuente") or "",r.get("notas") or "",r.get("url_original") or ""]).lower()
    return "doab" in text or "directory of open access books" in text

def choose_diverse_textual(textual,capacity,doab_cap):
    chosen=[];doab_n=0
    for r in textual:
        if len(chosen)>=capacity:break
        if is_doab(r):
            if doab_n>=doab_cap:continue
            doab_n+=1
        chosen.append(r)
    return chosen

def historical_cap(remaining,days_left,rungs,maxcap):
    if remaining<=0:return 0
    if days_left<=0:return maxcap
    need=math.ceil(remaining/max(1,days_left))
    for r in sorted(set(int(x) for x in rungs)):
        if r>=need:return min(r,maxcap)
    return maxcap

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    tz=ZoneInfo(cfg["timezone"]);now=datetime.now(tz);target_day=now.date()+timedelta(days=1)
    with Q.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames

    slots=list(cfg["slots_preferentes"])
    ncfg=cfg["contenido_actual"]["nuevos"]
    newmax=int(ncfg["maximo_diario_inicial"])
    ntmax=int(cfg["contenido_actual"]["no_textos"]["maximo_diario_inicial"])
    hmax=int(cfg["archivo_historico"]["maximo_diario_inicial"])

    # Ritmo histórico: target = referencia, no condición de apagado.
    retired=sum(1 for r in rows if r.get("flujo_editorial")=="archivo_historico"
                and (r.get("original_retirado") or "").lower() in {"1","true","yes"})
    backlog_ref=int(cfg["archivo_historico"].get("backlog_referencia",0))
    remaining=max(0,backlog_ref-retired)
    target=date.fromisoformat(cfg["archivo_historico"]["fecha_objetivo"])
    hcap=historical_cap(remaining,(target-now.date()).days,cfg["archivo_historico"]["escalones_preferidos"],hmax)

    def scheduled_for_day(r):
        return r.get("fecha_programada")==target_day.isoformat() and r.get("estado_editorial") in {"PROGRAMADO","PUBLICADO","ORIGINAL_RETIRADO"}

    existing=[r for r in rows if scheduled_for_day(r)]
    existing_hist=sum(1 for r in existing if r.get("flujo_editorial")=="archivo_historico")
    existing_nt=sum(1 for r in existing if r.get("flujo_editorial")!="archivo_historico" and r.get("tipo_recurso") in NON_TEXT)
    existing_new=sum(1 for r in existing if r.get("flujo_editorial")!="archivo_historico" and r.get("tipo_recurso") not in NON_TEXT)

    ready=[r for r in rows if r.get("estado_editorial") in READY and not r.get("fecha_programada") and certified(r)]
    hist=sorted([r for r in ready if r.get("flujo_editorial")=="archivo_historico"],key=priority)
    current=[r for r in ready if r.get("flujo_editorial")!="archivo_historico"]
    nontext=sorted([r for r in current if r.get("tipo_recurso") in NON_TEXT],key=priority)
    textual=sorted([r for r in current if r.get("tipo_recurso") not in NON_TEXT],key=priority)

    # Capacidad elástica: 6 normalmente; hasta 8 sólo con >=5 candidatos
    # sobresalientes (índice editorial >=9/10). No es una cuota.
    elastic=ncfg.get("regla_elastica",{})
    threshold=float(elastic.get("umbral_indice_editorial_10",9))
    min_high=int(elastic.get("minimo_candidatos_sobresalientes_para_expandir",5))
    high=sum(1 for r in textual if editorial_index_10(r)>=threshold)
    effective_newmax=newmax
    if elastic.get("activa") and high>=min_high:
        effective_newmax=int(ncfg.get("maximo_diario_excepcional",newmax))
    diversity=ncfg.get("diversidad",{});dcfg=diversity.get("doab",{})
    doab_cap=int(dcfg.get("maximo_diario_excepcional" if effective_newmax>newmax else "maximo_diario_normal",2))
    existing_doab=sum(1 for r in existing if r.get("flujo_editorial")!="archivo_historico"
                      and r.get("tipo_recurso") not in NON_TEXT and is_doab(r))
    choose_text=choose_diverse_textual(textual,max(0,effective_newmax-existing_new),
                                       max(0,doab_cap-existing_doab))
    choose_nt=nontext[:max(0,ntmax-existing_nt)]
    choose_hist=hist[:max(0,hcap-existing_hist)]
    chosen=choose_text+choose_nt+choose_hist
    chosen.sort(key=priority)

    occupied={r.get("orden_dia") for r in existing if r.get("orden_dia")}
    free=[x for x in slots if x not in occupied]
    if len(chosen)>len(free):chosen=chosen[:len(free)]
    # Distribuir por toda la ventana disponible.
    if chosen:
        idx=[round(i*(len(free)-1)/max(1,len(chosen)-1)) for i in range(len(chosen))]
        assigned=[];used=set()
        for i in idx:
            while i in used and i+1<len(free):i+=1
            if i in used:
                i=next(j for j in range(len(free)) if j not in used)
            used.add(i);assigned.append(free[i])
    else:assigned=[]

    for r,hhmm in zip(chosen,assigned):
        r["fecha_programada"]=target_day.isoformat()
        r["orden_dia"]=hhmm
        r["estado_editorial"]="PROGRAMADO"
        r["notas"]=((r.get("notas") or "")+" | Planificado automáticamente sin IA generativa.").strip(" |")

    with Q.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Programados {target_day}: total={len(chosen)}; nuevos={len(choose_text)}/{effective_newmax}; DOAB={sum(is_doab(r) for r in choose_text)}/{doab_cap}; sobresalientes9={high}; no-texto={len(choose_nt)}; histórico={len(choose_hist)}; cap histórico={hcap}; backlog ref restante={remaining}")

if __name__=="__main__":main()
