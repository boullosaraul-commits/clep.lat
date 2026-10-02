#!/usr/bin/env python3
"""Detector común de actualizaciones estadísticas CLEP.

Fuentes soportadas inicialmente:
- BLS Public Data API v2
- World Bank Indicators API v2
- IMF DataMapper API v2
- Eurostat Statistics API

Compara la última observación con estado persistente y sólo crea candidato
cuando cambia periodo o valor. No usa IA generativa.
"""
from __future__ import annotations
import csv, hashlib, json, math, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"data/editorial/monitoreo.json"
OUT=ROOT/"data/editorial/candidatos.csv"
STATE=ROOT/"data/editorial/state/statistical_updates.json"
UA="CLEP-editorial/2.0 (+https://clep.lat)"

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def fmt(v):
    if isinstance(v,str):
        try:v=float(v)
        except Exception:return v.strip()
    if isinstance(v,(int,float)):
        if not math.isfinite(float(v)):return ""
        x=round(float(v),3)
        return f"{x:g}"
    return str(v or "").strip()

def bls_latest(w):
    u=f"https://api.bls.gov/publicAPI/v2/timeseries/data/{urllib.parse.quote(w['series'])}?latest=true"
    d=get_json(u)
    series=((d.get("Results") or {}).get("series") or [])
    if not series or not series[0].get("data"):raise ValueError("BLS sin observación")
    x=series[0]["data"][0]
    period=x.get("periodName") or x.get("period") or ""
    ref=f"{period} {x.get('year','')}".strip()
    return {"period":ref,"value":x.get("value"),"points":[[ref,x.get("value")]],"source_api":u}

def worldbank_latest(w):
    u=(f"https://api.worldbank.org/v2/country/{urllib.parse.quote(w['country'])}/indicator/"
       f"{urllib.parse.quote(w['indicator_code'])}?format=json&per_page=10")
    d=get_json(u)
    rows=d[1] if isinstance(d,list) and len(d)>1 and isinstance(d[1],list) else []
    vals=[x for x in rows if x.get("value") is not None]
    if not vals:raise ValueError("World Bank sin observación")
    vals.sort(key=lambda x:str(x.get("date") or ""))
    points=[[str(x.get("date") or ""),x.get("value")] for x in vals[-8:]]
    x=vals[-1]
    return {"period":str(x.get("date") or ""),"value":x.get("value"),"points":points,"source_api":u}

def imf_datamapper(w):
    code=urllib.parse.quote(w["indicator_code"]);country=urllib.parse.quote(w["country"])
    u=f"https://www.imf.org/external/datamapper/api/v2/{code}/{country}"
    d=get_json(u)
    vals=(((d.get("values") or {}).get(w["indicator_code"]) or {}).get(w["country"]) or {})
    if not vals:raise ValueError("IMF DataMapper sin observación")
    items=sorted(((str(k),v) for k,v in vals.items() if v is not None),key=lambda x:x[0])
    if not items:raise ValueError("IMF DataMapper sin valores")
    period,value=items[-1]
    return {"period":period,"value":value,"points":[list(x) for x in items[-8:]],"source_api":u}

def eurostat_latest(w):
    base=f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{urllib.parse.quote(w['dataset'])}"
    params={"lang":"en"}
    params.update(w.get("filters") or {})
    u=base+"?"+urllib.parse.urlencode(params)
    d=get_json(u)
    ids=d.get("id") or [];sizes=d.get("size") or [];values=d.get("value") or {}
    if "time" not in ids:raise ValueError("Eurostat sin dimensión time")
    tpos=ids.index("time")
    tindex=(((d.get("dimension") or {}).get("time") or {}).get("category") or {}).get("index") or {}
    if isinstance(tindex,list):
        labels={i:str(v) for i,v in enumerate(tindex)}
    else:
        labels={int(v):str(k) for k,v in tindex.items()}
    def unravel(flat):
        coords=[0]*len(sizes)
        x=flat
        for i in range(len(sizes)-1,-1,-1):
            coords[i]=x%sizes[i];x//=sizes[i]
        return coords
    pts=[]
    iterable=values.items() if isinstance(values,dict) else enumerate(values)
    for k,v in iterable:
        if v is None:continue
        try:flat=int(k)
        except Exception:continue
        coords=unravel(flat)
        period=labels.get(coords[tpos],"")
        if period:pts.append((period,v))
    if not pts:raise ValueError("Eurostat sin observaciones")
    pts.sort(key=lambda x:x[0])
    period,value=pts[-1]
    return {"period":period,"value":value,"points":[list(x) for x in pts[-12:]],"source_api":u}

ADAPTERS={
 "bls_latest":bls_latest,
 "worldbank_latest":worldbank_latest,
 "imf_datamapper":imf_datamapper,
 "eurostat_latest":eurostat_latest,
}

def load_state():
    if not STATE.exists():return {"version":1,"watches":{}}
    return json.loads(STATE.read_text(encoding="utf-8"))

def fingerprint(period,value):
    return hashlib.sha256(f"{period}|{fmt(value)}".encode()).hexdigest()[:24]

def candidate_id(w,period,value):
    x=f"{w['id']}|{period}|{fmt(value)}"
    return "CAND-"+hashlib.sha256(x.encode()).hexdigest()[:16].upper()

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    state=load_state();sw=state.setdefault("watches",{})
    with OUT.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames
    existing={r.get("candidate_id") for r in rows}
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    added=0;primed=0;errors=0
    for w in cfg.get("watches",[]):
        try:obs=ADAPTERS[w["adapter"]](w)
        except Exception as e:
            sw[w["id"]]={"status":"ERROR","error":f"{type(e).__name__}: {e}","checked_at":now,
                         "last_fingerprint":(sw.get(w["id"]) or {}).get("last_fingerprint","")}
            errors+=1;continue
        fp=fingerprint(obs["period"],obs["value"])
        prev=(sw.get(w["id"]) or {}).get("last_fingerprint")
        changed=bool(prev and prev!=fp)
        first=not prev
        sw[w["id"]]={"status":"OK","last_fingerprint":fp,"period":obs["period"],
                     "value":fmt(obs["value"]),"checked_at":now,"source_api":obs["source_api"]}
        if first and not cfg.get("policy",{}).get("emit_on_first_seen",False):
            primed+=1;continue
        if not changed and not (first and cfg.get("policy",{}).get("emit_on_first_seen",False)):
            continue
        cid=candidate_id(w,obs["period"],obs["value"])
        if cid in existing:continue
        row={k:"" for k in fields}
        value=fmt(obs["value"])
        display=(value+(" "+w.get("unit","") if w.get("unit") else "")).strip()
        row.update({
          "candidate_id":cid,"source_id":w["id"],"source_type":"statistical_watch",
          "source_item_id":f"{w['id']}:{obs['period']}","detected_at":now,"published_at":now,
          "title":w["indicator"],"source_url":w["access_url"],"access_url":w["access_url"],
          "language":"en","area_clep":w.get("area_clep",""),"flujo_editorial":"recurso",
          "priority":str(w.get("priority",50)),"relevance_score":"100",
          "relevance_reasons":"curated_statistical_watch","oa_status":"NO_APLICA",
          "access_status":"OFFICIAL_SOURCE_VERIFIED","rights_status":"LINK_ONLY",
          "dedupe_key":hashlib.sha256((w["id"]+"|"+obs["period"]+"|"+value).encode()).hexdigest()[:24],
          "status":"METADATOS_OBTENIDOS","content_type":"dataset_grafica",
          "source_name":w["official_source"],"indicator_or_dataset":w["indicator"],
          "geography":w["geography"],"reference_period":obs["period"],"value_or_change":display,
          "official_source":w["official_source"],"data_points_json":json.dumps(obs["points"],ensure_ascii=False),
          "notes":"Actualización detectada por comparación determinista de última observación; sin IA generativa."
        })
        rows.append(row);existing.add(cid);added+=1
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with OUT.open("w",encoding="utf-8",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader();wr.writerows(rows)
    print(f"Monitoreo estadístico: nuevos={added}, inicializados={primed}, errores={errors}")

if __name__=="__main__":main()
