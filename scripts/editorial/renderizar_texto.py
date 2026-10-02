#!/usr/bin/env python3
"""Renderizador determinista de textos editoriales CLEP. Sin LLM."""
import json, re, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TPL=ROOT/"data/editorial/plantillas.json"
CFG=ROOT/"data/editorial/programacion.json"

def clean(v):
    return re.sub(r"\s+"," ",str(v or "")).strip()

def render(kind, data):
    cfg=json.loads(TPL.read_text(encoding="utf-8"))
    policy=json.loads(CFG.read_text(encoding="utf-8"))["text_policy"]
    spec=cfg["textos_cortos"].get(kind)
    if not spec: raise ValueError(f"tipo sin plantilla: {kind}")
    d={k:clean(v) for k,v in data.items()}
    missing=[k for k in spec["required"] if not d.get(k)]
    if missing: raise ValueError("faltan metadatos obligatorios: "+", ".join(missing))
    d.setdefault("date_label","Fecha")
    try: body=spec["template"].format_map(d)
    except KeyError as e: raise ValueError(f"falta campo de plantilla: {e.args[0]}")
    text=(spec["label"]+"\n\n"+body).strip()
    text=re.sub(r"[ \t]+\n","\n",text)
    text=re.sub(r"\n{3,}","\n\n",text)
    if len(text)>int(policy["max_chars"]):
        raise ValueError(f"texto excede máximo: {len(text)} > {policy['max_chars']}")
    paras=[p for p in text.split("\n\n") if p.strip()]
    if len(paras)>int(policy["max_paragraphs"]):
        raise ValueError(f"demasiados párrafos: {len(paras)}")
    return text

def main():
    if len(sys.argv)!=3:
        sys.exit("uso: renderizar_texto.py TIPO archivo.json")
    data=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(render(sys.argv[1],data))

if __name__=="__main__": main()
