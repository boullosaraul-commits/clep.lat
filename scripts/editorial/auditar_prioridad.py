#!/usr/bin/env python3
"""Auditoría reproducible del índice editorial CLEP."""
import csv,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
OUT=ROOT/"data/editorial/auditoria_prioridad.json"
ACADEMIC={"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}

def bucket(x):
    if x>=9:return "9_10"
    if x>=7:return "7_8_9"
    if x>=5:return "5_6_9"
    return "0_4_9"

def main():
    with P.open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    bins=Counter();decisions=Counter();sources=defaultdict(Counter);types=defaultdict(Counter);missing=0
    academic_rows=[r for r in rows if (r.get("content_type") or "") in ACADEMIC]
    for r in academic_rows:
        try:x=float(r.get("editorial_score") or "")
        except ValueError:x=None
        if x is None:missing+=1;continue
        b=bucket(x);bins[b]+=1;decisions[r.get("editorial_decision") or ""]+=1
        sources[r.get("source_type") or r.get("source_id") or "unknown"][b]+=1
        types[r.get("content_type") or "unknown"][b]+=1
    top=[]
    for r in sorted(academic_rows,key=lambda x:float(x.get("editorial_score") or 0),reverse=True)[:12]:
        top.append({"candidate_id":r.get("candidate_id"),"title":r.get("title"),"source":r.get("source_id"),
                    "type":r.get("content_type"),"score":r.get("editorial_score"),
                    "decision":r.get("editorial_decision"),"components":r.get("editorial_score_reasons"),
                    "relevance_score":r.get("relevance_score"),"access_status":r.get("access_status")})
    out={
      "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "records":len(rows),"academic_records":len(academic_rows),"missing_editorial_score":missing,
      "buckets":dict(bins),"decisions":dict(decisions),
      "by_source":{k:dict(v) for k,v in sorted(sources.items())},
      "by_type":{k:dict(v) for k,v in sorted(types.items())},
      "top_candidates":top
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
