#!/usr/bin/env python3
"""Enriquece candidatos NEP desde RePEc ReDIF con caché incremental persistente.

La red sólo se usa para handles que aún no están en caché. Cada serie se
sincroniza de forma independiente y un fallo no invalida las series ya
resueltas. La caché guarda exclusivamente metadatos ReDIF parseados, no copias
completas del espejo.
"""
import csv, html, json, os, re, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=Path(os.getenv("CLEP_CANDIDATES_PATH",str(ROOT/"data/editorial/candidatos.csv"))).resolve()
CACHE=Path(os.getenv("REPEC_CACHE_PATH",str(ROOT/"data/editorial/state/repec_cache.json"))).resolve()
LIMIT=int(os.getenv("REPEC_ENRICH_LIMIT","40"))
SERIES_LIMIT=max(1,int(os.getenv("REPEC_SYNC_SERIES_LIMIT","8")))
SYNC_TIMEOUT=max(20,int(os.getenv("REPEC_SYNC_TIMEOUT","70")))
RSYNC="rsync://rsync.repec.org/RePEc-ReDIF/"

def handle_from(value):
    value=(value or "").strip()
    if value.lower().startswith("repec:"):return value
    try:
        from urllib.parse import urlparse,parse_qs
        u=parse_qs(urlparse(value).query).get("u",[""])[0]
        return u if u.lower().startswith("repec:") else ""
    except Exception:return ""

def handle_of(r):
    h=handle_from(r.get("source_item_id")) or handle_from(r.get("source_url"))
    if h:return h
    m=re.search(r"RePEc:[^\s|]+",r.get("notes") or "",flags=re.I)
    return m.group(0) if m else ""

def series_of(handle):
    p=handle.split(":")
    return (p[1].lower(),p[2].lower()) if len(p)>=4 else ("","")

def sync_one_series(pair,dest):
    if not shutil.which("rsync"):raise RuntimeError("rsync no está instalado")
    archive,series=pair
    args=[
      "rsync","-r","--timeout=20","--contimeout=12","--prune-empty-dirs",
      f"--include=/{archive}/",f"--include=/{archive}/{series}/",
      f"--include=/{archive}/{series}/*.rdf",f"--include=/{archive}/{series}/*.redif",
      "--exclude=*",RSYNC,str(dest)+"/"
    ]
    cp=subprocess.run(args,text=True,capture_output=True,timeout=SYNC_TIMEOUT)
    if cp.returncode!=0:
        msg=(cp.stderr or cp.stdout or "").strip().replace("\n"," ")[:500]
        raise RuntimeError(f"rsync exit {cp.returncode}: {msg}")

def decode_file(path):
    data=path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):return data.decode("utf-8-sig","replace")
    if path.suffix.lower()==".redif":return data.decode("utf-8","replace")
    return data.decode("cp1252","replace")

def records(text):
    cur=[]
    for line in text.splitlines():
        if re.match(r"^Template-Type\s*:",line,re.I) and cur:
            yield cur;cur=[]
        if line.strip():cur.append(line.rstrip())
    if cur:yield cur

def parse_record(lines):
    fields={};last=None
    for raw in lines:
        if raw[:1].isspace() and last:
            fields[last][-1]+=" "+raw.strip();continue
        m=re.match(r"^([A-Za-z0-9-]+)\s*:\s*(.*)$",raw)
        if not m:continue
        k=m.group(1).lower();v=html.unescape(m.group(2).strip())
        fields.setdefault(k,[]).append(v);last=k
    return fields

def build_index(dest,wanted):
    wanted_low={h.lower():h for h in wanted};found={}
    for path in dest.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".rdf",".redif"}:continue
        try:text=decode_file(path)
        except Exception:continue
        low=text.lower()
        if not any(h in low for h in wanted_low):continue
        for block in records(text):
            f=parse_record(block);handles=f.get("handle") or []
            if not handles:continue
            h=handles[0].strip().lower()
            if h in wanted_low:found[wanted_low[h]]=f
    return found

def load_cache():
    if not CACHE.exists():return {"version":1,"handles":{},"updated_at":""}
    try:
        x=json.loads(CACHE.read_text(encoding="utf-8"))
        if not isinstance(x.get("handles"),dict):raise ValueError
        return x
    except Exception:return {"version":1,"handles":{},"updated_at":""}

def save_cache(cache):
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    cache["version"]=1;cache["updated_at"]=datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp=CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    tmp.replace(CACHE)

def first(f,*keys):
    for k in keys:
        vals=f.get(k) or []
        if vals:return vals[0].strip()
    return ""

def year_of(f):
    for s in (f.get("year") or [])+(f.get("creation-date") or [])+(f.get("revision-date") or []):
        m=re.search(r"\b(?:18|19|20)\d{2}\b",s)
        if m:return m.group(0)
    return ""

def choose_file(f):
    urls=f.get("file-url") or []
    for u in urls:
        if u.lower().split("?",1)[0].endswith(".pdf"):return u
    return urls[0] if urls else ""

def apply_metadata(r,h,f):
    title=first(f,"title")
    if not title:return False
    r["source_item_id"]=h;r["title"]=title
    r["authors"]="; ".join(dict.fromkeys(x.strip() for x in (f.get("author-name") or []) if x.strip()))
    r["summary"]=first(f,"abstract");r["language"]=first(f,"language")
    r["doi"]=first(f,"doi").replace("https://doi.org/","").replace("http://doi.org/","")
    r["access_url"]=choose_file(f)
    y=year_of(f);r["published_at"]=first(f,"creation-date","year") or y;r["publication_year"]=y
    r["venue"]=first(f,"journal","provider-name","series-name")
    r["content_type"]="paper";r["source_name"]="RePEc ReDIF";r["status"]="METADATOS_OBTENIDOS"
    note="Metadatos obtenidos del espejo ReDIF oficial de RePEc; OA aún por verificar."
    if note not in (r.get("notes") or ""):r["notes"]=((r.get("notes") or "")+" | "+note).strip(" |")
    return True

def main():
    with P.open(encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh);rows=list(rd);fields=rd.fieldnames
    pending=[r for r in rows if r.get("source_type")=="nep_report" and handle_of(r) and not (r.get("title") or "").strip()]
    batch=pending[:LIMIT];handles=[handle_of(r) for r in batch]
    cache=load_cache();cached=cache["handles"];found={}
    for h in handles:
        f=cached.get(h.lower())
        if isinstance(f,dict):found[h]=f

    missing=[h for h in handles if h not in found]
    by_pair={}
    for h in missing:
        pair=series_of(h)
        if pair!=("",""):by_pair.setdefault(pair,[]).append(h)

    sync_ok=sync_fail=0
    for pair,wanted in sorted(by_pair.items())[:SERIES_LIMIT]:
        try:
            with tempfile.TemporaryDirectory(prefix="clep-repec-") as td:
                dest=Path(td);sync_one_series(pair,dest);part=build_index(dest,wanted)
            for h,meta in part.items():
                found[h]=meta;cached[h.lower()]=meta
            sync_ok+=1
        except Exception as e:
            sync_fail+=1
            print(f"RePEc rsync WARN {pair[0]}/{pair[1]}: {type(e).__name__}: {e}")
    save_cache(cache)

    enriched=failed=cache_hits=0
    cached_keys={h.lower() for h in handles if h.lower() in cached}
    for r in batch:
        h=handle_of(r);f=found.get(h) or cached.get(h.lower())
        if not f:
            msg="RePEc ReDIF pendiente: handle no localizado; se conserva caché previa."
            if msg not in (r.get("notes") or ""):r["notes"]=((r.get("notes") or "")+" | "+msg).strip(" |")
            failed+=1;continue
        if h.lower() in cached_keys:cache_hits+=1
        if apply_metadata(r,h,f):enriched+=1
        else:failed+=1

    with P.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    untouched=max(0,len(pending)-len(batch))
    unsynced_pairs=max(0,len(by_pair)-SERIES_LIMIT)
    print(f"RePEc ReDIF incremental: intentados={len(batch)}; enriquecidos={enriched}; cache_hits={cache_hits}; pendientes/error={failed}; series_ok={sync_ok}; series_error={sync_fail}; series_diferidas={unsynced_pairs}; backlog={untouched}")

if __name__=="__main__":main()
