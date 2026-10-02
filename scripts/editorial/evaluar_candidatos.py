#!/usr/bin/env python3
"""Evaluación editorial determinista. El puntaje mide pertinencia CLEP, no calidad."""
import csv,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"

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

def main():
    with P.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    evaluated=0
    for r in rows:
        if r.get("status") not in {"DETECTADO","EVALUADO","METADATOS_OBTENIDOS","OA_VERIFICADO"}:continue
        if r.get("source_type")=="statistical_watch" and int(r.get("relevance_score") or 0)>=100:
            r["status"]="EVALUADO";continue
        text=((r.get("title") or "")+" "+(r.get("summary") or "")).lower()
        score=0;reasons=[]
        if r.get("source_type")=="nep_report":
            score+=20;reasons.append("fuente_nep_curada")
        for term,pts in POS.items():
            if re.search(r"(?<!\w)"+re.escape(term)+r"(?!\w)",text):
                score+=pts;reasons.append(term)
        score=min(score,100)
        r["relevance_score"]=str(score)
        r["relevance_reasons"]=";".join(reasons) if reasons else "sin_coincidencias"
        r["status"]="EVALUADO"
        if score<MIN_AUTO:
            r["notes"]=((r.get("notes") or "")+" | pertinencia insuficiente para promoción automática").strip(" |")
        evaluated+=1
    with P.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"Evaluados: {evaluated}; umbral promoción automática={MIN_AUTO}")
if __name__=="__main__":main()
