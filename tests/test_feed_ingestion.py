"""Offline regression for extended candidate CSVs and failure-safe persistence."""
import csv
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/editorial'))
import ingerir_feeds as feeds


class FeedIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'candidatos.csv'
        self.cfg = Path(self.tmp.name) / 'fuentes.json'
        self.cfg.write_text(json.dumps({'fuentes': [
            {'id': 'test', 'habilitada': True, 'tipo': 'rss', 'url': 'https://example.org/feed'}
        ]}))
        for name, value in [('OUT', self.out), ('CFG', self.cfg)]:
            mock = patch.object(feeds, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(feeds, 'fetch', return_value=ET.fromstring(
            '<rss><channel><item><title>New paper</title><link>https://example.org/new</link>'
            '<guid>new</guid></item></channel></rss>'))
        mock.start()
        self.addCleanup(mock.stop)

    def write(self, fields, rows):
        with self.out.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def read(self):
        with self.out.open(newline='') as f:
            reader = csv.DictReader(f)
            return list(reader), reader.fieldnames

    def test_actual_repository_schema_preserved_and_rerun_deduplicates(self):
        with (ROOT / 'data/editorial/candidatos.csv').open(newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fields = reader.fieldnames
        self.assertTrue(set(fields) - set(feeds.FIELDS))
        self.write(fields, rows)
        feeds.main()
        result, header = self.read()
        self.assertEqual(header, fields)
        self.assertEqual(result[:-1], rows)
        self.assertEqual(len(result), len(rows) + 1)
        self.assertEqual(result[-1]['title'], 'New paper')
        self.assertEqual(result[-1]['title_original'], '')
        feeds.main()
        self.assertEqual(self.read()[0], result)

    def test_empty_extended_header_survives(self):
        self.write(['source_id', 'source_item_id', 'future_metadata'], [])
        feeds.main()
        rows, fields = self.read()
        self.assertIn('future_metadata', fields)
        self.assertEqual(rows[0]['future_metadata'], '')
        self.assertTrue(set(feeds.FIELDS) <= set(fields))

    def test_creates_missing_csv(self):
        feeds.main()
        rows, fields = self.read()
        self.assertEqual(fields, feeds.FIELDS)
        self.assertEqual(len(rows), 1)

    def test_serialization_failure_leaves_original_intact(self):
        self.write(feeds.FIELDS, [])
        original = self.out.read_bytes()
        with patch.object(feeds.csv.DictWriter, 'writerows', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                feeds.main()
        self.assertEqual(self.out.read_bytes(), original)
        self.assertEqual(sorted(p.name for p in self.out.parent.iterdir()),
                         ['candidatos.csv', 'fuentes.json'])


if __name__ == '__main__':
    unittest.main()
