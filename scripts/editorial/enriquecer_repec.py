#!/usr/bin/env python3
"""Enriquece candidatos NEP desde el espejo ReDIF oficial de RePEc.

RePEc recomienda obtener los metadatos básicos desde los archivos editoriales
o, para acceso agregado, mediante rsync.repec.org. Este script sincroniza sólo
las series necesarias para el lote pendiente, localiza el Handle exacto y
extrae campos ReDIF declarados. No raspa IDEAS y no infiere acceso abierto.
"""
import csv, html, os, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"data/editorial/candidatos.csv"
LIMIT=int(os.getenv("REPEC_ENRICH_LIMIT","40"))
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

def sync_series(series_pairs,dest):
    if not shutil.which("rsync"):
        raise RuntimeError("rsync no está instalado")
    args=["rsync","-r","--timeout=30","--contimeout=15","--prune-empty-dirs"]
    # Una sola conexión al módulo; sólo se atraviesan archivos/series solicitados.
    for archive in sorted({a for a,_ in series_pairs}):
        args += [f"--include=/{archive}/"]
        for a,series in sorted(series_pairs):
            if a==archive:
                args += [f"--include=/{archive}/{series}/",
                         f"--include=/{archive}/{series}/*.rdf",
                         f"--include=/{archive}/{series}/*.redif"]
    args += ["--exclude=*",RSYNC,str(dest)+"/"]
    cp=subprocess.run(args,text=True,capture_output=True,timeout=180)
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
    fields={}
    last=None
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
        # Evitar parsear bloques que no contienen ningún handle solicitado.
        low=text.lower()
        relevant=[h for h in wanted_low if h in low]
        if not relevant:continue
        for block in records(text):
            f=parse_record(block)
            handles=f.get("handle") or []
            if not handles:continue
            h=handles[0].strip().lower()
            if h in wanted_low:found[wanted_low[h]]=f
    return found

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
    # Preferir PDF, sin asumir que sea OA; verificar_oa.py comprobará acceso.
    for u in urls:
        if u.lower().split("?",1)[0].endswith(".pdf"):return u
    return urls[0] if urls else ""

def main():
    with P.open(encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh);rows=list(rd);fields=rd.fieldnames
    pending=[r for r in rows if r.get("source_type")=="nep_report" and handle_of(r) and not (r.get("title") or "").strip()]
    batch=pending[:LIMIT]
    handles=[handle_of(r) for r in batch]
    pairs={series_of(h) for h in handles};pairs.discard(("",""))
    found={}
    if pairs:
        try:
            with tempfile.TemporaryDirectory(prefix="clep-repec-") as td:
                dest=Path(td)
                sync_series(pairs,dest)
                found=build_index(dest,handles)
        except Exception as e:
            print(f"RePEc rsync ERROR: {type(e).__name__}: {e}")
    enriched=failed=0
    for r in batch:
        h=handle_of(r);f=found.get(h)
        if not f:
            r["notes"]=((r.get("notes") or "")+" | RePEc ReDIF pendiente: handle no localizado en lote rsync.").strip(" |")
            failed+=1;continue
        title=first(f,"title")
        if not title:
            failed+=1;continue
        r["source_item_id"]=h;r["title"]=title
        r["authors"]="; ".join(dict.fromkeys(x.strip() for x in (f.get("author-name") or []) if x.strip()))
        r["summary"]=first(f,"abstract")
        r["language"]=first(f,"language")
        r["doi"]=first(f,"doi").replace("https://doi.org/","").replace("http://doi.org/","")
        r["access_url"]=choose_file(f)
        y=year_of(f);r["published_at"]=first(f,"creation-date","year") or y;r["publication_year"]=y
        r["venue"]=first(f,"journal","provider-name","series-name")
        r["content_type"]="paper";r["source_name"]="RePEc ReDIF"
        r["status"]="METADATOS_OBTENIDOS"
        r["notes"]=((r.get("notes") or "")+" | Metadatos obtenidos del espejo ReDIF oficial de RePEc; OA aún por verificar.").strip(" |")
        enriched+=1
    with P.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"RePEc ReDIF: intentados={len(batch)}; enriquecidos={enriched}; pendientes/error={failed}; backlog={max(0,len(pending)-len(batch))}")

if __name__=="__main__":main()
