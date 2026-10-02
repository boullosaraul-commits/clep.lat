#!/usr/bin/env python3
"""Preflight de credenciales Meta para CLEP.

Comprueba que el token vigente puede resolver la Page configurada. No modifica
Meta, no imprime el token y falla antes de cualquier operación editorial que
dependa de Facebook.
"""
import json, os, urllib.error, urllib.parse, urllib.request

API=os.getenv("META_GRAPH_VERSION","v26.0")

def main():
    token=os.getenv("CLEP_FB_TOKEN");page=os.getenv("CLEP_FB_PAGE_ID")
    if not token or not page:raise SystemExit("Faltan CLEP_FB_TOKEN o CLEP_FB_PAGE_ID")
    q=urllib.parse.urlencode({"fields":"id,name","access_token":token})
    url=f"https://graph.facebook.com/{API}/{page}?{q}"
    try:
        with urllib.request.urlopen(url,timeout=30) as r:
            obj=json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace").replace(token,"***")
        raise SystemExit(f"Meta preflight falló: HTTP {e.code}: {body[:800]}")
    if str(obj.get("id") or "")!=str(page):
        raise SystemExit("Meta preflight falló: la Page devuelta no coincide con CLEP_FB_PAGE_ID")
    print(f"Meta preflight OK: Page {obj.get('name','')} ({obj.get('id','')}).")

if __name__=="__main__":main()
