#!/usr/bin/env python3
"""Evaluación editorial determinista. El puntaje mide pertinencia CLEP, no calidad."""
import csv,json,os,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=Path(os.getenv("CLEP_CANDIDATES_PATH",str(ROOT/"data/editorial/candidatos.csv"))).resolve()
DOAB_CFG=ROOT/"data/editorial/pertinencia_doab.json"
PRIORITY_CFG=ROOT/"data/editorial/prioridad_editorial.json"

POS={
 "post-keynesian":25,"postkeynesian":25,"poskeynesian":25,"keynes":12,
 "monetary":15,"money":15,"dinero":15,"monetaria":15,"macroeconomic":12,"macroeconomics":12,"macroeconomía":12,
 "development":12,"desarrollo":12,"structural":10,"estructural":10,"employment":10,"empleo":10,
 "labour":10,"labor":10,"trabajo":10,"unemployment":10,"desempleo":10,
 "inequality":10,"desigualdad":10,"distribution":10,"distribución":10,
 "financial":10,"finance":8,"financiero":10,"finanzas":8,
 "input-output":15,"insumo-producto":15,"social reproduction":20,"reproducción social":20,
 "political economy":15,"economía política":15,"economic history":10,"historia económica":10,
 "public finance":10,"finanzas públicas":10,"industrial policy":12,"política industrial":12,
 "latin america":15,"américa latina":15,"mexico":15,"méxico":15,
 "marx":15,"kalecki":15,"sraffa":15,"mmt":15,"modern monetary":15,
 "economic growth":8,"crecimiento económico":8,"wages":8,"salarios":8
}
MIN_AUTO=15

def reference_year():
    raw=(os.getenv("CLEP_REFERENCE_DATE") or "").strip()
    if raw:
        try:return datetime.fromisoformat(raw).year
        except ValueError:pass
    return datetime.now(timezone.utc).year


def norm(s):
    s=unicodedata.normalize("NFKC",str(s or "")).lower()
    return re.sub(r"\s+"," ",s).strip()

def has(text,term):
    return bool(re.search(r"(?<!\w)"+re.escape(norm(term))+r"(?!\w)",text))

def pluralism_hits(body,priority_cfg):
    pl=priority_cfg.get("pluralism",{})
    groups=[]
    for key in ("explicit_traditions","characteristic_concepts","history_method"):
        groups.extend(pl.get(key,{}).get("terms",[]))
    return [t for t in groups if has(body,t)]

def doab_eval(r,cfg,priority_cfg=None):
    title=norm(r.get("title"));body=norm(" ".join([r.get("title",""),r.get("summary",""),r.get("notes","")]))
    anchors=[x for x in cfg["discipline_gate"]["economic_anchors"] if has(body,x)]
    priority_cfg=priority_cfg or json.loads(PRIORITY_CFG.read_text(encoding="utf-8"))
    plural_hits=pluralism_hits(body,priority_cfg)
    exclusions=[x for x in cfg["discipline_gate"]["strong_exclusions"] if has(body,x)]
    area_scores={};area_hits={}
    score=0
    for area,spec in cfg["areas"].items():
        hits=[t for t in spec["terms"] if has(body,t)]
        if hits:
            # Una sola contribución base por área evita inflar sinónimos del mismo tema.
            pts=int(spec["weight"])
            title_hits=[t for t in hits if has(title,t)]
            if title_hits:pts+=int(cfg["bonuses"]["title_match"])
            area_scores[area]=pts;area_hits[area]=hits[:6];score+=pts
    # El pluralismo/historia/metodología es también evidencia temática aguas arriba.
    # Si no fue capturado literalmente por el área, lo asignamos al área correspondiente.
    harea="historia-pensamiento-metodologia"
    if plural_hits and harea not in area_scores:
        pts=int(cfg["areas"][harea]["weight"])
        if any(has(title,t) for t in plural_hits):pts+=int(cfg["bonuses"]["title_match"])
        area_scores[harea]=pts;area_hits[harea]=plural_hits[:6];score+=pts
    n=len(area_scores)
    if n>=3:score+=int(cfg["bonuses"]["multi_area_3"])
    elif n>=2:score+=int(cfg["bonuses"]["multi_area_2"])
    y=0
    try:y=int(r.get("publication_year") or 0)
    except ValueError:pass
    if y and y>=reference_year()-2:score+=int(cfg["bonuses"]["recent_3_years"])
    discipline_ok=bool(anchors or area_scores)
    if exclusions and not anchors:
        score-=int(cfg["discipline_gate"]["exclusion_penalty"]);discipline_ok=False
    score=max(0,min(score,100))
    ta=int(cfg["thresholds"]["promocion_automatica"]);tr=int(cfg["thresholds"]["revision_editorial"])
    if discipline_ok and score>=ta:decision="PROMOCION_AUTOMATICA"
    elif discipline_ok and score>=tr:decision="REVISION_EDITORIAL"
    else:decision="ARCHIVADO"
    plural_rescue=(decision=="REVISION_EDITORIAL" and discipline_ok and bool(plural_hits)
                   and cfg.get("pluralism_rescue",{}).get("enabled",False))
    ranked=sorted(area_scores,key=lambda a:(-area_scores[a],a))
    primary=ranked[0] if ranked else ""
    reasons=[
      "decision="+decision,
      "disciplina="+("economia" if discipline_ok else "no_confirmada"),
      "areas="+(",".join(ranked) if ranked else "ninguna"),
      "anclas="+(",".join(anchors[:5]) if anchors else "ninguna"),
      "pluralismo_rescate="+("si" if plural_rescue else "no"),
      "senales_pluralistas="+(",".join(plural_hits[:6]) if plural_hits else "ninguna")
    ]
    if exclusions:reasons.append("exclusiones="+",".join(exclusions[:4]))
    for a in ranked[:4]:reasons.append(a+"="+",".join(area_hits[a][:4]))
    return score,decision,primary,";".join(reasons)

def generic_eval(r):
    text=norm((r.get("title") or "")+" "+(r.get("summary") or ""))
    score=0;reasons=[]
    if r.get("source_type")=="nep_report":
        score+=20;reasons.append("fuente_nep_curada")
    for term,pts in POS.items():
        if has(text,term):score+=pts;reasons.append(term)
    return min(score,100),"EVALUADO",r.get("area_clep") or "",";".join(reasons) if reasons else "sin_coincidencias"

def main():
    cfg=json.loads(DOAB_CFG.read_text(encoding="utf-8"))
    priority_cfg=json.loads(PRIORITY_CFG.read_text(encoding="utf-8"))
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    evaluated=0
    counts={"PROMOCION_AUTOMATICA":0,"REVISION_EDITORIAL":0,"ARCHIVADO":0}
    academic_counts={"PROMOCION_AUTOMATICA":0,"REVISION_EDITORIAL":0,"ARCHIVADO":0}
    for r in rows:
        if r.get("status") not in {"DETECTADO","EVALUADO","METADATOS_OBTENIDOS","OA_VERIFICADO","REVISION_EDITORIAL","ARCHIVADO","FICHA_LISTA"}:continue
        if r.get("source_type")=="statistical_watch" and int(r.get("relevance_score") or 0)>=100:
            r["status"]="EVALUADO";continue
        if r.get("source_type") in {"doab_oai","doab_rest"} or r.get("source_id")=="doab-economics":
            score,decision,area,reasons=doab_eval(r,cfg,priority_cfg)
            r["relevance_score"]=str(score);r["relevance_reasons"]=reasons
            if area:r["area_clep"]=area
            r["status"]="EVALUADO" if decision=="PROMOCION_AUTOMATICA" else decision
            counts[decision]+=1
        elif r.get("source_type") in {"crossref_academic","academic_oai","nep_report"}:
            score,decision,area,reasons=doab_eval(r,cfg,priority_cfg)
            r["relevance_score"]=str(score);r["relevance_reasons"]=reasons
            if area:r["area_clep"]=area
            r["status"]="EVALUADO" if decision=="PROMOCION_AUTOMATICA" else decision
            academic_counts[decision]+=1
        else:
            score,status,area,reasons=generic_eval(r)
            r["relevance_score"]=str(score);r["relevance_reasons"]=reasons;r["status"]=status
            if area:r["area_clep"]=area
            if score<MIN_AUTO:
                r["notes"]=((r.get("notes") or "")+" | pertinencia insuficiente para promoción automática").strip(" |")
        evaluated+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Evaluados: {evaluated}; umbral general={MIN_AUTO}")
    print("DOAB: "+", ".join(f"{k}={v}" for k,v in counts.items()))
    print("Novedades académicas: "+", ".join(f"{k}={v}" for k,v in academic_counts.items()))
if __name__=="__main__":main()
