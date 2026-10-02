#!/usr/bin/env python3

"""
preparar_recuperacion.py
========================

Construye la base de trabajo para sustituir los enlaces históricos
de Google Drive de CLEP por fuentes abiertas, legítimas y estables.

NO:
- consulta Internet;
- modifica Facebook;
- modifica el JSON maestro;
- descarga archivos;
- decide todavía qué obra corresponde a cada Drive.

ENTRADAS
--------
~/clep_facebook_posts.json
~/clep_auditoria/clep_urls.csv
~/clep_auditoria/clep_urls_auditadas.csv

SALIDAS
-------
~/clep_recuperacion/
    drive_recuperacion.csv
    drive_posts.csv
    resumen_preparacion.txt

UNIDAD PRINCIPAL
----------------
drive_recuperacion.csv:
    una fila por URL única de Google Drive.

drive_posts.csv:
    una fila por relación Drive ↔ publicación de Facebook.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


HOME = Path.home()

POSTS_JSON = HOME / "clep_facebook_posts.json"
URLS_CSV = HOME / "clep_auditoria" / "clep_urls.csv"
AUDIT_CSV = HOME / "clep_auditoria" / "clep_urls_auditadas.csv"

OUT_DIR = HOME / "clep_recuperacion"
OUT_MAIN = OUT_DIR / "drive_recuperacion.csv"
OUT_POSTS = OUT_DIR / "drive_posts.csv"
OUT_SUMMARY = OUT_DIR / "resumen_preparacion.txt"


def abortar(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def cargar_csv(path: Path) -> list[dict]:
    if not path.exists():
        abortar(f"No existe {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_json(path: Path):
    if not path.exists():
        abortar(f"No existe {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def recortar(texto: str, limite: int = 2000) -> str:
    texto = limpiar_texto(texto)
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1] + "…"


def extraer_drive_id(url: str) -> str:
    patrones = [
        r"/file/d/([A-Za-z0-9_-]+)",
        r"/document/d/([A-Za-z0-9_-]+)",
        r"/spreadsheets/d/([A-Za-z0-9_-]+)",
        r"/presentation/d/([A-Za-z0-9_-]+)",
        r"/folders/([A-Za-z0-9_-]+)",
        r"[?&]id=([A-Za-z0-9_-]+)",
    ]
    for patron in patrones:
        m = re.search(patron, url)
        if m:
            return m.group(1)
    return ""


def tipo_drive(url: str) -> str:
    if "/folders/" in url: return "carpeta"
    if "/document/d/" in url: return "google_doc"
    if "/spreadsheets/d/" in url: return "google_sheet"
    if "/presentation/d/" in url: return "google_slides"
    if "/file/d/" in url: return "archivo"
    if "open?id=" in url or "?id=" in url or "&id=" in url: return "enlace_id"
    return "otro"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("CLEP — preparación de recuperación bibliográfica")
    print("=" * 65)
    posts = cargar_json(POSTS_JSON)
    refs = cargar_csv(URLS_CSV)
    audit = cargar_csv(AUDIT_CSV)
    if not isinstance(posts, list): abortar("El JSON maestro no contiene una lista.")
    posts_by_id = {str(p.get("id", "")): p for p in posts if isinstance(p, dict)}
    audit_by_url_id = {r["url_id"]: r for r in audit if r.get("url_id")}
    drive_refs = [r for r in refs if r.get("categoria") == "google_drive"]
    by_url_id = defaultdict(list)
    for r in drive_refs: by_url_id[r["url_id"]].append(r)
    post_rows = []
    for url_id, occurrences in by_url_id.items():
        for r in occurrences:
            post_id = r.get("post_id", "")
            post = posts_by_id.get(post_id, {})
            message = post.get("message") or ""
            post_rows.append({"url_id":url_id,"post_id":post_id,"fecha":r.get("fecha",""),"url_drive":r.get("url_normalizada",""),"permalink_facebook":r.get("permalink_facebook",""),"texto_post":limpiar_texto(message)})
    main_rows=[]
    for url_id, occurrences in by_url_id.items():
        first=occurrences[0]; url=first.get("url_normalizada","")
        associated_posts=[p for p in post_rows if p["url_id"]==url_id]; associated_posts.sort(key=lambda x:x["fecha"])
        audit_row=audit_by_url_id.get(url_id,{})
        textos=[]
        for p in associated_posts:
            t=limpiar_texto(p["texto_post"])
            if t and t not in textos: textos.append(t)
        contexto="\n\n--- PUBLICACIÓN ---\n\n".join(textos)
        fechas=[p["fecha"] for p in associated_posts if p["fecha"]]
        main_rows.append({
            "url_id":url_id,"url_drive":url,"drive_id":extraer_drive_id(url),"tipo_drive":tipo_drive(url),
            "numero_posts":len({p["post_id"] for p in associated_posts}),"primera_fecha":min(fechas) if fechas else "","ultima_fecha":max(fechas) if fechas else "","post_ids":"|".join(p["post_id"] for p in associated_posts),
            "estado_drive":audit_row.get("estado",""),"tipo_resultado_drive":audit_row.get("tipo_resultado",""),"codigo_http_drive":audit_row.get("codigo_http",""),"contexto_posts":recortar(contexto,6000),
            "titulo":"","autores":"","anio":"","tipo_recurso":"","idioma":"","revista_serie":"","volumen":"","numero":"","paginas":"","editorial_institucion":"",
            "doi":"","repec_handle":"","isbn":"","otro_identificador":"","area_clep":"","tradicion_clep":"","temas_clep":"","jel":"",
            "confianza_identificacion":"","metodo_identificacion":"","requiere_revision":"","oa_encontrado":"","url_abierta":"","fuente_abierta":"","tipo_fuente_abierta":"","licencia":"","oa_verificado":"",
            "decision":"","reemplazo_aprobado":"","fecha_aprobacion":"","observaciones":""
        })
    main_rows.sort(key=lambda x:(x["primera_fecha"],x["url_id"])); post_rows.sort(key=lambda x:(x["fecha"],x["post_id"]))
    urls_unicas={r["url_drive"] for r in main_rows}; ids_unicos={r["url_id"] for r in main_rows}
    if len(main_rows)!=len(ids_unicos): abortar("Hay url_id duplicados en la tabla principal.")
    main_fields=["url_id","url_drive","drive_id","tipo_drive","numero_posts","primera_fecha","ultima_fecha","post_ids","estado_drive","tipo_resultado_drive","codigo_http_drive","contexto_posts","titulo","autores","anio","tipo_recurso","idioma","revista_serie","volumen","numero","paginas","editorial_institucion","doi","repec_handle","isbn","otro_identificador","area_clep","tradicion_clep","temas_clep","jel","confianza_identificacion","metodo_identificacion","requiere_revision","oa_encontrado","url_abierta","fuente_abierta","tipo_fuente_abierta","licencia","oa_verificado","decision","reemplazo_aprobado","fecha_aprobacion","observaciones"]
    with OUT_MAIN.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=main_fields); writer.writeheader(); writer.writerows(main_rows)
    post_fields=["url_id","post_id","fecha","url_drive","permalink_facebook","texto_post"]
    with OUT_POSTS.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=post_fields); writer.writeheader(); writer.writerows(post_rows)
    estados=Counter(r["estado_drive"] for r in main_rows); tipos_drive=Counter(r["tipo_drive"] for r in main_rows)
    con_id=sum(bool(r["drive_id"]) for r in main_rows); sin_id=len(main_rows)-con_id; multiples_posts=sum(int(r["numero_posts"])>1 for r in main_rows)
    lines=["CLEP — BASE DE RECUPERACIÓN BIBLIOGRÁFICA","="*65,"",f"Publicaciones maestras:        {len(posts)}",f"Referencias Drive:             {len(drive_refs)}",f"URLs Drive únicas:             {len(main_rows)}",f"URLs únicas verificadas:       {len(urls_unicas)}","",f"Drive con ID extraíble:        {con_id}",f"Drive sin ID extraíble:        {sin_id}",f"Drive usados en >1 post:       {multiples_posts}","","ESTADO DE LA AUDITORÍA PREVIA","-"*65]
    for estado,n in estados.most_common(): lines.append(f"{estado:25} {n:6}")
    lines.extend(["","TIPOS DE URL DRIVE","-"*65])
    for tipo,n in tipos_drive.most_common(): lines.append(f"{tipo:25} {n:6}")
    lines.extend(["","ARCHIVOS","-"*65,str(OUT_MAIN),str(OUT_POSTS),str(OUT_SUMMARY),"","Esta etapa NO buscó sustitutos y NO modificó Facebook."])
    summary="\n".join(lines)+"\n"; OUT_SUMMARY.write_text(summary,encoding="utf-8"); print(summary)

if __name__ == "__main__":
    main()
