#!/usr/bin/env python3
import json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"recovery"))
sys.path.insert(0,str(ROOT/"scripts/editorial"))

from matcher_v31 import evaluate, family
from renderizar_texto import render as render_text
from generar_tarjeta_clep import render as render_card
from generar_grafica_clep import render as render_chart
from evaluar_candidatos import doab_eval

class MatcherV31Tests(unittest.TestCase):
    def test_main_title_rescue(self):
        h={"title":"Heterodox Macroeconomics: Models of Demand, Distribution and Growth",
           "authors":"Robert A. Blecker; Mark Setterfield","type":"book"}
        c={"title":"Heterodox Macroeconomics",
           "authors":"Robert A. Blecker; Mark Setterfield","type":"book"}
        m=evaluate(h,c)
        self.assertEqual(m["status"],"IDENTIFICADO")
        self.assertTrue(m["rescued_by_main"])
        self.assertGreaterEqual(m["title_effective"],.90)

    def test_type_barrier(self):
        h={"title":"A Very Specific Economic Theory","authors":"Jane Doe","type":"book"}
        c={"title":"A Very Specific Economic Theory","authors":"Jane Doe","type":"article"}
        self.assertEqual(evaluate(h,c)["status"],"SIN_IDENTIFICAR")

    def test_people_metrics_gate(self):
        h={"title":"Growth and Distribution","authors":"Duncan K. Foley; Thomas R. Michl; Daniele Tavani","type":"unknown"}
        c={"title":"Growth and Distribution","authors":"Duncan K. Foley; Thomas R. Michl","type":"book"}
        m=evaluate(h,c)
        self.assertEqual(m["status"],"IDENTIFICADO")
        self.assertAlmostEqual(m["coverage"],2/3,places=3)
        self.assertEqual(m["precision"],1.0)

    def test_family_monograph_is_book(self):
        self.assertEqual(family("monograph"),"book")

class RendererTests(unittest.TestCase):
    def test_short_text_is_deterministic(self):
        d={"title":"A Monetary Paper","authors":"A. Author","source_or_series":"Working Paper Series",
           "year":"2026","access_url":"https://example.org/paper"}
        a=render_text("paper",d);b=render_text("paper",d)
        self.assertEqual(a,b)
        self.assertLessEqual(len(a),900)
        self.assertIn("PAPER ABIERTO · CLEP",a)

    def test_card_is_deterministic(self):
        d={"label":"PAPER ABIERTO · CLEP","title":"A Monetary Paper","meta":"A. Author · 2026","source":"Example"}
        self.assertEqual(render_card(d),render_card(d))
        self.assertIn('width="1200"',render_card(d))

    def test_chart_is_deterministic(self):
        d={"title":"Unemployment rate","geography":"Example","source":"Official source",
           "points":[["2026-01",4.1],["2026-02",4.0],["2026-03",3.9]]}
        a=render_chart(d);b=render_chart(d)
        self.assertEqual(a,b)
        self.assertIn("DATOS · CLEP",a)

class DOABRelevanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=json.loads((ROOT/"data/editorial/pertinencia_doab.json").read_text(encoding="utf-8"))

    def test_multi_area_economics_promotes(self):
        r={"title":"Monetary Policy, Income Distribution and Development in Latin America",
           "summary":"A study of inflation, wages, structural change and central banking.",
           "notes":"Temas: Economics; Political economy","publication_year":"2026"}
        score,decision,area,reasons=doab_eval(r,self.cfg)
        self.assertEqual(decision,"PROMOCION_AUTOMATICA")
        self.assertGreaterEqual(score,self.cfg["thresholds"]["promocion_automatica"])
        self.assertIn("areas=",reasons)

    def test_medical_keyword_collision_does_not_promote(self):
        r={"title":"Development of Labor-Saving Medical Devices",
           "summary":"Clinical medicine, nursing and medical technology.",
           "notes":"Temas: Medicine","publication_year":"2026"}
        score,decision,area,reasons=doab_eval(r,self.cfg)
        self.assertEqual(decision,"ARCHIVADO")
        self.assertIn("disciplina=no_confirmada",reasons)

    def test_single_relevant_area_goes_to_review(self):
        r={"title":"Banking and Credit",
           "summary":"An introduction to banking and financial institutions.",
           "notes":"","publication_year":"2026"}
        score,decision,area,reasons=doab_eval(r,self.cfg)
        self.assertIn(decision,{"REVISION_EDITORIAL","PROMOCION_AUTOMATICA"})
        self.assertNotEqual(decision,"ARCHIVADO")

class ConfigTests(unittest.TestCase):
    def test_no_generative_ai_and_no_noimage_fallback(self):
        cfg=json.loads((ROOT/"data/editorial/programacion.json").read_text(encoding="utf-8"))
        self.assertFalse(cfg["generative_ai"]["enabled"])
        self.assertNotIn("no_image",cfg["paper_visual"]["preference"])
        self.assertFalse(cfg["archivo_historico"]["stop_when_target_date_reached"])

if __name__=="__main__":
    unittest.main()
