#!/usr/bin/env python3
import csv,os,re,sys
from collections import Counter,defaultdict
from datetime import date,datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts/editorial"))
from editorial_rules import check_meta_ready, check_publishable

COLA=Path(os.getenv("CLEP_QUEUE_PATH",str(ROOT/"data/editorial/cola.csv"))).resolve()

FLUJOS={"archivo_historico","novedad","recurso","actividad_clep","publicacion_clep","otro"}
ESTADOS={"IDENTIFICANDO","OBRA_VERIFICADA","EDICION_VERIFICADA","OA_VERIFICADO","FICHA_LISTA","APROBADO","REVALIDAR","PROGRAMADO","PUBLICADO","ORIGINAL_RETIRADO","DESCARTADO"}
NON_TEXT={"actividad_clep","convocatoria","convocatoria_evento","recurso","video","grafica","dataset_grafica","material_didactico","efemeride","anuncio_institucional"}

def truthy(x):return (x or "").strip().lower() in {"1","true","yes"}
def valid_time(x):
    try:datetime.strptime(x,"%H:%M");return True
    except Exception:return False

def main():
    with COLA.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f);rows=list(rd)
    errors=[]
    ids=Counter(r.get("editorial_id") for r in rows if r.get("editorial_id"))
    for eid,n in ids.items():
        if n>1:errors.append(f"editorial_id duplicado: {eid}")

    day_counts=defaultdict(lambda:{"hist":0,"new":0,"nontext":0,"new_high":0,"doab":0,"types":Counter()})
    day_times=defaultdict(list)

    for n,r in enumerate(rows,start=2):
        flow=r.get("flujo_editorial","");state=r.get("estado_editorial","")
        day=(r.get("fecha_programada") or "").strip();tm=(r.get("orden_dia") or "").strip()

        if flow not in FLUJOS:errors.append(f"línea {n}: flujo inválido: {flow}")
        if state not in ESTADOS:errors.append(f"línea {n}: estado inválido: {state}")

        if day:
            try:date.fromisoformat(day)
            except ValueError:errors.append(f"línea {n}: fecha_programada inválida: {day}")
        if tm and not valid_time(tm):errors.append(f"línea {n}: orden_dia debe ser HH:MM: {tm}")

        if state=="PROGRAMADO":
            attempt=(r.get("meta_attempt_status") or "").strip()
            if attempt not in {"","IN_FLIGHT","SCHEDULED","REVIEW"}:
                errors.append(f"línea {n}: estado de intento Meta inválido para PROGRAMADO: {attempt}")
            if r.get("post_nuevo_id") and attempt!="SCHEDULED":
                errors.append(f"línea {n}: PROGRAMADO con post_nuevo_id pero sin SCHEDULED")
            if attempt=="SCHEDULED" and not r.get("post_nuevo_id"):
                errors.append(f"línea {n}: SCHEDULED sin post_nuevo_id")
            if attempt=="IN_FLIGHT":
                meta_check=check_meta_ready(r)
                if not meta_check:
                    errors.append(f"línea {n}: reserva Meta inválida [{meta_check.code}]: {meta_check.detail}")
            if not day or not tm:errors.append(f"línea {n}: PROGRAMADO sin fecha/hora")
            text=(r.get("ficha_es") or "").strip()
            if not text:errors.append(f"línea {n}: PROGRAMADO sin texto editorial")
            if len(text)>900:errors.append(f"línea {n}: texto editorial excede 900 caracteres")
            if len([p for p in re.split(r"\n\s*\n",text) if p.strip()])>5:
                errors.append(f"línea {n}: texto editorial excede 5 párrafos")
            if r.get("text_method")!="deterministic_template":
                errors.append(f"línea {n}: PROGRAMADO sin método determinista")
            if not (r.get("text_template") or "").strip():
                errors.append(f"línea {n}: PROGRAMADO sin plantilla registrada")
            if r.get("text_status")!="VERIFICADO":
                errors.append(f"línea {n}: PROGRAMADO con texto no verificado")
            if not (r.get("media_type") or "").strip():
                errors.append(f"línea {n}: PROGRAMADO sin media_type")
            if not ((r.get("media_path") or "").strip() or (r.get("media_url") or "").strip()):
                errors.append(f"línea {n}: PROGRAMADO sin imagen")
            if not (r.get("media_source") or "").strip():
                errors.append(f"línea {n}: PROGRAMADO sin media_source")
            if r.get("media_rights_status") not in {"VERIFICADO","CAPTURA_LANDING_OFICIAL","PROPIO_DETERMINISTA"}:
                errors.append(f"línea {n}: derechos de imagen no verificados")
            if day and tm:day_times[day].append(tm)

        if state in {"PROGRAMADO","PUBLICADO","ORIGINAL_RETIRADO"} and day:
            if flow=="archivo_historico":day_counts[day]["hist"]+=1
            elif r.get("tipo_recurso") in NON_TEXT:day_counts[day]["nontext"]+=1
            else:
                day_counts[day]["new"]+=1
                notes=(r.get("notas") or "")
                try:es=float(r.get("editorial_score") or 0)
                except ValueError:es=0.0
                if es>=9:day_counts[day]["new_high"]+=1
                publishable_check=check_publishable(r)
                if not publishable_check:
                    errors.append(f"línea {n}: novedad académica no publicable [{publishable_check.code}]: {publishable_check.detail}")
                src=" ".join([r.get("oa_fuente") or "",notes,r.get("url_original") or ""]).lower()
                if "doab" in src or "directory of open access books" in src:day_counts[day]["doab"]+=1
                day_counts[day]["types"][r.get("tipo_recurso") or "otro"]+=1
                sm=re.search(r"venue=([^;|]+)",notes,re.I)
                sk=(sm.group(1).strip().lower() if sm and sm.group(1).strip() else (r.get("oa_fuente") or "").strip().lower())
                if sk:day_counts[day].setdefault("sources",Counter())[sk]+=1

        if flow=="archivo_historico":
            if truthy(r.get("original_retirado")) and not r.get("post_nuevo_id"):
                errors.append(f"línea {n}: original retirado sin post nuevo")
            if state=="FICHA_LISTA":
                if r.get("obra_estado")!="OBRA_VERIFICADA":
                    errors.append(f"línea {n}: histórico FICHA_LISTA sin obra verificada")
                if r.get("edicion_estado")!="EDICION_VERIFICADA":
                    errors.append(f"línea {n}: histórico FICHA_LISTA sin edición verificada")
                if r.get("oa_estado")!="OA_VERIFICADO":
                    errors.append(f"línea {n}: histórico FICHA_LISTA sin OA verificado")

    for day,c in sorted(day_counts.items()):
        total=c["hist"]+c["new"]+c["nontext"]
        if total>17:errors.append(f"{day}: total={total} > 17 slots")
        if c["hist"]>6:errors.append(f"{day}: históricos={c['hist']} > 6")
        if c["new"]>8:errors.append(f"{day}: novedades={c['new']} > 8")
        if c["new"]>6 and c["new_high"]<5:
            errors.append(f"{day}: novedades={c['new']} > 6 sin al menos 5 candidatos con índice editorial >=9")
        if c["doab"]>2:errors.append(f"{day}: libros DOAB={c['doab']} > 2")
        for typ,n in c["types"].items():
            if n>3:errors.append(f"{day}: novedades tipo {typ}={n} > 3")
        for src,n in c.get("sources",{}).items():
            if n>2:errors.append(f"{day}: novedades misma institución/serie {src}={n} > 2")
        if c["nontext"]>4:errors.append(f"{day}: no-texto={c['nontext']} > 4")
    for day,times in day_times.items():
        dup=[x for x,n in Counter(times).items() if n>1]
        if dup:errors.append(f"{day}: horas duplicadas: {', '.join(sorted(dup))}")
        mins=[]
        for x in times:
            h,m=map(int,x.split(":"));mins.append(h*60+m)
        mins.sort()
        for a,b in zip(mins,mins[1:]):
            if b-a<60:errors.append(f"{day}: separación menor a 60 minutos")

    print("CLEP — VALIDACIÓN EDITORIAL")
    print("="*72)
    print(f"Registros: {len(rows)}")
    if errors:
        print("\nERRORES")
        for e in errors:print(" -",e)
        return 1
    print("\nOK — cola válida: texto+imagen obligatorios; 17 slots totales; novedades 6 (hasta 8 con >=5 editorial_score 9), DOAB <=2, mismo tipo <=3, histórico <=6, no-texto <=4.")
    return 0

if __name__=="__main__":sys.exit(main())
