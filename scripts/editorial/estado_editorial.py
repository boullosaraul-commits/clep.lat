#!/usr/bin/env python3
"""Estado derivado y fingerprints deterministas del pipeline editorial CLEP."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ACADEMIC={"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}
QUEUE_DERIVED_FIELDS=["editorial_score","editorial_decision","editorial_policy_fingerprint","candidate_fingerprint"]
POLICY_FILES=[
    ROOT/"data/editorial/pertinencia_doab.json",
    ROOT/"data/editorial/prioridad_editorial.json",
    ROOT/"scripts/editorial/evaluar_candidatos.py",
    ROOT/"scripts/editorial/calcular_prioridad_editorial.py",
]
CANDIDATE_FIELDS=[
    "candidate_id","title","authors","content_type","publication_year","published_at","detected_at",
    "access_url","source_url","access_status","oa_status","source_type","source_id","source_name","venue",
    "language","relevance_score","relevance_reasons","editorial_score","editorial_decision",
    "editorial_score_reasons","area_clep","doi",
]

def _digest(parts):
    h=hashlib.sha256()
    for p in parts:
        b=p if isinstance(p,bytes) else str(p).encode("utf-8")
        h.update(len(b).to_bytes(8,"big"));h.update(b)
    return h.hexdigest()

def policy_fingerprint():
    parts=[]
    for path in POLICY_FILES:
        parts.extend([str(path.relative_to(ROOT)),path.read_bytes()])
    return _digest(parts)

def candidate_fingerprint(row):
    payload={k:str(row.get(k) or "") for k in CANDIDATE_FIELDS}
    return _digest([json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"))])

def score(row):
    try:return float(row.get("editorial_score") or 0)
    except (TypeError,ValueError):return 0.0

def publishable(row,threshold=7.0):
    kind=(row.get("content_type") or row.get("tipo_recurso") or "").strip()
    return kind in ACADEMIC and score(row)>=threshold and row.get("editorial_decision") in {"PUBLISHABLE","OUTSTANDING"}
