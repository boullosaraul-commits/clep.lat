#!/usr/bin/env python3
"""Gráfica SVG determinista CLEP para series cortas.

Entrada: JSON con title, geography, source y points=[[period,value],...].
Sin red, aleatoriedad, modelos ni inferencias.
"""
import html,json,math,re,sys
from pathlib import Path

W,H=1200,1500
LEFT,RIGHT,TOP,BOTTOM=120,1080,360,1160

def clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()
def esc(x):return html.escape(clean(x),quote=True)

def num(x):
    try:
        v=float(str(x).replace(",",""))
        return v if math.isfinite(v) else None
    except Exception:return None

def render(data):
    title=clean(data.get("title"));geo=clean(data.get("geography"));source=clean(data.get("source"))
    raw=data.get("points") or []
    pts=[(clean(p[0]),num(p[1])) for p in raw if isinstance(p,(list,tuple)) and len(p)>=2]
    pts=[p for p in pts if p[0] and p[1] is not None]
    if not title or not source or len(pts)<2:raise ValueError("gráfica requiere title, source y >=2 observaciones")
    pts=pts[-12:]
    vals=[v for _,v in pts];lo=min(vals);hi=max(vals)
    if hi==lo:lo-=1;hi+=1
    pad=(hi-lo)*.12;lo-=pad;hi+=pad
    def x(i):return LEFT+(RIGHT-LEFT)*(i/max(1,len(pts)-1))
    def y(v):return BOTTOM-(BOTTOM-TOP)*((v-lo)/(hi-lo))
    path=" ".join(("M" if i==0 else "L")+f" {x(i):.1f} {y(v):.1f}" for i,(_,v) in enumerate(pts))
    nodes=[]
    for i,(period,v) in enumerate(pts):
        nodes.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="7" fill="#111"/>')
    labels=[]
    show={0,len(pts)-1}
    if len(pts)>4:show.add(len(pts)//2)
    for i in sorted(show):
        labels.append(f'<text x="{x(i):.1f}" y="1225" text-anchor="middle" class="axis">{esc(pts[i][0])}</text>')
    ticks=[]
    for j in range(5):
        v=lo+(hi-lo)*j/4;yy=y(v)
        ticks.append(f'<line x1="{LEFT}" y1="{yy:.1f}" x2="{RIGHT}" y2="{yy:.1f}" stroke="#ccc" stroke-width="1"/>')
        ticks.append(f'<text x="{LEFT-22}" y="{yy+10:.1f}" text-anchor="end" class="axis">{v:.2f}</text>')
    latest=pts[-1]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="1200" height="1500" fill="#f5f2e9"/>
<rect width="1200" height="24" fill="#111"/>
<style>
.k{{font-family:Arial,Helvetica,sans-serif;font-size:34px;font-weight:700;letter-spacing:2px;fill:#111}}
.t{{font-family:Georgia,'Times New Roman',serif;font-size:60px;font-weight:700;fill:#111}}
.s{{font-family:Arial,Helvetica,sans-serif;font-size:31px;fill:#444}}
.axis{{font-family:Arial,Helvetica,sans-serif;font-size:24px;fill:#555}}
.latest{{font-family:Arial,Helvetica,sans-serif;font-size:38px;font-weight:700;fill:#111}}
.brand{{font-family:Arial,Helvetica,sans-serif;font-size:32px;font-weight:700;fill:#111}}
</style>
<text x="100" y="145" class="k">DATOS · CLEP</text>
<text x="100" y="240" class="t">{esc(title[:70])}</text>
<text x="100" y="305" class="s">{esc(geo)}</text>
{''.join(ticks)}
<path d="{path}" fill="none" stroke="#111" stroke-width="8" stroke-linejoin="round" stroke-linecap="round"/>
{''.join(nodes)}
{''.join(labels)}
<text x="100" y="1310" class="latest">Último dato: {esc(latest[0])} · {esc(f"{latest[1]:g}")}</text>
<text x="100" y="1380" class="s">Fuente: {esc(source)}</text>
<text x="100" y="1450" class="brand">CLEP · Economía pluralista</text>
</svg>'''

def main():
    if len(sys.argv)!=3:sys.exit("uso: generar_grafica_clep.py entrada.json salida.svg")
    data=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out=Path(sys.argv[2]);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(render(data),encoding="utf-8");print(out)
if __name__=="__main__":main()
