#!/usr/bin/env python3
"""Recuperación histórica CLEP, conservadora y transaccional.

- procesa hasta N casos históricos buscables por ejecución;
- usa texto + metadatos de attachments de Facebook;
- identifica obras con matcher_v31 (título principal, responsables, barreras de tipo);
- busca bibliografía en OpenLibrary, Crossref y RePEc/IDEAS;
- verifica edición sólo con evidencia concreta (año/ISBN/DOI del histórico);
- resuelve OA mediante evidencia explícita de fuente o OpenAlex;
- prepara texto e imagen deterministas sólo cuando obra+edición+OA están verificados;
- nunca borra el post original; eso pertenece al cierre transaccional posterior.
"""
from __future__ import annotations
import csv, hashlib, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECOVERY_DIR=Path(__file__).resolve().parent
EDITORIAL_DIR=ROOT/"scripts"/"editorial"
for p in (RECOVERY_DIR,EDITORIAL_DIR):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from matcher_v31 import evaluate, family
from renderizar_texto import render as render_text
from generar_tarjeta_clep import render as render_card

CONFIG=ROOT/"recovery/config.json"
STATE=ROOT/"recovery/state/historical_recovery.json"
COLA=ROOT/"data/editorial/cola.csv"
MEDIA=ROOT/"data/editorial/media"
API=os.getenv("META_GRAPH_VERSION","v26.0")
UA="CLEP-recovery/3.1 (+https://clep.lat)"

def get(url,accept="application/json",limit=5_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
    with urllib.request.urlopen(req,timeout=35) as r:
        return r.read(limit),r.headers,r.geturl()

def get_json(url):
    b,_,_=get(url); return json.loads(b.decode("utf-8","replace"))

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(str(s or ""))).strip()

def extract_doi(s):
    m=re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",s or "",re.I)
    return m.group(0).rstrip(".,;)") if m else ""

def extract_isbns(s):
    vals=[]
    for x in re.findall(r"(?:97[89][\s-]?)?(?:\d[\s-]?){9}[\dXx]",s or ""):
        z=re.sub(r"[^0-9Xx]","",x).upper()
        if len(z) in {10,13}: vals.append(z)
    return sorted(set(vals))

def extract_year(s):
    m=re.search(r"\b(18|19|20)\d{2}\b",s or "")
    return m.group(0) if m else ""

def infer_type(s,attachment_type=""):
    t=(s or "").lower()
    for needles,out in [
      (("tesis","dissertation"),"thesis"),(("capítulo","capitulo","chapter"),"chapter"),
      (("artículo","articulo","paper","journal article"),"article"),
      (("informe","report"),"report"),(("libro","book"),"book")]:
        if any(x in t for x in needles): return out
    if attachment_type=="share": return "unknown"
    return "unknown"

def parse_authors(s):
    lines=(s or "").splitlines()
    for raw in lines[:12]:
        m=re.match(r"\s*(?:autor(?:es)?|author(?:s)?|editor(?:es|s)?)\s*[:\-]\s*(.+)$",raw,re.I)
        if m:return clean(re.sub(r"\s*(?:,|\band\b|\by\b)\s*","; ",m.group(1),flags=re.I))
    return ""

def plausible_title(s):
    for raw in (s or "").splitlines():
        line=raw.strip(" \t-–—•")
        if 8<=len(line)<=300 and not line.lower().startswith(("http://","https://","autor:","autores:","author:")):
            return clean(line)
    return ""

def attachment_text(post):
    out=[]
    for a in ((post.get("attachments") or {}).get("data") or []):
        for k in ("title","description"):
            if a.get(k): out.append(str(a[k]))
    return "\n".join(out)

def historical_meta(post):
    msg=post.get("message") or ""
    att=attachment_text(post)
    combined="\n".join(x for x in [msg,att] if x)
    title=plausible_title(msg) or plausible_title(att)
    atype=""
    data=((post.get("attachments") or {}).get("data") or [])
    if data: atype=data[0].get("type") or ""
    return {
      "title":title,"authors":parse_authors(combined),"type":infer_type(combined,atype),
      "year":extract_year(combined),"doi":extract_doi(combined),"isbns":extract_isbns(combined),
      "raw":combined
    }

def facebook_posts(page,token):
    fields="id,message,created_time,permalink_url,attachments{type,title,description,url}"
    qs=urllib.parse.urlencode({"fields":fields,"limit":100,"access_token":token})
    url=f"https://graph.facebook.com/{API}/{page}/posts?{qs}"
    while url:
        data=get_json(url)
        yield from data.get("data",[])
        url=(data.get("paging") or {}).get("next")

def crossref_candidates(hist):
    params={"query.title":hist["title"],"rows":"10","select":"DOI,title,author,published,type,ISBN,URL,link,license"}
    if hist.get("authors"): params["query.author"]=hist["authors"].split(";")[0]
    u="https://api.crossref.org/works?"+urllib.parse.urlencode(params)
    items=(get_json(u).get("message") or {}).get("items") or []
    out=[]
    for x in items:
        title=((x.get("title") or [""])[0])
        authors=[]
        for a in x.get("author") or []:
            name=clean(" ".join(y for y in [a.get("given",""),a.get("family","")] if y))
            if name:authors.append(name)
        parts=((x.get("published") or {}).get("date-parts") or [[]])[0]
        year=str(parts[0]) if parts else ""
        links=x.get("link") or []
        pdf=next((z.get("URL","") for z in links if "pdf" in (z.get("content-type") or "").lower()),"")
        out.append({"source":"crossref","title":title,"authors":"; ".join(authors),"type":x.get("type") or "unknown",
                    "year":year,"doi":x.get("DOI") or "","isbns":x.get("ISBN") or [],
                    "access_url":pdf,"license":bool(x.get("license")),"source_url":x.get("URL") or ""})
    return out

def openlibrary_candidates(hist):
    p={"title":hist["title"],"limit":"10","fields":"key,title,author_name,first_publish_year,isbn"}
    if hist.get("authors"):p["author"]=hist["authors"].split(";")[0]
    docs=get_json("https://openlibrary.org/search.json?"+urllib.parse.urlencode(p)).get("docs") or []
    return [{"source":"openlibrary","title":d.get("title") or "","authors":"; ".join(d.get("author_name") or []),
             "type":"book","year":str(d.get("first_publish_year") or ""),"doi":"","isbns":d.get("isbn") or [],
             "access_url":"","license":False,"source_url":"https://openlibrary.org"+(d.get("key") or "")} for d in docs]

class RePEcLinks(HTMLParser):
    def __init__(self): super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag!="a":return
        href=dict(attrs).get("href","")
        if re.match(r"^/(?:p|a|b|c)/.+\.html$",href):self.links.append(href)

class MetaParser(HTMLParser):
    def __init__(self):super().__init__();self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag!="meta":return
        a={k.lower():v for k,v in attrs}
        k=(a.get("name") or a.get("property") or "").lower()
        if k and a.get("content"):self.meta.setdefault(k,[]).append(a["content"])

def repec_candidates(hist):
    q=urllib.parse.urlencode({"q":hist["title"],"cmd":"Search!"})
    try:
        body,_,_=get("https://ideas.repec.org/cgi-bin/htsearch?"+q,"text/html")
        p=RePEcLinks();p.feed(body.decode("utf-8","replace"))
    except Exception:return []
    out=[]
    for href in list(dict.fromkeys(p.links))[:8]:
        url=urllib.parse.urljoin("https://ideas.repec.org",href)
        try:
            b,_,_=get(url,"text/html");m=MetaParser();m.feed(b.decode("utf-8","replace"));md=m.meta
        except Exception:continue
        title=(md.get("citation_title") or md.get("dc.title") or [""])[0]
        authors=md.get("citation_author") or md.get("dc.creator") or []
        date=(md.get("citation_publication_date") or md.get("dc.date") or [""])[0]
        pdf=(md.get("citation_pdf_url") or [""])[0]
        doi=(md.get("citation_doi") or [""])[0]
        typ="book" if href.startswith("/b/") else ("article" if href.startswith("/a/") else "unknown")
        out.append({"source":"repec","title":title,"authors":"; ".join(authors),"type":typ,
                    "year":extract_year(date),"doi":doi,"isbns":[],"access_url":pdf,
                    "license":False,"source_url":url})
    return out

def public_https(url):
    if not (url or "").startswith("https://"):return False,""
    for method in ("HEAD","GET"):
        try:
            hdr={"User-Agent":UA}
            if method=="GET":hdr["Range"]="bytes=0-1023"
            req=urllib.request.Request(url,headers=hdr,method=method)
            with urllib.request.urlopen(req,timeout=25) as r:
                return True,r.geturl()
        except Exception:pass
    return False,""

def openalex_oa(hit):
    if hit.get("doi"):
        q="filter="+urllib.parse.quote("doi:https://doi.org/"+hit["doi"])
    else:
        q="search="+urllib.parse.quote(hit["title"])+"&per-page=5"
    try: items=get_json("https://api.openalex.org/works?"+q).get("results") or []
    except Exception:return None
    for w in items:
        if hit.get("doi") and (w.get("doi") or "").lower().endswith(hit["doi"].lower()):
            pass
        elif evaluate({"title":hit["title"],"authors":hit["authors"],"type":hit["type"]},
                      {"title":w.get("display_name") or "","authors":"; ".join(((a.get("author") or {}).get("display_name") or "") for a in w.get("authorships") or []),"type":w.get("type") or "unknown"})["status"]!="IDENTIFICADO":
            continue
        if not (w.get("open_access") or {}).get("is_oa"):continue
        loc=w.get("best_oa_location") or {}
        u=loc.get("pdf_url") or loc.get("landing_page_url") or ""
        ok,final=public_https(u)
        if ok:return {"url":final,"evidence":"OpenAlex OA","oa_status":(w.get("open_access") or {}).get("oa_status") or "oa"}
    return None

def edition_verified(hist,hit):
    if hist.get("doi") and hit.get("doi"):
        return hist["doi"].lower()==hit["doi"].lower(),"doi"
    hi=set(hist.get("isbns") or []);ci={re.sub(r"[^0-9Xx]","",x).upper() for x in hit.get("isbns") or []}
    if hi and ci and hi&ci:return True,"isbn"
    if hist.get("year") and hit.get("year") and hist["year"]==hit["year"]:return True,"year"
    return False,""

def resolve_oa(hit):
    # Explicit Crossref license + reachable registered PDF.
    if hit["source"]=="crossref" and hit.get("license") and hit.get("access_url"):
        ok,u=public_https(hit["access_url"])
        if ok:return {"url":u,"evidence":"Crossref license + registered PDF"}
    # RePEc/IDEAS citation PDF is provider-declared scholarly access.
    if hit["source"]=="repec" and hit.get("access_url"):
        ok,u=public_https(hit["access_url"])
        if ok:return {"url":u,"evidence":"RePEc/IDEAS citation PDF"}
    return openalex_oa(hit)

def best_match(hist):
    candidates=[]
    for fn in (openlibrary_candidates,crossref_candidates,repec_candidates):
        try:candidates.extend(fn(hist))
        except Exception as e:print(f"WARN {fn.__name__}: {type(e).__name__}",file=sys.stderr)
    scored=[]
    for c in candidates:
        m=evaluate(hist,c);c["match"]=m
        rank={"IDENTIFICADO":0,"PROBABLE":1,"SIN_IDENTIFICAR":2}[m["status"]]
        scored.append((rank,-m["title_effective"],-m["coverage"],-m["precision"],c))
    scored.sort(key=lambda x:x[:4])
    return scored[0][4] if scored else None

def load_state():
    if not STATE.exists():return {"version":2,"posts":{}}
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(s):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def load_queue():
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);return list(rd),rd.fieldnames

def enqueue(post,hist,hit,oa):
    rows,fields=load_queue();pid=str(post["id"])
    if any(r.get("post_original_id")==pid for r in rows):return False
    kind="book" if hit.get("type")=="book" else "paper"
    meta={"title":hit["title"],"authors_or_editors":hit["authors"],"year":hit["year"],"access_url":oa["url"]}
    text=render_text("book" if hit["type"]=="book" else "paper",
        meta if hit["type"]=="book" else {"title":hit["title"],"authors":hit["authors"],
        "source_or_series":hit["source"],"year":hit["year"],"access_url":oa["url"]})
    card=render_card({"label":"DEL ARCHIVO DE CLEP","title":hit["title"],
                      "meta":" · ".join(x for x in [hit["authors"],hit["year"]] if x),
                      "source":hit["source"]})
    MEDIA.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(card.encode()).hexdigest()[:16]
    rel=f"data/editorial/media/HIST-{pid.replace('_','-')}-{digest}.svg"
    (ROOT/rel).write_text(card,encoding="utf-8")
    row={k:"" for k in fields}
    row.update({
      "editorial_id":"hist-"+pid.replace("_","-"),"flujo_editorial":"archivo_historico","prioridad":"1",
      "estado_editorial":"FICHA_LISTA","post_original_id":pid,"post_original_url":post.get("permalink_url",""),
      "fecha_original":post.get("created_time",""),"titulo_original":hist["title"],"titulo_es":hit["title"],
      "responsables":hit["authors"],"rol_responsables":"author","tipo_recurso":kind,
      "anio":hit["year"],"obra_estado":"OBRA_VERIFICADA","edicion_estado":"EDICION_VERIFICADA",
      "oa_estado":"OA_VERIFICADO","doi":hit.get("doi",""),"isbn":";".join(hit.get("isbns") or []),
      "oa_url":oa["url"],"oa_fuente":oa["evidence"],"ficha_es":text,"original_retirado":"false",
      "media_type":"image/svg+xml","media_path":rel,"media_source":"CLEP deterministic card",
      "media_rights_status":"PROPIO_DETERMINISTA","alt_text":"Tarjeta CLEP: "+hit["title"],
      "text_method":"deterministic_template","text_template":kind,
      "text_status":"VERIFICADO",
      "notas":f"Recuperación v3.1; fuente bibliográfica {hit['source']}; OA: {oa['evidence']}; original conservar hasta reemplazo verificado."
    })
    rows.append(row)
    with COLA.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return True

def main():
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))["historical_recovery"]
    limit=int(cfg.get("daily_search_batch",10))
    token=os.environ["CLEP_FB_TOKEN"];page=os.environ["CLEP_FB_PAGE_ID"]
    state=load_state();seen=state.setdefault("posts",{})
    searched=queued=0
    for post in facebook_posts(page,token):
        if searched>=limit:break
        pid=str(post.get("id",""));old=seen.get(pid,{})
        if old.get("status") in {"QUEUED","ORIGINAL_RETIRADO"}:continue
        hist=historical_meta(post)
        if not hist["title"]:
            seen[pid]={"status":"NEEDS_ATTACHMENT_METADATA","last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        searched+=1
        try:hit=best_match(hist)
        except Exception as e:
            seen[pid]={"status":"SEARCH_ERROR","title":hist["title"],"error":type(e).__name__,
                       "last_checked":datetime.now(timezone.utc).isoformat()};continue
        if not hit or hit["match"]["status"]=="SIN_IDENTIFICAR":
            seen[pid]={"status":"SIN_IDENTIFICAR","title":hist["title"],"last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        if hit["match"]["status"]=="PROBABLE":
            seen[pid]={"status":"CANDIDATO_PROBABLE","title":hist["title"],"candidate":hit["title"],
                       "match":hit["match"],"last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        ed,why=edition_verified(hist,hit)
        if not ed:
            seen[pid]={"status":"OBRA_VERIFICADA","title":hist["title"],"candidate":hit["title"],
                       "match":hit["match"],"edition_status":"POR_VERIFICAR",
                       "last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        oa=resolve_oa(hit)
        if not oa:
            seen[pid]={"status":"EDICION_VERIFICADA","title":hist["title"],"candidate":hit["title"],
                       "match":hit["match"],"edition_evidence":why,"oa_status":"POR_VERIFICAR",
                       "last_checked":datetime.now(timezone.utc).isoformat()}
            continue
        try:did=enqueue(post,hist,hit,oa)
        except Exception as e:
            seen[pid]={"status":"PREPARATION_ERROR","title":hist["title"],"error":f"{type(e).__name__}: {e}",
                       "last_checked":datetime.now(timezone.utc).isoformat()};continue
        if did:queued+=1
        seen[pid]={"status":"QUEUED" if did else "MATCHED","title":hist["title"],"candidate":hit["title"],
                   "match":hit["match"],"edition_evidence":why,"oa_url":oa["url"],
                   "last_checked":datetime.now(timezone.utc).isoformat()}
        time.sleep(.5)
    state["last_run"]=datetime.now(timezone.utc).isoformat()
    state["last_run_searched"]=searched;state["last_run_queued"]=queued
    save_state(state)
    print(f"Histórico v3.1: buscados={searched}, preparados={queued}, originales retirados=0.")

if __name__=="__main__":main()
