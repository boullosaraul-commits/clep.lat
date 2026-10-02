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

def render(data):
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
