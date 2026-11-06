"""验证长度计算、逗号绕过、段末扫描和图文材料，不调用模型。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prose_metrics import reading_length, split_sentences, split_clauses, comma_only_changes
from scan_syntax import scan_syntax
from scan_redundancy import scan_redundancy
from scan_visuals import scan_visuals
from doc_parser import load_document_items
from xml.etree import ElementTree as ET


def write_document(path, body):
    namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml',
                         f'<w:document xmlns:w="{namespace}"><w:body>{body}</w:body></w:document>')


class WordingReviewTests(unittest.TestCase):
    def test_skip_cover_at_saved_page_boundaries(self):
        cover = '<w:p><w:r><w:t>封面字段</w:t></w:r></w:p>'
        boundaries = [
            '<w:p><w:pPr><w:pageBreakBefore/></w:pPr><w:r><w:t>正文内容</w:t></w:r></w:p>',
            '<w:p><w:r><w:t>封面尾行</w:t><w:br w:type="page"/><w:t>正文内容</w:t></w:r></w:p>',
            '<w:p><w:r><w:t>封面尾行</w:t><w:lastRenderedPageBreak/><w:t>正文内容</w:t></w:r></w:p>',
            '<w:p><w:pPr><w:sectPr><w:type w:val="nextPage"/></w:sectPr></w:pPr></w:p>'
            '<w:p><w:r><w:t>正文内容</w:t></w:r></w:p>',
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'pages.docx'
            for boundary in boundaries:
                with self.subTest(boundary=boundary):
                    write_document(path, cover + boundary)
                    rows = load_document_items(path, skip_first_page=True)
                    self.assertEqual([text for _, text, _ in rows], ['正文内容'])
                    self.assertEqual(rows[0][0], 'P2')

    def test_cli_cover_default_and_override(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'pages.docx'
            cover = '<w:p><w:r><w:t>封面字段</w:t></w:r></w:p>'
            body = '<w:p><w:pPr><w:pageBreakBefore/></w:pPr><w:r><w:t>正文内容</w:t></w:r></w:p>'
            write_document(path, cover + body)
            args = [sys.executable, str(ROOT / 'scripts/check_prose.py'), str(path), '--stage', 'redundancy']
            result = subprocess.run(args, capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('封面字段', result.stdout)
            self.assertIn('正文内容', result.stdout)
            result = subprocess.run(args + ['--include-cover'], capture_output=True, encoding='utf-8')
            self.assertIn('封面字段', result.stdout)
            write_document(path, cover)
            result = subprocess.run(args, capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 2)
            self.assertIn('PAGE_BOUNDARY_MISSING', result.stderr)

    def test_missing_visual_returns_pending_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'draft.md'
            path.write_text('正文。\n\n<!-- FIGURE: diagram -->', encoding='utf-8')
            for stage in ['visuals', 'all']:
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/check_prose.py'), str(path), '--stage', stage],
                    capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn('MATERIALS_PENDING', result.stdout)

    def test_units_and_code(self):
        self.assertEqual(reading_length('“中文”，CPU 512。'), 4)
        self.assertEqual(reading_length('中文 `record->value` assets/ input/data.csv load()。'), 2)
        self.assertEqual(reading_length('数值3.14'), 3)

    def test_token_punctuation_is_not_a_boundary(self):
        self.assertEqual(len(split_clauses('调用 read(fd, buf, 1)，返回结果。')), 2)
        self.assertEqual(len(split_sentences('读取 data.csv。随后调用 load()。')), 2)
        self.assertEqual(split_clauses('首先处理；随后返回。'), ['首先处理', '随后返回'])

    def test_fifteen_boundary(self):
        result = scan_syntax([('P1', '甲' * 15 + '，' + '乙' * 16 + '。', 'p')])
        self.assertEqual(result['max_clause_len'], 15)
        self.assertEqual(result['long_clauses'], [('P1', 16, '乙' * 16)])

    def test_comma_only_bypass_and_real_rewrite(self):
        before = [('P1', '甲' * 19 + '。')]
        after = [('P2', '甲' * 9 + '，' + '甲' * 10 + '。')]
        self.assertEqual(len(comma_only_changes(before, after)), 1)
        self.assertEqual(comma_only_changes(before, [('P2', '甲' * 9 + '。' + '甲' * 10 + '。')]), [])
        self.assertEqual(comma_only_changes(before, [('P2', '乙' * 10 + '。')]), [])

    def test_defensive_hits_and_tail_are_separate(self):
        text = '严格来说先处理输入。而非省略检查，仅用于说明边界。'
        result = scan_redundancy([('P1', text, 'p')])
        hits = [r[2] for r in result['pattern_hits']]
        self.assertTrue({'严格来说', '而非', '仅用于说明'} <= set(hits))
        self.assertNotIn('严格来说', result['paragraph_tails'][0][2])
        self.assertIn('而非', result['paragraph_tails'][0][2])
        self.assertEqual(result['paragraph_tails'][0][3], text)

    def test_visual_assets_and_missing_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            path = temp / 'sample.docx'
            w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            xml = f'''<w:document xmlns:w="{w}" xmlns:r="{r}" xmlns:a="urn:a"><w:body>
            <w:p><w:r><w:t>前文说明</w:t></w:r></w:p>
            <w:p><w:r><a:blip r:embed="rId1"/></w:r></w:p>
            <w:tbl><w:tr><w:tc><w:p><w:r><w:t>参数</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>值</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
            <w:p><w:r><w:t>后文分析</w:t></w:r></w:p></w:body></w:document>'''
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('word/document.xml', xml)
                archive.writestr('word/_rels/document.xml.rels', '<Relationships><Relationship Id="rId1" Target="media/a.png"/></Relationships>')
                archive.writestr('word/media/a.png', b'example-image-bytes')
            result = scan_visuals(path, temp / 'assets')
            self.assertEqual(result['pending'], [])
            self.assertEqual([g['kind'] for g in result['groups']], ['image', 'table'])
            image = result['groups'][0]
            self.assertEqual(Path(image['images'][0]).read_bytes(), b'example-image-bytes')
            self.assertEqual(image['before'][0]['text'], '前文说明')
            self.assertEqual(image['after'][0]['text'], '后文分析')
            md = temp / 'pending.md'
            md.write_text('正文\n\n<!-- FIGURE: diagram -->', encoding='utf-8')
            self.assertTrue(scan_visuals(md)['pending'])

    def test_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            before, after = temp / 'before.md', temp / 'after.md'
            before.write_text('甲' * 19 + '。', encoding='utf-8')
            after.write_text('甲' * 9 + '，' + '甲' * 10 + '。', encoding='utf-8')
            args = [sys.executable, str(ROOT / 'scripts/check_prose.py'), str(after),
                    '--stage', 'syntax', '--check', '--compare-to', str(before)]
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            after.write_text('乙' * 10 + '。', encoding='utf-8')
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_exception_matches_one_exact_clause(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'sample.md'
            first, second = '甲' * 16, '乙' * 16
            path.write_text(first + '，' + second + '。', encoding='utf-8')
            args = [sys.executable, str(ROOT / 'scripts/check_prose.py'), str(path),
                    '--stage', 'syntax', '--check', '--length-exempt', 'L1:' + first]
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 1)
            path.write_text(first + '。', encoding='utf-8')
            result = subprocess.run(args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(first, result.stdout.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
