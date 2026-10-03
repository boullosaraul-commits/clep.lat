#!/usr/bin/env python3
"""Dry-run E2E determinista del pipeline editorial, sin escrituras a Meta."""
from __future__ import annotations
import csv, os, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PY=sys.executable

CAND_FIELDS=[
 "candidate_id","source_id","source_type","source_name","title","authors","summary","content_type",
 "publication_year","published_at","detected_at","access_url","source_url","access_status","oa_status",
 "status","language","venue","notes","relevance_score","relevance_reasons","area_clep","priority","doi"
]

def run(script,*args,env):
    p=subprocess.run([PY,str(ROOT/script),*args],cwd=ROOT,env=env,text=True,capture_output=True)
    if p.returncode:
        raise AssertionError(f"{script} rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p.stdout

def main():
    media_created=[]
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);cand=td/"candidatos.csv";queue=td/"cola.csv"
        rows=[
          {
            "candidate_id":"CAND-E2E-PERU","source_id":"doab-economics","source_type":"doab_oai",
            "source_name":"Directory of Open Access Books (DOAB)",
            "title":"Desafíos y limitaciones en la implementación del etiquetado de alimentos transgénicos en el Perú",
            "authors":"A. Autora; B. Autor",
            "summary":"Economics, regulation and institutions in Peru; consumer information and public policy.",
            "content_type":"book","publication_year":"2026","published_at":"2026-10-02",
            "detected_at":"2026-10-03T10:00:00+00:00","access_url":"https://example.org/peru.pdf",
            "source_url":"https://example.org/peru","access_status":"PUBLIC_ACCESS_VERIFIED",
            "oa_status":"VERIFICADO_FUENTE","status":"OA_VERIFICADO","language":"es",
            "venue":"Editorial de prueba","notes":"","priority":"20"
          },
          {
            "candidate_id":"CAND-E2E-CHAOS","source_id":"nep-hme","source_type":"nep_report",
            "source_name":"NEP History and Methodology",
            "title":"From the Point to Chaos: The Evolution of the Concept of Equilibrium in Economic Theory",
            "authors":"C. Author",
            "summary":"A history of economic theory examining the concept of equilibrium and changes in economic methodology.",
            "content_type":"paper","publication_year":"2026","published_at":"2026-10-02",
            "detected_at":"2026-10-03T10:00:00+00:00","access_url":"https://example.org/chaos.pdf",
            "source_url":"https://example.org/chaos","access_status":"PUBLIC_ACCESS_VERIFIED",
            "oa_status":"VERIFICADO_FUENTE","status":"OA_VERIFICADO","language":"en",
            "venue":"Working Paper Series","notes":"","priority":"20"
          }
        ]
        with cand.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=CAND_FIELDS);w.writeheader();w.writerows(rows)
        with (ROOT/"data/editorial/cola.csv").open(encoding="utf-8",newline="") as f:
            qfields=list(csv.DictReader(f).fieldnames or [])
        for x in ["editorial_score","editorial_decision","editorial_policy_fingerprint","candidate_fingerprint"]:
            if x not in qfields:qfields.append(x)
        with queue.open("w",encoding="utf-8",newline="") as f:
            csv.DictWriter(f,fieldnames=qfields).writeheader()

        env=os.environ.copy()
        env.update({
          "CLEP_CANDIDATES_PATH":str(cand),"CLEP_QUEUE_PATH":str(queue),
          "CLEP_REFERENCE_DATE":"2026-10-03","CLEP_SCREENSHOT_LIMIT":"0","CLEP_META_MODE":"mock"
        })
        run("scripts/editorial/evaluar_candidatos.py",env=env)
        run("scripts/editorial/calcular_prioridad_editorial.py",env=env)
        run("scripts/editorial/preparar_publicacion.py",env=env)

        with queue.open(encoding="utf-8",newline="") as f:qrows=list(csv.DictReader(f))
        assert len(qrows)==2,qrows
        for r in qrows:
            assert r["estado_editorial"]=="FICHA_LISTA",r
            assert float(r["editorial_score"])>=7.0,r
            assert r["editorial_decision"] in {"PUBLISHABLE","OUTSTANDING"},r
            assert r["candidate_fingerprint"] and r["editorial_policy_fingerprint"],r
            if r.get("media_path"):media_created.append(ROOT/r["media_path"])

        run("scripts/editorial/planificar.py",env=env)
        run("scripts/editorial/verificar_cola.py",env=env)
        with queue.open(encoding="utf-8",newline="") as f:qrows=list(csv.DictReader(f))
        assert all(r["estado_editorial"]=="PROGRAMADO" for r in qrows),qrows

        out=td/"reserved"
        for _ in range(2):
            run("scripts/editorial/marcar_intento_meta.py","--output",str(out),env=env)
            eid=out.read_text(encoding="utf-8").strip()
            run("scripts/editorial/programar_facebook.py","--editorial-id",eid,env=env)
        run("scripts/editorial/verificar_cola.py",env=env)
        with queue.open(encoding="utf-8",newline="") as f:qrows=list(csv.DictReader(f))
        assert all(r["meta_attempt_status"]=="SCHEDULED" and r["post_nuevo_id"].startswith("mock-post-") for r in qrows),qrows
        print("E2E OK: Perú aplicado + historia del equilibrio -> publicados en Meta mock.")
    for p in media_created:
        try:p.unlink()
        except FileNotFoundError:pass

if __name__=="__main__":
    try:main()
    finally:
        for p in (ROOT/"data/editorial/media").glob("CAND-E2E-*"):
            try:p.unlink()
            except FileNotFoundError:pass
