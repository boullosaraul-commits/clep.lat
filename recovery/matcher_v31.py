#!/usr/bin/env python3
"""Matcher bibliográfico conservador CLEP v3.1-compatible.

Reglas congeladas recuperadas del piloto:
- título efectivo = max(título completo, título principal antes de ':');
- IDENTIFICADO requiere título >= .90;
- cobertura de responsables >= .50;
- precisión de responsables >= .25;
- una incompatibilidad explícita de tipo bloquea identificación;
- PROBABLE nunca autoriza publicación automática.

No usa aprendizaje automático ni IA generativa.
"""
from __future__ import annotations
import re, unicodedata
from difflib import SequenceMatcher

BOOK={"book","monograph","edited-book","reference-book","book-series"}
ARTICLE={"article","journal-article","proceedings-article","posted-content"}
THESIS={"thesis","dissertation"}
REPORT={"report","report-series","standard"}
CHAPTER={"chapter","book-chapter","book-section","reference-entry"}

def norm(s):
    s=unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()
    s=re.sub(r"\b(the|a|an|el|la|los|las|un|una|unos|unas)\b"," ",s)
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def principal(title):
    return (title or "").split(":",1)[0].strip()

def ratio(a,b):
    a,b=norm(a),norm(b)
    if not a or not b:return 0.0
    return SequenceMatcher(None,a,b).ratio()

def title_scores(hist,cand):
    full=ratio(hist,cand)
    hp,cp=principal(hist),principal(cand)
    main=max(ratio(hp,cand),ratio(hist,cp),ratio(hp,cp))
    return full,main,max(full,main)

def people(raw):
    if isinstance(raw,list): xs=raw
    else: xs=re.split(r"\s*;\s*|\s+and\s+|\s+y\s+",raw or "")
    return [x.strip() for x in xs if x and x.strip()]

def person_key(name):
    toks=[x for x in norm(name).split() if len(x)>1]
    if not toks:return ""
    # surname signal plus initials/tokens; handles R. M. Goodwin vs Richard M. Goodwin
    return toks[-1]

def person_metrics(hist,cand):
    h,c=people(hist),people(cand)
    if not h:
        return 1.0,1.0,[],[]
    hk=[person_key(x) for x in h]; ck=[person_key(x) for x in c]
    matched_h=set(); matched_c=set()
    for i,a in enumerate(hk):
        for j,b in enumerate(ck):
            if a and b and a==b:
                matched_h.add(i); matched_c.add(j)
    coverage=len(matched_h)/len(h) if h else 1.0
    precision=len(matched_c)/len(c) if c else 0.0
    missing=[h[i] for i in range(len(h)) if i not in matched_h]
    extra=[c[j] for j in range(len(c)) if j not in matched_c]
    return coverage,precision,missing,extra

def family(t):
    x=(t or "").strip().lower()
    if x in BOOK:return "book"
    if x in ARTICLE:return "article"
    if x in THESIS:return "thesis"
    if x in REPORT:return "report"
    if x in CHAPTER:return "chapter"
    if x in {"","unknown","other"}:return "unknown"
    return x

def type_relation(hist,cand):
    h,c=family(hist),family(cand)
    if h=="unknown" or c=="unknown":return "unknown"
    return "compatible" if h==c else "incompatible"

def evaluate(hist,cand):
    full,main,effective=title_scores(hist.get("title",""),cand.get("title",""))
    coverage,precision,missing,extra=person_metrics(hist.get("authors",""),cand.get("authors",""))
    rel=type_relation(hist.get("type",""),cand.get("type",""))
    has_hist_people=bool(people(hist.get("authors","")))
    identified=(effective>=.90 and rel!="incompatible" and
                ((coverage>=.50 and precision>=.25) if has_hist_people else effective>=.98))
    probable=(not identified and effective>=.80 and rel!="incompatible" and
              ((coverage>=.50) if has_hist_people else effective>=.90))
    status="IDENTIFICADO" if identified else ("PROBABLE" if probable else "SIN_IDENTIFICAR")
    return {
      "status":status,"title_full":round(full,4),"title_main":round(main,4),
      "title_effective":round(effective,4),"coverage":round(coverage,4),
      "precision":round(precision,4),"type_relation":rel,
      "missing_people":missing,"extra_people":extra,
      "rescued_by_main":main>=.90 and full<.90
    }
