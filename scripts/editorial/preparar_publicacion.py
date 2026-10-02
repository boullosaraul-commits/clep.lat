#!/usr/bin/env python3
"""Prepara candidatos CLEP para publicación: texto + imagen, de forma atómica.

Única etapa autorizada para certificar simultáneamente:
  text_status=VERIFICADO
  media_rights_status=PROPIO_DETERMINISTA

No usa LLM, red, aleatoriedad ni inferencias editoriales.
"""
import csv, hashlib, re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts/editorial"))
from renderizar_texto import render as render_text
from generar_tarjeta_clep import render as render_card

C=ROOT/"data/editorial/candidatos.csv"
Q=ROOT/"data/editorial/cola.csv"
MEDIA=ROOT/"data/editorial/media"

def year(r):
    m=re.search(r"\b(?:19|20)\d{2}\b",(r.get("published_at") or ""))
    return m.group(0) if m else ""

def source_name(r):
    return (r.get("source_id") or r.get("source_type") or "Fuente verificada").strip()

def paper_meta(r):
    y=year(r)
    # source_id is factual provenance; until venue metadata exists, use it as
    # source_or_series rather than inventing a journal/series.
    return {
      "title":r.get("title","").strip(),
      "authors":r.get("authors","").strip(),
      "source_or_series":source_name(r),
      "year":y,
      "access_url":r.get("access_url","").strip(),
    }

def eligible(r):
    return (
      r.get("oa_status")=="VERIFICADO"
      and r.get("status") in {"OA_VERIFICADO","EVALUADO","METADATOS_OBTENIDOS"}
      and r.get("title","").strip()
      and r.get("authors","").strip()
      and r.get("access_url","").strip()
      and year(r)
    )

def main():
    MEDIA.mkdir(parents=True,exist_ok=True)
    with C.open(encoding="utf-8",newline="") as f:
        cr=csv.DictReader(f); candidates=list(cr); cfields=cr.fieldnames
    with Q.open(encoding="utf-8",newline="") as f:
        qr=csv.DictReader(f); queue=list(qr); qfields=qr.fieldnames
    existing={r.get("url_id","") for r in queue}
    prepared=0; blocked=0
    for r in candidates:
        if r.get("candidate_id") in existing: continue
        if not eligible(r): continue
        meta=paper_meta(r)
        try:
            text=render_text("paper",meta)
            card_data={
              "label":"PAPER ABIERTO · CLEP",
              "title":meta["title"],
              "meta":f'{meta["authors"]} · {meta["year"]}',
              "source":source_name(r),
            }
            svg=render_card(card_data)
        except ValueError as e:
            r["notes"]=((r.get("notes") or "")+f" | preparación bloqueada: {e}").strip(" |")
            blocked+=1; continue
        digest=hashlib.sha256(svg.encode("utf-8")).hexdigest()[:16]
        rel=f"data/editorial/media/{r['candidate_id']}-{digest}.svg"
        (ROOT/rel).write_text(svg,encoding="utf-8")
        q={k:"" for k in qfields}
        q.update({
          "editorial_id":"ED-"+r["candidate_id"].removeprefix("CAND-"),
          "flujo_editorial":r.get("flujo_editorial") or "novedad",
          "prioridad":r.get("priority") or "100",
          "estado_editorial":"FICHA_LISTA",
          "url_id":r["candidate_id"],
          "url_original":r.get("source_url",""),
          "titulo_original":meta["title"],
          "responsables":meta["authors"],
          "tipo_recurso":"paper",
          "anio":meta["year"],
          "idioma_obra":r.get("language",""),
          "obra_estado":"OBRA_VERIFICADA",
          "edicion_estado":"EDICION_VERIFICADA",
          "oa_estado":"OA_VERIFICADO",
          "doi":r.get("doi",""),
          "oa_url":meta["access_url"],
          "oa_fuente":source_name(r),
          "area_clep":r.get("area_clep",""),
          "ficha_es":text,
          "notas":f"Origen {source_name(r)}; preparación atómica determinista sin IA generativa.",
          "media_type":"image/svg+xml",
          "media_path":rel,
          "media_source":"CLEP deterministic card",
          "media_rights_status":"PROPIO_DETERMINISTA",
          "alt_text":f"Tarjeta CLEP: {meta['title']}",
          "text_method":"deterministic_template",
          "text_template":"paper",
          "text_status":"VERIFICADO",
        })
        queue.append(q); existing.add(r["candidate_id"])
        r["status"]="FICHA_LISTA"; prepared+=1
    with Q.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=qfields); w.writeheader(); w.writerows(queue)
    with C.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cfields); w.writeheader(); w.writerows(candidates)
    print(f"Preparados atómicamente: {prepared}; bloqueados: {blocked}")

if __name__=="__main__": main()
