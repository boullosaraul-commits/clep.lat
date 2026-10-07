#!/usr/bin/env python3
"""Planificador determinista CLEP."""
import csv,json,math,os,re
from collections import Counter
from datetime import datetime,timedelta,date
from pathlib import Path
from zoneinfo import ZoneInfo
from editorial_rules import NON_TEXT_TYPES, academic_publishable, editorial_score, publication_certified, schedulable

ROOT=Path(__file__).resolve().parents[2]
Q=Path(os.getenv("CLEP_QUEUE_PATH",str(ROOT/"data/editorial/cola.csv"))).resolve()
CFG=ROOT/"data/editorial/programacion.json"
NON_TEXT=NON_TEXT_TYPES

def certified(r):return publication_certified(r)
def priority(r):
    try:p=int(r.get("prioridad") or 999)
    except Exception:p=999
    return (p,r.get("editorial_id") or "")
def editorial_index_10(r):return editorial_score(r)
def reference_now(tz):
    raw=(os.getenv("CLEP_REFERENCE_DATE") or "").strip()
    if raw:return datetime.fromisoformat(raw+"T12:00:00").replace(tzinfo=tz)
    return datetime.now(tz)
def is_doab(r):
    text=" ".join([r.get("oa_fuente") or "",r.get("notas") or "",r.get("url_original") or ""]).lower()
    return "doab" in text or "directory of open access books" in text
def institution_series(r):
    notes=r.get("notas") or "";m=re.search(r"venue=([^;|]+)",notes,re.I)
    return (m.group(1).strip().lower() if m and m.group(1).strip() else (r.get("oa_fuente") or "").strip().lower())

def choose_diverse_textual(textual,capacity,doab_cap,max_same_type=3,min_types=3,max_same_source=2,existing_type_counts=None,existing_doab=0,existing_source_counts=None):
    existing_type_counts=Counter(existing_type_counts or {});counts=Counter(existing_type_counts);source_counts=Counter(existing_source_counts or {})
    represented={k for k,v in counts.items() if v>0};chosen=[];used=set();doab_n=existing_doab
    def can_take(r):
        nonlocal doab_n
        typ=r.get("tipo_recurso") or "otro"
        if counts[typ]>=max_same_type:return False
        src=institution_series(r)
        if src and source_counts[src]>=max_same_source:return False
        if is_doab(r) and doab_n>=doab_cap:return False
        return True
    target=min(min_types,len({r.get("tipo_recurso") or "otro" for r in textual}|represented))
    if len(represented)<target:
        for r in textual:
            if len(chosen)>=capacity or len(represented)>=target:break
            typ=r.get("tipo_recurso") or "otro"
            if typ in represented or not can_take(r):continue
            chosen.append(r);used.add(id(r));counts[typ]+=1;represented.add(typ)
            src=institution_series(r)
            if src:source_counts[src]+=1
            if is_doab(r):doab_n+=1
    for r in textual:
        if len(chosen)>=capacity:break
        if id(r) in used or not can_take(r):continue
        typ=r.get("tipo_recurso") or "otro";chosen.append(r);counts[typ]+=1
        src=institution_series(r)
        if src:source_counts[src]+=1
        if is_doab(r):doab_n+=1
    return chosen

def historical_cap(remaining,days_left,rungs,maxcap):
    if remaining<=0:return 0
    if days_left<=0:return maxcap
    need=math.ceil(remaining/max(1,days_left))
    for r in sorted(set(int(x) for x in rungs)):
        if r>=need:return min(r,maxcap)
    return maxcap

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"));tz=ZoneInfo(cfg["timezone"]);now=reference_now(tz);target_day=now.date()+timedelta(days=1)
    with Q.open(encoding="utf-8",newline="") as f:rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    slots=list(cfg["slots_preferentes"]);total_cap=min(int(cfg.get("maximo_total_diario",len(slots))),len(slots));ncfg=cfg["contenido_actual"]["nuevos"]
    newmax=int(ncfg["maximo_diario_inicial"]);ntmax=int(cfg["contenido_actual"]["no_textos"]["maximo_diario_inicial"]);hmax=int(cfg["archivo_historico"]["maximo_diario_inicial"])
    retired=sum(1 for r in rows if r.get("flujo_editorial")=="archivo_historico" and (r.get("original_retirado") or "").lower() in {"1","true","yes"})
    backlog_ref=int(cfg["archivo_historico"].get("backlog_referencia",0));remaining=max(0,backlog_ref-retired);target=date.fromisoformat(cfg["archivo_historico"]["fecha_objetivo"])
    hcap=historical_cap(remaining,(target-now.date()).days,cfg["archivo_historico"]["escalones_preferidos"],hmax)
    def scheduled_for_day(r):return r.get("fecha_programada")==target_day.isoformat() and r.get("estado_editorial") in {"PROGRAMADO","PUBLICADO","ORIGINAL_RETIRADO"}
    existing=[r for r in rows if scheduled_for_day(r)];existing_hist=sum(1 for r in existing if r.get("flujo_editorial")=="archivo_historico");existing_nt=sum(1 for r in existing if r.get("flujo_editorial")!="archivo_historico" and r.get("tipo_recurso") in NON_TEXT);existing_new=sum(1 for r in existing if r.get("flujo_editorial")!="archivo_historico" and r.get("tipo_recurso") not in NON_TEXT)
    ready=[r for r in rows if schedulable(r)];hist=sorted([r for r in ready if r.get("flujo_editorial")=="archivo_historico"],key=priority);current=[r for r in ready if r.get("flujo_editorial")!="archivo_historico"]
    allowed_raw=(os.getenv("CLEP_ALLOWED_URL_IDS") or "").strip();allowed={x.strip() for x in allowed_raw.split(",") if x.strip()};controlled=bool(allowed)
    if controlled:current=[r for r in current if (r.get("url_id") or "") in allowed];hist=[]
    nontext=[] if controlled else sorted([r for r in current if r.get("tipo_recurso") in NON_TEXT],key=priority)
    textual=[r for r in current if r.get("tipo_recurso") not in NON_TEXT and academic_publishable(r)]
    textual=sorted(textual,key=lambda r:(-editorial_index_10(r),)+priority(r))
    elastic=ncfg.get("regla_elastica",{});threshold=float(elastic.get("umbral_indice_editorial_10",9));min_high=int(elastic.get("minimo_candidatos_sobresalientes_para_expandir",5));high=sum(1 for r in textual if editorial_index_10(r)>=threshold);effective_newmax=newmax
    if elastic.get("activa") and high>=min_high:effective_newmax=int(ncfg.get("maximo_diario_excepcional",newmax))
    diversity=ncfg.get("diversidad",{});dcfg=diversity.get("doab",{});doab_cap=int(dcfg.get("maximo_diario_excepcional" if effective_newmax>newmax else "maximo_diario_normal",2))
    existing_textual=[r for r in existing if r.get("flujo_editorial")!="archivo_historico" and r.get("tipo_recurso") not in NON_TEXT];existing_doab=sum(1 for r in existing_textual if is_doab(r));existing_types=Counter((r.get("tipo_recurso") or "otro") for r in existing_textual);existing_sources=Counter(institution_series(r) for r in existing_textual if institution_series(r));max_same=int(diversity.get("maximo_mismo_tipo_diario",3));max_same_source=int(diversity.get("maximo_misma_institucion_serie_diario",2));min_types=int(diversity.get("minimo_tipos_distintos_si_disponibles",3))
    choose_text=choose_diverse_textual(textual,max(0,effective_newmax-existing_new),doab_cap,max_same,min_types,max_same_source,existing_types,existing_doab,existing_sources)
    remaining_after_new=max(0,total_cap-len(existing)-len(choose_text));choose_nt=nontext[:min(max(0,ntmax-existing_nt),remaining_after_new)];remaining_after_current=max(0,total_cap-len(existing)-len(choose_text)-len(choose_nt));choose_hist=hist[:min(max(0,hcap-existing_hist),remaining_after_current)];chosen=choose_text+choose_nt+choose_hist;chosen.sort(key=priority)
    occupied={r.get("orden_dia") for r in existing if r.get("orden_dia")};free=[x for x in slots if x not in occupied]
    if len(chosen)>len(free):chosen=chosen[:len(free)]
    if chosen:
        idx=[round(i*(len(free)-1)/max(1,len(chosen)-1)) for i in range(len(chosen))];assigned=[];used=set()
        for i in idx:
            while i in used and i+1<len(free):i+=1
            if i in used:i=next(j for j in range(len(free)) if j not in used)
            used.add(i);assigned.append(free[i])
    else:assigned=[]
    for r,hhmm in zip(chosen,assigned):r["fecha_programada"]=target_day.isoformat();r["orden_dia"]=hhmm;r["estado_editorial"]="PROGRAMADO";r["notas"]=((r.get("notas") or "")+" | Planificado automáticamente sin IA generativa.").strip(" |")
    with Q.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    mode=("controlado" if controlled else "normal");print(f"Programados {target_day}: modo={mode}; total={len(chosen)}; nuevos={len(choose_text)}/{effective_newmax}; DOAB={sum(is_doab(r) for r in choose_text)}/{doab_cap}; sobresalientes9={high}; no-texto={len(choose_nt)}; histórico={len(choose_hist)}; cap histórico={hcap}; backlog ref restante={remaining}")

if __name__=="__main__":main()
