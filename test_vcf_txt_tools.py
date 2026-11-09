"""Tests for VCF imports and bulk TXT outputs."""

import tempfile
import unittest
from pathlib import Path

from vcf_txt_tools import (parse_vcf_text, read_vcf, format_txt_row,
                           plan_txt_files, write_txt_files)


class VCFImportTests(unittest.TestCase):
    def test_multiple_phones_unnamed_and_uri(self):
        text = ('\ufeffBEGIN:VCARD\nVERSION:4.0\nFN:Andi\n'
                'TEL;VALUE=uri:tel:+628123\nitem1.TEL;TYPE=HOME:081234\nEND:VCARD\n'
                'BEGIN:VCARD\nTEL:+628999\nEND:VCARD\n'
                'BEGIN:VCARD\nFN:No phone\nEND:VCARD\n')
        self.assertEqual(parse_vcf_text(text), [('+628123', 'Andi'), ('081234', 'Andi'), ('+628999', '')])

    def test_folded_escaped_unicode_and_structured_name(self):
        text = ('BEGIN:VCARD\r\nFN:Grup\\, A\\;B\\\\C\\n名\r\n lanjutan\r\n'
                'TEL:00123\r\nEND:VCARD\r\n'
                'BEGIN:VCARD\nN:Doe;Jane;A\\;B;;\nTEL:00456\nEND:VCARD\n')
        rows = parse_vcf_text(text)
        self.assertEqual(rows, [('00123', 'Grup, A;B\\C\n名lanjutan'), ('00456', 'Doe Jane A;B')])
        self.assertEqual(format_txt_row(rows[0], True), '00123 Grup, A;B\\C 名lanjutan')

    def test_quoted_printable_and_incomplete_card(self):
        text = ('BEGIN:VCARD\nFN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Jos=C3=\n'
                '=A9\nTEL:+123\nEND:VCARD\n')
        self.assertEqual(parse_vcf_text(text), [('+123', 'José')])
        with self.assertRaises(ValueError):
            parse_vcf_text('BEGIN:VCARD\nTEL:123')

    def test_utf16_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.vcf'
            path.write_text('BEGIN:VCARD\nFN:名\nTEL:0123\nEND:VCARD', encoding='utf-16')
            self.assertEqual(read_vcf(path), [('0123', '名')])


class TXTExportTests(unittest.TestCase):
    def setUp(self):
        self.rows = [('0123', 'Andi'), ('+62456', ''), ('0123', 'Nama lain')]
        self.sources = [('Satu', self.rows[:2]), ('Dua', self.rows[2:])]

    def test_combined_split_and_source_preserve_order(self):
        combined = plan_txt_files(self.sources)
        self.assertEqual(combined, [('contacts', self.rows)])
        split = plan_txt_files(self.sources, 'split', 2, 'Tim')
        self.assertEqual(split, [('Tim-1', self.rows[:2]), ('Tim-2', self.rows[2:])])
        self.assertEqual(plan_txt_files(self.sources, 'source'), self.sources)
        self.assertEqual(plan_txt_files(self.sources, 'split', 99), combined)

    def test_rename_fallback_and_invalid_input(self):
        plan = plan_txt_files(self.sources, 'split', 2, rename_names=['Custom'])
        self.assertEqual([stem for stem, _ in plan], ['Custom', 'Z2'])
        for per in (0, -1, None, 'two'):
            with self.subTest(per=per), self.assertRaises(ValueError):
                plan_txt_files(self.sources, 'split', per)
        for name in ('../outside', 'CON', 'NUL.txt', 'bad:', 'bad.'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                plan_txt_files(self.sources, 'source', rename_names=['Okay', name])
        with self.assertRaises(ValueError):
            plan_txt_files([('Empty', [])])

    def test_write_named_unnamed_collision_and_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            existing = Path(folder) / 'Tim.txt'
            existing.write_text('keep', encoding='utf-8')
            plan = plan_txt_files(self.sources, 'source', rename_names=['Tim', 'Tim'])
            progress = []
            paths = write_txt_files(plan, folder, True, lambda *args: progress.append(args))
            self.assertEqual([Path(path).name for path in paths], ['Tim_1.txt', 'Tim_2.txt'])
            self.assertEqual(existing.read_text(), 'keep')
            self.assertEqual(Path(paths[0]).read_bytes(), b'0123 Andi\r\n+62456\r\n')
            self.assertEqual(progress[-1][2], 1)
            paths = write_txt_files(plan_txt_files(self.sources), folder)
            self.assertEqual(Path(paths[0]).read_bytes(), b'0123\r\n+62456\r\n0123\r\n')

    def test_validate_entire_plan_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                write_txt_files([('Okay', self.rows), ('../bad', self.rows)], folder)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
