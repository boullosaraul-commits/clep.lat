#!/usr/bin/env python3
"""Genera una tarjeta CLEP determinista en SVG a partir de metadatos verificados.

No usa modelos generativos, red, fuentes remotas ni aleatoriedad.
"""
import html, json, re, sys, textwrap
from pathlib import Path

W,H=1200,1500
MAX_TITLE=180
MAX_META=110

def clean(x):
    return re.sub(r"\s+"," ",str(x or "")).strip()

def lines(text,width,max_lines):
    xs=textwrap.wrap(clean(text),width=width,break_long_words=False,break_on_hyphens=False)
    if len(xs)>max_lines:
        xs=xs[:max_lines]
        xs[-1]=xs[-1].rstrip(" .,:;")+"…"
    return xs

def esc(x): return html.escape(x,quote=True)

def paper_card(data):
    title=clean(data.get("title")); synopsis=clean(data.get("synopsis"))
    title_lines=lines(title,29,5)
    title_nodes="".join(f'<text x="96" y="{300+i*70}" class="ptitle">{esc(line)}</text>' for i,line in enumerate(title_lines))
    meta_nodes="".join(f'<text x="96" y="{695+i*42}" class="pmeta">{esc(line)}</text>' for i,line in enumerate(lines(data.get("meta"),58,2)))
    synopsis_nodes="".join(f'<text x="126" y="{906+i*43}" class="psummary">{esc(line)}</text>' for i,line in enumerate(lines(synopsis,54,8)))
    source_nodes="".join(f'<text x="96" y="{1334+i*34}" class="psource">{esc(line)}</text>' for i,line in enumerate(lines(data.get("source"),65,2)))
    disclosure="Síntesis asistida por IA · basada en el abstract" if data.get("synopsis_method")=="llm_source_grounded" else "Extracto del resumen en español"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500" viewBox="0 0 1200 1500">
<rect width="1200" height="1500" fill="#f3f5ef"/><rect width="1200" height="190" fill="#075e62"/>
<style>.ptitle{{font-family:Georgia,serif;font-weight:700;font-size:44px;fill:#143133}}.pmeta{{font-family:Arial,sans-serif;font-size:29px;fill:#496366}}.psummary{{font-family:Arial,sans-serif;font-size:31px;fill:#143133}}.psource{{font-family:Arial,sans-serif;font-size:24px;fill:#496366}}</style>
<text x="96" y="82" fill="#b6eece" font-family="Arial,sans-serif" font-size="28" letter-spacing="3">LECTURAS · ECONOMÍA PLURALISTA</text>
<text x="96" y="140" fill="white" font-family="Arial,sans-serif" font-size="38" font-weight="700">PAPER ABIERTO · CLEP</text>
{title_nodes}{meta_nodes}<rect x="96" y="813" width="1008" height="443" rx="18" fill="#e0ece7"/>
<text x="126" y="862" font-family="Arial,sans-serif" font-size="24" fill="#075e62" font-weight="700">DE QUÉ TRATA</text>{synopsis_nodes}
<text x="96" y="1292" font-family="Arial,sans-serif" font-size="21" fill="#496366">{esc(disclosure)}</text>{source_nodes}
<line x1="96" y1="1410" x2="1104" y2="1410" stroke="#075e62"/>
<text x="96" y="1460" font-family="Arial,sans-serif" font-size="27" fill="#075e62" font-weight="700">CLEP · clep.lat</text>
<text x="1104" y="1460" text-anchor="end" font-family="Arial,sans-serif" font-size="24" fill="#075e62">Lee el trabajo completo ↗</text></svg>'''


def render(data):
    if clean(data.get("synopsis")):
        return paper_card(data)

    label=clean(data.get("label") or "CLEP")
    title=clean(data.get("title"))
    meta=clean(data.get("meta"))
    source=clean(data.get("source"))
    if not title: raise ValueError("falta title")
    if not source: raise ValueError("falta source")
    title=title[:MAX_TITLE]; meta=meta[:MAX_META]
    tl=lines(title,31,5); ml=lines(meta,48,3) if meta else []
    y=390
    title_nodes=[]
    for x in tl:
        title_nodes.append(f'<text x="100" y="{y}" class="title">{esc(x)}</text>'); y+=92
    y+=55
    meta_nodes=[]
    for x in ml:
        meta_nodes.append(f'<text x="100" y="{y}" class="meta">{esc(x)}</text>'); y+=54
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="1200" height="1500" fill="#f5f2e9"/>
<rect x="0" y="0" width="1200" height="24" fill="#111111"/>
<style>
.label{{font-family:Arial,Helvetica,sans-serif;font-size:38px;font-weight:700;letter-spacing:3px;fill:#111}}
.title{{font-family:Georgia,'Times New Roman',serif;font-size:68px;font-weight:700;fill:#111}}
.meta{{font-family:Arial,Helvetica,sans-serif;font-size:34px;fill:#333}}
.source{{font-family:Arial,Helvetica,sans-serif;font-size:27px;fill:#555}}
.brand{{font-family:Arial,Helvetica,sans-serif;font-size:34px;font-weight:700;fill:#111}}
</style>
<text x="100" y="175" class="label">{esc(label.upper())}</text>
<line x1="100" y1="235" x2="1100" y2="235" stroke="#111" stroke-width="3"/>
{''.join(title_nodes)}
{''.join(meta_nodes)}
<line x1="100" y1="1280" x2="1100" y2="1280" stroke="#999" stroke-width="2"/>
<text x="100" y="1345" class="source">Fuente: {esc(source)}</text>
<text x="100" y="1420" class="brand">CLEP · Economía pluralista</text>
</svg>'''

def main():
    if len(sys.argv)!=3: sys.exit("uso: generar_tarjeta_clep.py entrada.json salida.svg")
    data=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out=Path(sys.argv[2]); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(render(data),encoding="utf-8")
    print(out)

if __name__=="__main__": main()
