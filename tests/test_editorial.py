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
from ingerir_novedades_academicas import classify_crossref, explicit_revision_or_translation
from calcular_prioridad_editorial import evaluate as editorial_evaluate
from planificar import editorial_index_10
from verificar_oa import preverification_score

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

    def test_history_of_equilibrium_gets_pluralist_rescue(self):
        r={"title":"From the Point to Chaos: The Evolution of the Concept of Equilibrium in Economic Theory",
           "summary":"A history of economic theory and economic methodology.","notes":"","publication_year":"2026"}
        score,decision,area,reasons=doab_eval(r,self.cfg)
        self.assertIn(area,{"historia-pensamiento-metodologia",""})
        self.assertIn("pluralismo_rescate=si",reasons)
        self.assertEqual(decision,"REVISION_EDITORIAL")

    def test_single_relevant_area_goes_to_review(self):
        r={"title":"Banking and Credit",
           "summary":"An introduction to banking and financial institutions.",
           "notes":"","publication_year":"2026"}
        score,decision,area,reasons=doab_eval(r,self.cfg)
        self.assertIn(decision,{"REVISION_EDITORIAL","PROMOCION_AUTOMATICA"})
        self.assertNotEqual(decision,"ARCHIVADO")


class AcademicNoveltyTests(unittest.TestCase):
    def test_crossref_types(self):
        self.assertEqual(classify_crossref({"type":"book-chapter","title":["Demand and Distribution"]}),"chapter")
        self.assertEqual(classify_crossref({"type":"report","title":["A Policy Brief on Employment"]}),"policy_brief")
        self.assertEqual(classify_crossref({"type":"dissertation","title":["Essays in Monetary Economics"]}),"thesis")
        self.assertEqual(classify_crossref({"type":"journal-issue","title":["Special Issue: Political Economy"]}),"special_issue")

    def test_books_require_explicit_edition_event(self):
        self.assertEqual(classify_crossref({"type":"book","title":["Ordinary First Book"]}),"")
        self.assertEqual(classify_crossref({"type":"book","title":["Political Economy, 2nd Edition"]}),"edition_translation")
        ok,kind=explicit_revision_or_translation({"type":"book","title":["A Translation of Keynes"]})
        self.assertTrue(ok);self.assertEqual(kind,"translation")

    def test_new_templates_render(self):
        chapter=render_text("chapter",{"title":"A Chapter","authors":"A. Author","container_title":"A Book","year":"2026","access_url":"https://example.org/ch"})
        report=render_text("report",{"title":"A Report","authors_or_institution":"CEPAL","year":"2026","access_url":"https://example.org/r"})
        thesis=render_text("thesis",{"title":"A Thesis","authors":"A. Author","institution":"UNAM","year":"2026","access_url":"https://example.org/t"})
        self.assertIn("CAPÍTULO ABIERTO · CLEP",chapter)
        self.assertIn("INFORME ABIERTO · CLEP",report)
        self.assertIn("TESIS ABIERTA · CLEP",thesis)


class EditorialPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=json.loads((ROOT/"data/editorial/prioridad_editorial.json").read_text(encoding="utf-8"))

    def test_relevance_and_editorial_priority_are_separate(self):
        r={"title":"Monetary Policy and Distribution in Latin America","authors":"A. Author",
           "publication_year":"2026","published_at":"2026-10-01","access_url":"https://example.org/a.pdf",
           "oa_status":"VERIFICADO","access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"paper",
           "summary":"Post-Keynesian effective demand with new empirical evidence and data for research.",
           "relevance_score":"77",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero,trabajo-distribucion-bienestar;anclas=monetary,economics",
           "language":"es","venue":"Example Series","source_name":"Example"}
        score,decision,reasons=editorial_evaluate(r,self.cfg)
        self.assertGreaterEqual(score,7)
        self.assertIn(decision,{"PUBLISHABLE","OUTSTANDING"})
        self.assertNotEqual(score,7.7)

    def test_ineligible_cannot_buy_entry_with_relevance(self):
        r={"title":"Relevant but closed","authors":"A. Author","publication_year":"2026",
           "published_at":"2026-10-01","access_url":"https://example.org/closed","oa_status":"POR_VERIFICAR",
           "access_status":"SOURCE_UNCHECKED","content_type":"paper",
           "relevance_score":"100","relevance_reasons":"disciplina=economia;areas=macroeconomia-dinero;anclas=economics"}
        score,decision,_=editorial_evaluate(r,self.cfg)
        self.assertEqual(score,0.0);self.assertEqual(decision,"INELIGIBLE")

    def test_source_oa_without_live_link_is_ineligible(self):
        r={"title":"OA source but unchecked URL","authors":"A. Author","publication_year":"2026",
           "published_at":"2026-10-01","access_url":"https://example.org/item",
           "oa_status":"VERIFICADO_FUENTE","access_status":"SOURCE_OA_UNCHECKED","content_type":"book",
           "source_type":"doab_oai","relevance_score":"70",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero;anclas=economics"}
        score,decision,_=editorial_evaluate(r,self.cfg)
        self.assertEqual((score,decision),(0.0,"INELIGIBLE"))

    def test_exact_novelty_date_required(self):
        r={"title":"Undated current-year item","authors":"A. Author","publication_year":"2026",
           "published_at":"2026","access_url":"https://example.org/item.pdf",
           "oa_status":"VERIFICADO_FUENTE","access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"paper",
           "relevance_score":"70",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero;anclas=economics"}
        score,decision,_=editorial_evaluate(r,self.cfg)
        self.assertEqual((score,decision),(0.0,"INELIGIBLE"))

    def test_bounded_recent_stream_can_supply_freshness(self):
        r={"title":"Recent OAI monetary report","authors":"Institution","publication_year":"2026",
           "published_at":"2026","detected_at":"2026-10-02T18:00:00+00:00",
           "access_url":"https://example.org/item.pdf","oa_status":"VERIFICADO_FUENTE",
           "access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"report","source_type":"academic_oai",
           "relevance_score":"70",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero,finanzas-sector-publico;anclas=economics,monetary"}
        score,decision,reasons=editorial_evaluate(r,self.cfg)
        self.assertGreater(score,0)
        self.assertIn("freshness=bounded_stream_detection",reasons)

    def test_outstanding_score_is_reachable(self):
        r={"title":"New empirical research on monetary policy, income distribution and structural change in Latin America",
           "authors":"A. Author","publication_year":"2026","published_at":"2026-10-01",
           "access_url":"https://example.org/item.pdf","oa_status":"VERIFICADO_FUENTE",
           "access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"edition_translation",
           "summary":"Post-Keynesian effective demand and endogenous money. New evidence and data. A revised edition for teaching economic methodology.",
           "language":"es","venue":"Latin American Political Economy",
           "relevance_score":"90",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero,desarrollo-estructura,trabajo-distribucion-bienestar;anclas=economics,monetary"}
        score,decision,_=editorial_evaluate(r,self.cfg)
        self.assertGreaterEqual(score,9.0)
        self.assertEqual(decision,"OUTSTANDING")

    def test_pluralist_non_latin_work_gets_pluralism_points(self):
        r={"title":"Post-Keynesian Effective Demand and Endogenous Money","authors":"A. Author",
           "publication_year":"2026","published_at":"2026-10-01","access_url":"https://example.org/p.pdf",
           "oa_status":"VERIFICADO","access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"paper",
           "summary":"A post-Keynesian model of effective demand and endogenous money.",
           "language":"en","venue":"Cambridge Working Papers","source_name":"Example",
           "relevance_score":"80",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero,finanzas-sector-publico;anclas=monetary,economics"}
        score,decision,reasons=editorial_evaluate(r,self.cfg)
        self.assertIn("H=2.0",reasons)
        self.assertIn("R=0.0",reasons)
        self.assertGreaterEqual(score,7.0)

    def test_latin_america_does_not_imply_pluralism(self):
        r={"title":"Food Labelling Regulation in Peru","authors":"A. Author",
           "publication_year":"2026","published_at":"2026-10-01","access_url":"https://example.org/p.pdf",
           "oa_status":"VERIFICADO","access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"book",
           "summary":"Regulation, institutions and consumer information in Peru.",
           "language":"es","venue":"Example","source_name":"Example",
           "relevance_score":"70",
           "relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=economia-politica-instituciones;anclas=economics"}
        score,decision,reasons=editorial_evaluate(r,self.cfg)
        self.assertIn("R=1.0",reasons)
        self.assertIn("H=0.0",reasons)

    def test_thematic_review_cannot_become_publishable(self):
        r={"title":"Monetary banking topic","authors":"A. Author","publication_year":"2026",
           "published_at":"2026-10-01","access_url":"https://example.org/item.pdf",
           "oa_status":"VERIFICADO_FUENTE","access_status":"PUBLIC_ACCESS_VERIFIED","content_type":"book",
           "relevance_score":"20",
           "relevance_reasons":"decision=REVISION_EDITORIAL;disciplina=economia;areas=macroeconomia-dinero;anclas=monetary"}
        score,decision,_=editorial_evaluate(r,self.cfg)
        self.assertEqual(score,0.0)
        self.assertEqual(decision,"THEMATIC_REVIEW")


    def test_oa_preverification_prioritizes_pluralist_and_regional_value(self):
        from calcular_prioridad_editorial import reference_now
        cfg=self.cfg
        base={"authors":"A. Author","publication_year":"2026","published_at":"2026-10-02",
              "access_url":"https://example.org/x","content_type":"paper","source_name":"Example",
              "relevance_score":"30","relevance_reasons":"decision=PROMOCION_AUTOMATICA;disciplina=economia;areas=macroeconomia-dinero;anclas=economics"}
        ordinary=dict(base,title="A Monetary Economics Paper",summary="A conventional monetary economics study.")
        plural=dict(base,title="Post-Keynesian Effective Demand",summary="Post-Keynesian effective demand and endogenous money.")
        regional=dict(base,title="Economic Development in Peru",summary="Economic development and institutions in Peru.")
        now=reference_now()
        self.assertGreater(preverification_score(plural,cfg,now),preverification_score(ordinary,cfg,now))
        self.assertGreater(preverification_score(regional,cfg,now),preverification_score(ordinary,cfg,now))

    def test_planner_reads_canonical_score_only(self):
        self.assertEqual(editorial_index_10({"editorial_score":"8.5","notas":"indice_editorial=2"}),8.5)
        self.assertEqual(editorial_index_10({"notas":"editorial_score=9"}),0.0)

class TemplateRenderingTests(unittest.TestCase):
    def test_templates_render_real_newlines(self):
        paper=render_text("paper",{
            "title":"Título","authors":"A. Autora","source_or_series":"Serie","year":"2026",
            "access_url":"https://example.org/paper.pdf"})
        self.assertIn("\n\nTítulo\n\n",paper)
        self.assertNotIn("\\\\n",paper)

        book=render_text("book",{
            "title":"Libro","authors_or_editors":"B. Autor","year":"2026",
            "access_url":"https://example.org/book.pdf"})
        self.assertIn("\n\nLibro\n\n",book)
        self.assertNotIn("\\\\n",book)

class ConfigTests(unittest.TestCase):
    def test_no_generative_ai_and_no_noimage_fallback(self):
        cfg=json.loads((ROOT/"data/editorial/programacion.json").read_text(encoding="utf-8"))
        self.assertFalse(cfg["generative_ai"]["enabled"])
        self.assertNotIn("no_image",cfg["paper_visual"]["preference"])
        self.assertFalse(cfg["archivo_historico"]["stop_when_target_date_reached"])

    def test_expanded_academic_sources_are_configured(self):
        src=json.loads((ROOT/"data/editorial/fuentes.json").read_text(encoding="utf-8"))
        by_id={x["id"]:x for x in src["fuentes"]}
        self.assertTrue({"scielo-books-oai","dialnet-articles-oai","dialnet-theses-oai","clacso-repository-oai"} <= set(by_id))
        self.assertTrue(by_id["clacso-repository-oai"]["habilitada"])
        self.assertTrue(by_id["dialnet-articles-oai"]["habilitada"])
        self.assertFalse(by_id["scielo-books-oai"]["habilitada"])
        self.assertIn("TLS",by_id["scielo-books-oai"]["nota"])

if __name__=="__main__":
    unittest.main()
