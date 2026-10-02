#!/usr/bin/env python3
"""Evaluación editorial determinista. El puntaje mide pertinencia CLEP, no calidad."""
import csv,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"

# Primera capa conservadora. Se ampliará por área/fuente.
POS={
 "monetary":15,"money":15,"macroeconomic":12,"macroeconomics":12,
 "development":12,"structural":10,"employment":10,"labour":10,"labor":10,
 "inequality":10,"distribution":10,"financial":10,"finance":8,
 "input-output":15,"social reproduction":20,"political economy":15,
 "economic history":10,"public finance":10,"industrial policy":12,
 "latin america":15,"mexico":15
}
def main():
    with P.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    for r in rows:
        if r.get("status") not in {"DETECTADO","EVALUADO"}: continue
        text=(r.get("title","")+" "+r.get("summary","")).lower()
        score=0; reasons=[]
        for term,pts in POS.items():
            if re.search(r"\b"+re.escape(term)+r"\b",text):
                score+=pts; reasons.append(term)
        score=min(score,100)
        r["relevance_score"]=str(score)
        r["relevance_reasons"]=";".join(reasons) if reasons else "sin_coincidencias"
        r["status"]="EVALUADO"
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys() if rows else [])
        if rows: w.writeheader(); w.writerows(rows)
    print(f"Evaluados: {len(rows)}")
if __name__=="__main__": main()
