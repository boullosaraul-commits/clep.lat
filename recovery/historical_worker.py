#!/usr/bin/env python3
"""Worker diario de recuperación histórica de CLEP.

Principios:
- examina como máximo N publicaciones históricas no resueltas por ejecución;
- no usa IA generativa;
- sólo prepara un reemplazo cuando identifica la obra de forma conservadora
  y una fuente bibliográfica declara acceso abierto;
- NUNCA elimina la publicación original. El retiro pertenece a una fase
  posterior, después de que el reemplazo haya sido publicado y verificado.

Fuentes de descubrimiento: Facebook Graph API y OpenAlex.
Estado persistente: recovery/state/historical_recovery.json.
Salida editorial: data/editorial/cola.csv.
"""
from __future__ import annotations
import csv, json, os, re, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/"recovery/config.json"
STATE=ROOT/"recovery/state/historical_recovery.json"
COLA=ROOT/"data/editorial/cola.csv"
API=os.getenv("META_GRAPH_VERSION","v26.0")

def get_json(url, headers=None):
    req=Request(url,headers=headers or {"User-Agent":"CLEP-recovery/1.0"})
    with urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def norm(s):
    s=unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def title_from_message(message):
    # Sólo acepta una primera línea razonablemente bibliográfica; no inventa título.
    for raw in (message or "").splitlines():
        line=raw.strip(" \t-–—•")
        if 8 <= len(line) <= 300 and not line.lower().startswith(("http://","https://")):
            return line
    return ""

def facebook_posts(page, token):
    fields="id,message,created_time,permalink_url"
    url=f"https://graph.facebook.com/{API}/{page}/posts?fields={quote(fields)}&limit=100&access_token={quote(token)}"
    while url:
        data=get_json(url)
        for p in data.get("data",[]): yield p
        url=data.get("paging",{}).get("next")

def openalex_candidates(title):
    url="https://api.openalex.org/works?search="+quote(title)+"&per-page=10"
    mail=os.getenv("OPENALEX_MAILTO","").strip()
    if mail: url += "&mailto="+quote(mail)
    return get_json(url).get("results",[])

def identify(title):
    nt=norm(title)
    if not nt: return None
    for w in openalex_candidates(title):
        wt=w.get("display_name") or w.get("title") or ""
        nwt=norm(wt)
        # Conservador: igualdad normalizada o contención sólo para títulos largos.
        exact=(nt==nwt)
        contained=min(len(nt),len(nwt))>=45 and (nt in nwt or nwt in nt)
        if not (exact or contained): continue
        oa=w.get("open_access") or {}
        if not oa.get("is_oa"): continue
        loc=w.get("best_oa_location") or w.get("primary_location") or {}
        access=loc.get("landing_page_url") or loc.get("pdf_url") or ""
        if not access.startswith("https://"): continue
        authors=[]
        for a in w.get("authorships") or []:
            name=((a.get("author") or {}).get("display_name") or "").strip()
            if name: authors.append(name)
        doi=(w.get("doi") or "").replace("https://doi.org/","")
        return {"title":wt,"authors":"; ".join(authors),"year":str(w.get("publication_year") or ""),
                "doi":doi,"access_url":access,"openalex_id":w.get("id") or "",
                "oa_status":oa.get("oa_status") or "oa"}
    return None

def load_state():
    if not STATE.exists(): return {"version":1,"posts":{}}
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def load_queue():
    with COLA.open(encoding="utf-8",newline="") as f:
        r=csv.DictReader(f); return list(r),r.fieldnames

def ficha(hit):
    bits=[hit["title"]]
    meta=" · ".join(x for x in [hit["authors"],hit["year"]] if x)
    if meta: bits+=["",meta]
    bits+=["","Acceso abierto:",hit["access_url"]]
    if hit["doi"]: bits+=["","DOI:",hit["doi"]]
    return "\n".join(bits)

def enqueue(post, title, hit):
    rows,fields=load_queue()
    pid=str(post["id"])
    if any(r.get("post_original_id")==pid for r in rows): return False
    row={k:"" for k in fields}
    row.update({
      "editorial_id":"hist-"+pid.replace("_","-"),"flujo_editorial":"archivo_historico",
      "prioridad":"1","estado_editorial":"FICHA_LISTA","post_original_id":pid,
      "post_original_url":post.get("permalink_url",""),"fecha_original":post.get("created_time",""),
      "titulo_original":title,"titulo_es":hit["title"],"responsables":hit["authors"],
      "rol_responsables":"author","anio":hit["year"],"obra_estado":"IDENTIFICADO",
      "edicion_estado":"POR_VERIFICAR","oa_estado":"VERIFICADO_FUENTE",
      "doi":hit["doi"],"oa_url":hit["access_url"],"oa_fuente":"OpenAlex",
      "ficha_es":ficha(hit),"original_retirado":"false",
      "notas":"Recuperación automática determinista; coincidencia conservadora de título; OA declarado por OpenAlex; original NO retirar hasta verificar reemplazo publicado."
    })
    rows.append(row)
    with COLA.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    return True

def main():
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))["historical_recovery"]
    limit=int(cfg.get("daily_search_batch",10))
    token=os.environ["CLEP_FB_TOKEN"]; page=os.environ["CLEP_FB_PAGE_ID"]
    state=load_state(); seen=state.setdefault("posts",{})
    checked=found=0
    for post in facebook_posts(page,token):
        if checked>=limit: break
        pid=str(post.get("id",""))
        old=seen.get(pid,{})
        if old.get("status") in {"MATCHED","QUEUED"}: continue
        title=title_from_message(post.get("message",""))
        if not title:
            # No consume cupo: no hay base textual suficiente para una búsqueda segura.
            seen[pid]={"status":"NEEDS_ATTACHMENT_METADATA","last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        checked+=1
        try:
            hit=identify(title)
        except Exception as e:
            seen[pid]={"status":"SEARCH_ERROR","title":title,"error":type(e).__name__,
                       "last_checked":datetime.now(timezone.utc).isoformat()}
            time.sleep(1); continue
        if not hit:
            seen[pid]={"status":"NOT_FOUND","title":title,"last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        queued=enqueue(post,title,hit)
        found+=1
        seen[pid]={"status":"QUEUED" if queued else "MATCHED","title":title,
                   "openalex_id":hit["openalex_id"],"access_url":hit["access_url"],
                   "last_checked":datetime.now(timezone.utc).isoformat()}
        time.sleep(1)
    state["last_run"]=datetime.now(timezone.utc).isoformat()
    state["last_run_checked"]=checked; state["last_run_found"]=found
    save_state(state)
    print(f"Histórico: examinados={checked}, encontrados={found}. Originales retirados=0.")

if __name__=="__main__": main()
