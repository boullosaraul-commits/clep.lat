#!/usr/bin/env python3
"""Índice editorial CLEP 0–10, separado de pertinencia temática.

No evalúa calidad científica. Ordena candidatos ya pertinentes según utilidad
editorial verificable para CLEP. Sólo usa campos/metadatos y vocabularios
explícitos; no usa IA generativa.
"""
import csv,json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
CFG=ROOT/"data/editorial/prioridad_editorial.json"
ACADEMIC={"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}

def norm(s):
    s=unicodedata.normalize("NFKC",str(s or "")).lower()
    return re.sub(r"\s+"," ",s).strip()

def has(text,term):
    return bool(re.search(r"(?<!\w)"+re.escape(norm(term))+r"(?!\w)",text))

def year(r):
    try:return int(r.get("publication_year") or 0)
    except ValueError:return 0

def age_days(r,now):
    raw=(r.get("published_at") or "").strip()
    if not raw:return None
    try:
        d=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return max(0,(now-d.astimezone(timezone.utc)).days)
    except Exception:
        m=re.match(r"(\d{4})-(\d{2})-(\d{2})",raw)
        if not m:return None
        try:return max(0,(now.date()-datetime.strptime(m.group(0),"%Y-%m-%d").date()).days)
        except Exception:return None

def identified_responsibility(r):
    return bool((r.get("authors") or "").strip() or (r.get("venue") or "").strip() or (r.get("source_name") or "").strip())

def access_verified(r):
    # Evidencia OA y enlace vivo son dimensiones distintas. La elegibilidad
    # exige que el recurso haya sido comprobado por HTTP.
    return r.get("access_status") in {"PUBLIC_ACCESS_VERIFIED","VERIFICADO"}

def pertinence_component(r):
    reasons=r.get("relevance_reasons") or ""
    m=re.search(r"(?:^|;)areas=([^;]+)",reasons)
    areas=[] if not m or m.group(1)=="ninguna" else [x for x in m.group(1).split(",") if x]
    discipline="disciplina=economia" in reasons
    if not discipline:return 0.0,areas
    pts=2.0 if areas else 0.0
    if len(areas)>=2:pts+=1.0
    # Ancla económica + área temática = economía como objeto central para este
    # clasificador determinista, no mera coincidencia incidental.
    if areas and "anclas=ninguna" not in reasons:pts+=1.0
    return min(4.0,pts),areas

def editorial_value(r,cfg,text):
    ev=cfg["editorial_value"];pts=0.0;kind=r.get("content_type") or ""
    # El primer punto corresponde al carácter académico sustantivo ya verificado.
    if kind in ev["substantive_types"]:pts+=1.0
    if any(has(text,t) for t in ev["training_research_terms"]):pts+=1.0
    if kind in ev["special_utility_types"] or any(has(text,t) for t in ev["special_utility_terms"]):pts+=1.0
    return min(3.0,pts)

def recency_from_days(d):
    if d is None:return 0.0
    if d<=7:return 1.0
    if d<=21:return 0.5
    return 0.0

def access_value(r):
    u=(r.get("access_url") or "").lower()
    if r.get("oa_status") not in {"VERIFICADO","VERIFICADO_FUENTE","OA_VERIFICADO"}:return 0.0
    if u.endswith(".pdf") or "pdf" in u:return 1.0
    return 0.5

def regional_pluralist(r,cfg,text):
    rp=cfg["regional_pluralist"]
    if any(has(text,t) for t in rp["terms"]):return 1.0
    if norm(r.get("language")) in {norm(x) for x in rp["languages"]}:return 1.0
    return 0.0

def thematic_approved(r):
    reasons=r.get("relevance_reasons") or ""
    if "decision=REVISION_EDITORIAL" in reasons:return False,"THEMATIC_REVIEW"
    if "decision=ARCHIVADO" in reasons:return False,"THEMATIC_REJECTED"
    if r.get("source_type") in {"doab_oai","doab_rest","crossref_academic","academic_oai"}:
        return ("decision=PROMOCION_AUTOMATICA" in reasons,
                "THEMATIC_REJECTED" if "decision=PROMOCION_AUTOMATICA" not in reasons else "")
    try:score=float(r.get("relevance_score") or 0)
    except ValueError:score=0
    return (score>=15,"THEMATIC_REVIEW" if score<15 else "")

def evaluate(r,cfg,now=None):
    now=now or datetime.now(timezone.utc)
    approved,thematic_decision=thematic_approved(r)
    if not approved:return 0.0,thematic_decision,"pertinencia_temática=no_aprobada"
    d,freshness_basis=freshness(r,cfg,now)
    eligible=(bool((r.get("title") or "").strip()) and bool(year(r))
              and bool((r.get("access_url") or "").strip()) and access_verified(r)
              and identified_responsibility(r)
              and d is not None and d<=int(cfg["eligibility"]["max_age_days"]))
    if not eligible:
        return 0.0,"INELIGIBLE","eligibilidad=fallida"
    text=norm(" ".join([r.get("title",""),r.get("summary",""),r.get("notes",""),r.get("venue",""),r.get("source_name","")]))
    p,areas=pertinence_component(r)
    v=editorial_value(r,cfg,text);a=recency_from_days(d);o=access_value(r);regional=regional_pluralist(r,cfg,text)
    score=round(min(10.0,p+v+a+o+regional),1)
    th=cfg["thresholds"]
    if score>=float(th["outstanding"]):decision="OUTSTANDING"
    elif score>=float(th["publishable"]):decision="PUBLISHABLE"
    elif score>=float(th["review"]):decision="REVIEW"
    else:decision="ARCHIVE"
    reasons=f"editorial_decision={decision};P={p:.1f};V={v:.1f};A={a:.1f};O={o:.1f};R={regional:.1f};freshness={freshness_basis};areas={','.join(areas) if areas else 'ninguna'}"
    return score,decision,reasons

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=list(rd.fieldnames or [])
    for field in ["editorial_score","editorial_decision","editorial_score_reasons"]:
        if field not in fields:fields.append(field)
    counts={}
    for r in rows:
        # El índice 0–10 sólo gobierna novedades académicas.
        if (r.get("content_type") or "") not in ACADEMIC:continue
        if not (r.get("relevance_reasons") or ""):continue
        score,decision,reasons=evaluate(r,cfg)
        r["editorial_score"]=f"{score:.1f}";r["editorial_decision"]=decision;r["editorial_score_reasons"]=reasons
        counts[decision]=counts.get(decision,0)+1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print("Prioridad editorial: "+", ".join(f"{k}={v}" for k,v in sorted(counts.items())))

if __name__=="__main__":main()
