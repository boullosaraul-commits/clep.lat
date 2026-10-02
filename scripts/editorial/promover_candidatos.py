#!/usr/bin/env python3
"""Promueve candidatos OA verificados a cola CLEP con ficha determinista."""
import csv,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts/editorial"))
from generar_ficha_paper import ficha_paper
C=ROOT/"data/editorial/candidatos.csv"; Q=ROOT/"data/editorial/cola.csv"

def year(r):
    m=re.search(r"\b(19|20)\d{2}\b",r.get("published_at","") or "")
    return m.group(0) if m else ""

def main():
    with C.open(encoding="utf-8",newline="") as f: cs=list(csv.DictReader(f))
    with Q.open(encoding="utf-8",newline="") as f: qs=list(csv.DictReader(f)); fields=f.fieldnames
    existing={r["url_id"] for r in qs if r.get("url_id")}
    n=0
    for r in cs:
        if r.get("oa_status")!="VERIFICADO" or r.get("status") not in {"OA_VERIFICADO","EVALUADO"}: continue
        if r["candidate_id"] in existing: continue
        meta={"title":r["title"],"authors":r["authors"],"summary":r["summary"],
              "summary_es":r.get("summary_es",""),"translation_label":"ES · Traducción automática",
              "access_url":r["access_url"],"doi":r["doi"],"year":year(r),"venue":"",
              "oa_status":"VERIFICADO"}
        try:ficha=ficha_paper(meta)
        except ValueError:continue
        q={k:"" for k in fields}
        q.update({"editorial_id":"ED-"+r["candidate_id"].removeprefix("CAND-"),
          "flujo_editorial":"novedad","prioridad":r["priority"] or "100","estado_editorial":"FICHA_LISTA",
          "url_id":r["candidate_id"],"url_original":r["source_url"],"titulo_original":r["title"],
          "responsables":r["authors"],"tipo_recurso":"paper","anio":year(r),"idioma_obra":r["language"],
          "obra_estado":"OBRA_VERIFICADA","edicion_estado":"EDICION_VERIFICADA","oa_estado":"OA_VERIFICADO",
          "doi":r["doi"],"oa_url":r["access_url"],"oa_fuente":"RePEc/ReDIF",
          "area_clep":r["area_clep"],"sinopsis_es":r.get("summary_es",""),"ficha_es":ficha,
          "notas":f"Origen {r['source_id']}; ficha automática sin IA generativa."})
        qs.append(q);existing.add(r["candidate_id"]);r["status"]="FICHA_LISTA";n+=1
    with Q.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(qs)
    with C.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cs[0].keys());w.writeheader();w.writerows(cs)
    print(f"Promovidos a FICHA_LISTA: {n}")

if __name__=="__main__":main()
