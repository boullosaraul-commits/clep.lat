#!/usr/bin/env python3
"""Auditoría reproducible del índice editorial CLEP y salud del embudo."""
import csv,json,os
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=Path(os.getenv("CLEP_CANDIDATES_PATH",str(ROOT/"data/editorial/candidatos.csv"))).resolve()
OUT=Path(os.getenv("CLEP_PRIORITY_AUDIT_PATH",str(ROOT/"data/editorial/auditoria_prioridad.json"))).resolve()
ACADEMIC={"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}

def bucket(x):
    if x>=9:return "9_10"
    if x>=7:return "7_8_9"
    if x>=5:return "5_6_9"
    return "0_4_9"

def score_of(r):
    try:return float(r.get("editorial_score") or 0)
    except ValueError:return 0.0

def source_of(r):return r.get("source_id") or r.get("source_type") or "unknown"

def compact(r):
    return {
      "candidate_id":r.get("candidate_id"),"title":r.get("title"),"source":source_of(r),
      "type":r.get("content_type"),"score":r.get("editorial_score"),
      "decision":r.get("editorial_decision"),"components":r.get("editorial_score_reasons"),
      "relevance_score":r.get("relevance_score"),"relevance_reasons":r.get("relevance_reasons"),
      "access_status":r.get("access_status"),"oa_status":r.get("oa_status")
    }

def sample(rows,predicate,n=25):
    xs=[r for r in rows if predicate(r)]
    xs.sort(key=lambda r:(-score_of(r),r.get("candidate_id") or ""))
    return [compact(r) for r in xs[:n]]

def main():
    with P.open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    bins=Counter();decisions=Counter();sources=defaultdict(Counter);types=defaultdict(Counter);missing=0
    academic_rows=[r for r in rows if (r.get("content_type") or "") in ACADEMIC]
    funnel=defaultdict(Counter)
    for r in academic_rows:
        src=source_of(r);funnel[src]["discovered"]+=1
        rel=r.get("relevance_reasons") or ""
        if "decision=PROMOCION_AUTOMATICA" in rel:funnel[src]["thematic_auto"]+=1
        elif "pluralismo_rescate=si" in rel:funnel[src]["thematic_rescue"]+=1
        elif "decision=REVISION_EDITORIAL" in rel:funnel[src]["thematic_review"]+=1
        elif "decision=ARCHIVADO" in rel:funnel[src]["thematic_rejected"]+=1
        if r.get("access_status") in {"PUBLIC_ACCESS_VERIFIED","VERIFICADO"}:funnel[src]["access_verified"]+=1
        if r.get("oa_status") in {"VERIFICADO","VERIFICADO_FUENTE","OA_VERIFICADO"}:funnel[src]["oa_evidence"]+=1
        if r.get("editorial_decision") in {"PUBLISHABLE","OUTSTANDING"}:funnel[src]["publishable"]+=1
        try:x=float(r.get("editorial_score") or "")
        except ValueError:x=None
        if x is None:missing+=1;continue
        b=bucket(x);bins[b]+=1;decisions[r.get("editorial_decision") or ""]+=1
        sources[r.get("source_type") or r.get("source_id") or "unknown"][b]+=1
        types[r.get("content_type") or "unknown"][b]+=1

    top=[compact(r) for r in sorted(academic_rows,key=lambda x:score_of(x),reverse=True)[:12]]
    calibration={
      "pluralist_rescues":sample(academic_rows,lambda r:"pluralismo_rescate=si" in (r.get("relevance_reasons") or "")),
      "regional_nonplural":sample(academic_rows,lambda r:"R=1.0" in (r.get("editorial_score_reasons") or "") and "H=0.0" in (r.get("editorial_score_reasons") or "")),
      "thematic_rejected":sample(academic_rows,lambda r:r.get("editorial_decision")=="THEMATIC_REJECTED"),
      "borderline":sample(academic_rows,lambda r:5.0<=score_of(r)<7.0)
    }
    health={
      "oa_pending":sum(1 for r in academic_rows if r.get("access_status") not in {"PUBLIC_ACCESS_VERIFIED","VERIFICADO"} and (r.get("access_url") or "").strip()),
      "repec_metadata_pending":sum(1 for r in rows if r.get("source_type")=="nep_report" and not (r.get("title") or "").strip()),
      "publishable":sum(1 for r in academic_rows if r.get("editorial_decision") in {"PUBLISHABLE","OUTSTANDING"}),
      "pluralist_rescues_total":sum(1 for r in academic_rows if "pluralismo_rescate=si" in (r.get("relevance_reasons") or ""))
    }
    out={
      "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "records":len(rows),"academic_records":len(academic_rows),"missing_editorial_score":missing,
      "buckets":dict(bins),"decisions":dict(decisions),
      "by_source":{k:dict(v) for k,v in sorted(sources.items())},
      "by_type":{k:dict(v) for k,v in sorted(types.items())},
      "source_funnel":{k:dict(v) for k,v in sorted(funnel.items())},
      "health":health,"calibration_sample":calibration,"top_candidates":top
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
