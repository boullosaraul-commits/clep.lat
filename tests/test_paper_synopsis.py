import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/editorial'))
from sinopsis_papers import enrich, generate, valid_synopsis
from preparar_publicacion import meta_for, text_context
from renderizar_texto import render_result
from resolver_media import resolve_media


class SynopsisTests(unittest.TestCase):
    def row(self):
        return {'candidate_id':'TEST', 'content_type':'paper', 'title':'Money and employment',
                'authors':'A. Author', 'publication_year':'2026', 'source_name':'Working Papers',
                'source_url':'https://example.org/paper', 'access_url':'https://example.org/paper',
                'language':'en', 'summary':'The paper studies monetary policy and employment using a theoretical model.',
                'editorial_decision':'PUBLISHABLE'}

    def test_generation_render_and_source_invalidation(self):
        row=self.row()
        summary='El artículo estudia la relación entre política monetaria y empleo mediante un modelo teórico.'
        fn=lambda *args: (summary, 'Dinero y empleo', [row['summary']])
        self.assertEqual(enrich([row], 'key', generator=fn)['generated'], 1)
        self.assertTrue(valid_synopsis(row))
        meta=meta_for('paper',row);meta.update(text_context(row))
        result=render_result('paper',meta)
        self.assertIn(summary,result.post_text)
        self.assertIn('asistida por IA',result.post_text)
        self.assertEqual(result.editorial_description,summary)
        self.assertEqual(enrich([row],'key',generator=lambda *a:self.fail('cache miss'))['generated'],0)
        row['summary'] += ' New evidence.'
        self.assertFalse(valid_synopsis(row))

    def test_missing_key_uses_only_spanish_source(self):
        row=self.row()
        self.assertEqual(enrich([row])['extractive'],0)
        self.assertNotIn('sinopsis_es',row)
        row['language']='es'
        self.assertEqual(enrich([row])['extractive'],0)
        row['summary']='Este artículo estudia la política monetaria y el empleo mediante un modelo teórico para analizar sus efectos con una estructura explícita.'
        self.assertEqual(enrich([row])['extractive'],1)
        self.assertTrue(valid_synopsis(row))
        self.assertEqual(row['sinopsis_es'],row['summary'])

    def test_invalid_evidence_and_incomplete_responses_fail(self):
        class Response:
            def __init__(self,payload):self.payload=payload
            def __enter__(self):
                import io
                return io.StringIO(json.dumps(self.payload))
            def __exit__(self,*args):pass
        output={'sinopsis_es':'Una sinopsis larga sobre política monetaria que debe estar respaldada por el resumen original.',
                'title_es':'Dinero y empleo','evidence':['This quote is fabricated.']}
        payload={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(output)}]}]}
        with patch('urllib.request.urlopen',return_value=Response(payload)):
            with self.assertRaisesRegex(ValueError,'EVIDENCE_NOT_IN_SOURCE'):
                generate(self.row(),'key','model')
        with patch('urllib.request.urlopen',return_value=Response({'status':'incomplete'})):
            with self.assertRaisesRegex(ValueError,'INCOMPLETE'):
                generate(self.row(),'key','model')

    def test_api_error_preserves_other_rows_and_fallback(self):
        row=self.row();row['language']='es';row['summary']='Este artículo estudia la política monetaria y el empleo mediante un modelo teórico para analizar sus efectos con una estructura explícita.'
        def fail(*args):raise RuntimeError('unavailable')
        result=enrich([row],'key',generator=fail)
        self.assertEqual(result,{'generated':0,'extractive':1,'failed':1})
        self.assertEqual(row['synopsis_method'],'extractive_es')

    def test_card_receives_synopsis_instead_of_landing_capture(self):
        row=self.row();row['sinopsis_es']='Una sinopsis editorial basada en el resumen original y sin resultados inventados.'
        row['synopsis_method']='llm_source_grounded'
        result=resolve_media(row)
        self.assertEqual(result.media_method,'deterministic_card')
        self.assertEqual(result.acquisition_payload['synopsis'],row['sinopsis_es'])
