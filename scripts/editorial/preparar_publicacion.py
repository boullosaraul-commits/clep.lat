#!/usr/bin/env python3
"""Preparación editorial atómica CLEP: texto + visual + procedencia.

Sólo esta etapa certifica una candidatura como FICHA_LISTA. No usa IA
generativa. Para visuales aplica:
  imagen oficial con derechos verificados > gráfica determinista > tarjeta CLEP.
"""
from __future__ import annotations
import csv, hashlib, json, mimetypes, re, shutil, subprocess, sys, urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts/editorial"))
from renderizar_texto import render as render_text
from generar_tarjeta_clep import render as render_card
from generar_grafica_clep import render as render_chart

C=ROOT/"data/editorial/candidatos.csv"
Q=ROOT/"data/editorial/cola.csv"
MEDIA=ROOT/"data/editorial/media"
UA="CLEP-editorial/2.1 (+https://clep.lat)"

def clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def year(r):
    x=clean(r.get("publication_year"))
    if re.fullmatch(r"(?:18|19|20)\d{2}",x):return x
    m=re.search(r"\b(?:18|19|20)\d{2}\b",r.get("published_at") or "")
    return m.group(0) if m else ""
def source_name(r):return clean(r.get("source_name") or r.get("official_source") or r.get("source_id") or r.get("source_type") or "Fuente verificada")
def ctype(r):return clean(r.get("content_type") or ("paper" if r.get("source_type") in {"nep_report","rss"} else "recurso"))
def access(r):return clean(r.get("access_url") or r.get("source_url"))

def meta_for(kind,r):
    u=access(r)
    if kind=="paper":
        return {"title":clean(r.get("title")),"authors":clean(r.get("authors")),
                "source_or_series":clean(r.get("venue") or source_name(r)),"year":year(r),"access_url":u}
    if kind=="book":
        return {"title":clean(r.get("title")),"authors_or_editors":clean(r.get("authors")),
                "year":year(r),"access_url":u}
    if kind=="chapter":
        return {"title":clean(r.get("title")),"authors":clean(r.get("authors")),
                "container_title":clean(r.get("venue") or source_name(r)),"year":year(r),"access_url":u}
    if kind in {"report","policy_brief"}:
        return {"title":clean(r.get("title")),"authors_or_institution":clean(r.get("authors") or r.get("venue") or source_name(r)),
                "year":year(r),"access_url":u}
    if kind=="special_issue":
        return {"title":clean(r.get("title")),"journal":clean(r.get("venue") or source_name(r)),
                "year":year(r),"access_url":u}
    if kind=="thesis":
        return {"title":clean(r.get("title")),"authors":clean(r.get("authors")),
                "institution":clean(r.get("venue") or source_name(r)),"year":year(r),"access_url":u}
    if kind=="edition_translation":
        note="traducción" if "edition_event=translation" in (r.get("notes") or "") else clean(re.search(r"edition_number=([^|]+)",r.get("notes") or "").group(1) if re.search(r"edition_number=([^|]+)",r.get("notes") or "") else "nueva edición")
        return {"title":clean(r.get("title")),"authors_or_editors":clean(r.get("authors")),
                "edition_note":note,"year":year(r),"access_url":u}
    if kind=="dataset_grafica":
        return {"indicator_or_dataset":clean(r.get("indicator_or_dataset") or r.get("title")),
                "geography":clean(r.get("geography")),"reference_period":clean(r.get("reference_period")),
                "value_or_change":clean(r.get("value_or_change")),"official_source":source_name(r),"access_url":u}
    if kind=="convocatoria_evento":
        return {"title":clean(r.get("title")),"organizer":clean(r.get("organizer") or source_name(r)),
                "date_or_deadline":clean(r.get("date_or_deadline")),"access_url":u,"date_label":"Fecha"}
    if kind=="video":
        return {"title":clean(r.get("title")),"speaker_or_organization":clean(r.get("speaker_or_organization") or r.get("authors") or source_name(r)),
                "access_url":u}
    if kind=="recurso":
        return {"title":clean(r.get("title")),"source":source_name(r),"access_url":u}
    raise ValueError(f"tipo no soportado: {kind}")

def eligible(r,kind):
    # La preparación nunca sustituye a la decisión de pertinencia.
    if r.get("status") not in {"OA_VERIFICADO","EVALUADO","LISTO"}:return False
    try: relevance=int(r.get("relevance_score") or 0)
    except ValueError: relevance=0
    if relevance < 15:return False
    if kind in academic:
        try: editorial=float(r.get("editorial_score") or 0)
        except ValueError: editorial=0.0
        if editorial < 7.0 or r.get("editorial_decision") not in {"PUBLISHABLE","OUTSTANDING"}:return False
    if r.get("source_id")=="doab-economics" or r.get("source_type") in {"doab_oai","doab_rest","crossref_academic","academic_oai"}:
        if "decision=PROMOCION_AUTOMATICA" not in (r.get("relevance_reasons") or ""):return False
    if not clean(r.get("title")) or not access(r):return False
    academic={"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"}
    if kind in academic:
        if r.get("oa_status") not in {"VERIFICADO","VERIFICADO_FUENTE","OA_VERIFICADO"} or not year(r):return False
        if r.get("access_status") not in {"PUBLIC_ACCESS_VERIFIED","VERIFICADO"}:return False
        if kind in {"paper","book","chapter","thesis","edition_translation"} and not clean(r.get("authors")):return False
        return True
    return r.get("access_status") in {"OFFICIAL_SOURCE_VERIFIED","PUBLIC_ACCESS_VERIFIED","VERIFICADO"} or clean(r.get("source_url")).startswith("https://")

def download_verified_image(r):
    url=clean(r.get("official_image_url"));rights=clean(r.get("official_image_rights"))
    if not url or rights!="VERIFICADO" or urlparse(url).scheme!="https":return None
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"image/*"})
    with urllib.request.urlopen(req,timeout=35) as resp:
        ctype=(resp.headers.get("Content-Type") or "").split(";",1)[0].lower()
        if ctype not in {"image/png","image/jpeg","image/webp"}:raise ValueError("imagen oficial no es PNG/JPEG/WebP")
        data=resp.read(12_000_001)
        if len(data)>12_000_000:raise ValueError("imagen oficial excede 12 MB")
    ext={"image/png":".png","image/jpeg":".jpg","image/webp":".webp"}[ctype]
    dig=hashlib.sha256(data).hexdigest()[:16]
    rel=f"data/editorial/media/{r['candidate_id']}-official-{dig}{ext}"
    (ROOT/rel).write_bytes(data)
    return {"media_type":ctype,"media_path":rel,"media_source":clean(r.get("official_image_source") or url),
            "media_rights_status":"VERIFICADO","alt_text":clean(r.get("title"))}

def capture_official_landing(r):
    """Captura determinista de la landing oficial con Chrome headless.

    No se presenta como imagen con licencia reutilizable: queda registrada como
    CAPTURA_LANDING_OFICIAL y sólo se usa para representar el recurso enlazado.
    Si Chrome no está disponible o la página falla, se usa la tarjeta CLEP.
    """
    url=clean(r.get("source_url") or r.get("access_url"))
    if not url or urlparse(url).scheme!="https":return None
    chrome=shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if not chrome:return None
    dig=hashlib.sha256(url.encode()).hexdigest()[:16]
    rel=f"data/editorial/media/{r['candidate_id']}-landing-{dig}.png"
    out=ROOT/rel
    cmd=[chrome,"--headless=new","--disable-gpu","--no-sandbox","--disable-dev-shm-usage",
         "--hide-scrollbars","--window-size=1200,1500","--virtual-time-budget=5000",
         f"--screenshot={out}",url]
    try:
        subprocess.run(cmd,check=True,timeout=35,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except Exception:return None
    if not out.is_file() or out.stat().st_size<5000:return None
    return {"media_type":"image/png","media_path":rel,"media_source":url,
            "media_rights_status":"CAPTURA_LANDING_OFICIAL",
            "alt_text":f"Captura de la página oficial: {clean(r.get('title'))}"}

def deterministic_visual(kind,r):
    if kind=="dataset_grafica" and clean(r.get("data_points_json")):
        try:points=json.loads(r["data_points_json"])
        except Exception:points=[]
        if len(points)>=2:
            svg=render_chart({"title":clean(r.get("indicator_or_dataset") or r.get("title")),
                              "geography":clean(r.get("geography")),"source":source_name(r),"points":points})
            mode="chart"
        else:svg=None
    else:svg=None
    if svg is None:
        label={"paper":"PAPER ABIERTO · CLEP","book":"LIBRO ABIERTO · CLEP",
               "chapter":"CAPÍTULO ABIERTO · CLEP","report":"INFORME ABIERTO · CLEP",
               "policy_brief":"POLICY BRIEF · CLEP","special_issue":"NÚMERO ESPECIAL · CLEP",
               "thesis":"TESIS ABIERTA · CLEP","edition_translation":"NUEVA EDICIÓN / TRADUCCIÓN · CLEP",
               "dataset_grafica":"DATOS · CLEP","convocatoria_evento":"AGENDA · CLEP",
               "video":"VIDEO · CLEP","recurso":"RECURSO · CLEP"}.get(kind,"CLEP")
        y=year(r)
        meta=" · ".join(x for x in [clean(r.get("authors")),clean(r.get("geography")),y] if x)
        svg=render_card({"label":label,"title":clean(r.get("title") or r.get("indicator_or_dataset")),
                         "meta":meta,"source":source_name(r)})
        mode="card"
    dig=hashlib.sha256(svg.encode()).hexdigest()[:16]
    rel=f"data/editorial/media/{r['candidate_id']}-{mode}-{dig}.svg"
    (ROOT/rel).write_text(svg,encoding="utf-8")
    return {"media_type":"image/svg+xml","media_path":rel,"media_source":f"CLEP deterministic {mode}",
            "media_rights_status":"PROPIO_DETERMINISTA","alt_text":f"{'Gráfica' if mode=='chart' else 'Tarjeta'} CLEP: {clean(r.get('title') or r.get('indicator_or_dataset'))}"}

def main():
    MEDIA.mkdir(parents=True,exist_ok=True)
    with C.open(encoding="utf-8",newline="") as f:
        cr=csv.DictReader(f);candidates=list(cr);cfields=cr.fieldnames
    with Q.open(encoding="utf-8",newline="") as f:
        qr=csv.DictReader(f);queue=list(qr);qfields=qr.fieldnames
    existing={r.get("url_id","") for r in queue};prepared=blocked=0
    for r in candidates:
        if r.get("candidate_id") in existing:continue
        kind=ctype(r)
        if not eligible(r,kind):continue
        try:
            meta=meta_for(kind,r);text=render_text(kind,meta)
            visual=download_verified_image(r) or capture_official_landing(r) or deterministic_visual(kind,r)
        except Exception as e:
            r["notes"]=((r.get("notes") or "")+f" | preparación bloqueada: {type(e).__name__}: {e}").strip(" |")
            blocked+=1;continue
        q={k:"" for k in qfields}
        q.update({
          "editorial_id":"ED-"+r["candidate_id"].removeprefix("CAND-"),"flujo_editorial":r.get("flujo_editorial") or "novedad",
          "prioridad":r.get("priority") or "100","estado_editorial":"FICHA_LISTA","url_id":r["candidate_id"],
          "url_original":r.get("source_url",""),"titulo_original":clean(r.get("title")),"responsables":clean(r.get("authors")),
          "tipo_recurso":kind,"anio":year(r),"idioma_obra":r.get("language",""),
          "obra_estado":"OBRA_VERIFICADA","edicion_estado":"EDICION_VERIFICADA" if kind in {"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"} else "NO_APLICA",
          "oa_estado":"OA_VERIFICADO" if kind in {"paper","book","chapter","report","policy_brief","special_issue","thesis","edition_translation"} else "NO_APLICA","doi":r.get("doi",""),
          "oa_url":access(r),"oa_fuente":source_name(r),"area_clep":r.get("area_clep",""),
          "licencia":clean((re.search(r"license_url=([^|;\s]+)",r.get("notes") or "") or [None,""])[1]),
          "ficha_es":text,"notas":f"Origen {source_name(r)}; relevance_score={r.get('relevance_score') or '0'}; editorial_score={r.get('editorial_score') or '0'}; editorial_decision={r.get('editorial_decision') or ''}; venue={clean(r.get('venue'))}; preparación atómica determinista sin IA generativa.",
          "text_method":"deterministic_template","text_template":kind,"text_status":"VERIFICADO",**visual
        })
        queue.append(q);existing.add(r["candidate_id"]);r["status"]="FICHA_LISTA";prepared+=1
    with Q.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=qfields);w.writeheader();w.writerows(queue)
    with C.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cfields);w.writeheader();w.writerows(candidates)
    print(f"Preparados atómicamente: {prepared}; bloqueados: {blocked}")

if __name__=="__main__":main()
