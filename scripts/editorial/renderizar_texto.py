#!/usr/bin/env python3
"""Autoridad única de renderizado textual editorial CLEP.

Sin IA generativa; determinista; fail-closed ante metadata o provenance inválida.
"""
from __future__ import annotations
import json, re, sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from traduccion_textual import TranslationError, TranslationRecord, validate_translation

ROOT=Path(__file__).resolve().parents[2]
TPL=ROOT/"data/editorial/plantillas.json"
CFG=ROOT/"data/editorial/programacion.json"
TEXT_METHOD="deterministic_template"; TEXT_STATUS="VERIFIED"; FACTUAL_FALLBACK_VERSION=1

class TextRenderError(ValueError):
    def __init__(self,code:str,detail:str,field:str=""):
        self.code=code; self.detail=detail; self.field=field
        super().__init__(f"{code}: {detail}")

@dataclass(frozen=True)
class TextRenderResult:
    content_type:str; source_summary:str; source_summary_es:str; editorial_description:str
    post_text:str; text_method:str; text_template:str; text_template_version:int
    text_status:str; translation:dict[str,Any]
    def to_dict(self): return asdict(self)

def clean(v): return re.sub(r"\s+"," ",str(v or "")).strip()

def _configs():
    t=json.loads(TPL.read_text(encoding="utf-8")); p=json.loads(CFG.read_text(encoding="utf-8"))
    return t,p["text_policy"]

def supported_content_types():
    t,_=_configs(); return tuple(sorted(t.get("textos_cortos",{})))

def _source_summary(data):
    for k in ("source_summary","summary","abstract","description"):
        v=clean(data.get(k))
        if v:return v
    return ""

def _source_summary_es(data):
    for k in ("source_summary_es","summary_es","abstract_es","description_es"):
        v=clean(data.get(k))
        if v:return v
    return ""

def _validated_translation(data,translated):
    if not translated:return None
    try:return validate_translation(translated,data)
    except TranslationError as exc: raise TextRenderError(exc.code,exc.detail,exc.field) from None

def factual_fallback(kind,data):
    d={k:clean(v) for k,v in data.items()}; title=d.get("title") or d.get("indicator_or_dataset")
    author=d.get("authors") or d.get("authors_or_editors") or d.get("authors_or_institution") or d.get("speaker_or_organization") or d.get("organizer") or d.get("source") or d.get("official_source")
    year=d.get("year") or d.get("reference_period") or d.get("date_or_deadline")
    source=d.get("source_or_series") or d.get("container_title") or d.get("institution") or d.get("journal")
    access=d.get("access_url")
    if not title or not access:
        missing=[n for n,v in (("title",title),("access_url",access)) if not v]
        raise TextRenderError("INSUFFICIENT_METADATA","fallback factual requiere "+", ".join(missing),missing[0])
    bits=[f"{kind}: {title}"]
    for v in (author,year,source):
        if v:bits.append(v)
    bits.append(access); return " · ".join(bits)

def _editorial_description(kind,data,source,translated):
    lang=clean(data.get("source_language")).lower()
    if source and lang in {"","es","spa","spanish","español"}:return source
    if translated:return translated
    return factual_fallback(kind,data)

def _paper_contract(data,source,translated):
    lang=clean(data.get("source_language") or data.get("language")).lower()
    if lang not in {"en","eng","english","inglés","ingles"}: return ""
    missing=[]
    if not clean(data.get("authors")): missing.append("authors")
    if not source: missing.append("source_summary")
    if not translated: missing.append("source_summary_es")
    if not clean(data.get("title_es")) and " — ES: " not in clean(data.get("title")): missing.append("title_es")
    if missing: raise TextRenderError("INSUFFICIENT_METADATA","paper en inglés requiere "+", ".join(missing),missing[0])
    return f"Abstract (original):\n{source}\n\nResumen en español · traducción automática:\n{translated}\n\n"

def _render_template(kind,data,paper_abstract_block=""):
    templates,policy=_configs(); spec=templates.get("textos_cortos",{}).get(kind)
    if not spec: raise TextRenderError("TEMPLATE_MISSING",f"tipo sin plantilla: {kind}","content_type")
    d={k:clean(v) for k,v in data.items()}; d["paper_abstract_block"]=paper_abstract_block
    missing=[k for k in spec.get("required",[]) if not d.get(k)]
    if missing: raise TextRenderError("INSUFFICIENT_METADATA","faltan metadatos obligatorios: "+", ".join(missing),missing[0])
    d.setdefault("date_label","Fecha")
    try: body=spec["template"].format_map(d)
    except KeyError as exc: raise TextRenderError("TEMPLATE_FIELD_MISSING",f"falta campo de plantilla: {exc.args[0]}",str(exc.args[0])) from None
    body=body.replace("\\\\n","\n"); text=(spec["label"]+"\n\n"+body).strip()
    text=re.sub(r"[ \t]+\n","\n",text); text=re.sub(r"\n{3,}","\n\n",text)
    if "\\\\n" in text: raise TextRenderError("TEMPLATE_ESCAPE_ERROR","plantilla contiene saltos escapados literalmente")
    if len(text)>int(policy["max_chars"]): raise TextRenderError("TEXT_OVERFLOW",f"texto excede máximo: {len(text)} > {policy['max_chars']}")
    paragraphs=[p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs)>int(policy["max_paragraphs"]): raise TextRenderError("TEXT_TOO_MANY_PARAGRAPHS",f"demasiados párrafos: {len(paragraphs)} > {policy['max_paragraphs']}")
    return text,clean(spec.get("id") or f"textos_cortos.{kind}"),int(spec.get("version") or templates.get("version") or 1)

def render_result(kind,data):
    kind=clean(kind).lower()
    if not kind: raise TextRenderError("CONTENT_TYPE_MISSING","content_type vacío","content_type")
    source=_source_summary(data); translated=_source_summary_es(data)
    paper_block=_paper_contract(data,source,translated) if kind=="paper" else ""
    translation=_validated_translation(data,translated)
    description=_editorial_description(kind,data,source,translated)
    post_text,template_id,template_version=_render_template(kind,data,paper_block)
    translation_data={"present":False}
    if translation: translation_data={"present":True,**translation.to_dict()}
    return TextRenderResult(kind,source,translated,description,post_text,TEXT_METHOD,template_id,template_version,TEXT_STATUS,translation_data)

def render(kind,data): return render_result(kind,data).post_text

def main():
    if len(sys.argv)!=3: sys.exit("uso: renderizar_texto.py TIPO archivo.json")
    data=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(render_result(sys.argv[1],data).to_dict(),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
