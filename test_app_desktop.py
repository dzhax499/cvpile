"""Regression checks: python -m unittest test_app_desktop -v"""

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app_desktop as app


class NameSyncTests(unittest.TestCase):
    def setUp(self):
        self.tk = tk.Tcl()
        self.enabled = tk.BooleanVar(self.tk, False)
        self.contact = tk.StringVar(self.tk, 'REY')
        self.filename = tk.StringVar(self.tk, '')
        self.link = app.SyncedNames(self.enabled, self.contact, self.filename)

    def test_both_directions_clear_and_uncheck(self):
        self.enabled.set(True)
        self.assertEqual(self.filename.get(), 'REY')
        self.contact.set('Kontak Baru')
        self.assertEqual(self.filename.get(), 'Kontak Baru')
        self.filename.set('Nama File')
        self.assertEqual(self.contact.get(), 'Nama File')
        self.filename.set('')
        self.assertEqual(self.contact.get(), '')
        self.enabled.set(False)
        self.filename.set('Terpisah')
        self.assertEqual(self.contact.get(), '')

    def test_enable_uses_last_edited_nonempty_field(self):
        self.filename.set('File Dulu')
        self.enabled.set(True)
        self.assertEqual(self.contact.get(), 'File Dulu')
        self.enabled.set(False)
        self.contact.set('Kontak Dulu')
        self.enabled.set(True)
        self.assertEqual(self.filename.get(), 'Kontak Dulu')


class VCardTests(unittest.TestCase):
    def test_number_normalization_and_required_fields(self):
        card, valid = app.build_vcard('REY 001', '62 812-3456-7890')
        self.assertTrue(valid)
        self.assertIn('TEL;TYPE=CELL:+6281234567890\r\n', card)
        for field in ('VERSION:3.0', 'N:REY 001', 'FN:REY 001'):
            self.assertIn(field + '\r\n', card)
        self.assertNotIn('NOTE:', card)
        self.assertTrue(card.startswith('BEGIN:VCARD\r\n'))
        self.assertTrue(card.endswith('END:VCARD\r\n'))

    def test_clean_phone_number_regex_08_and_formatting(self):
        # 0821xxx with spaces, dashes, parentheses -> 62821xxx
        self.assertEqual(app.clean_phone_number('0821-1234-5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('0821 1234 5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('0821 - 1234 - 5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('(0821) 1234-5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('0821.1234.5678'), '6282112345678')
        # Variants: +62 821, 62821, +620821, 620821, +0821
        self.assertEqual(app.clean_phone_number('+62 821-1234-5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('62821-1234-5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('+620821-1234-5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('620821-1234-5678'), '6282112345678')
        self.assertEqual(app.clean_phone_number('+0821-1234-5678'), '6282112345678')
        # Other Indonesian 08 prefixes
        self.assertEqual(app.clean_phone_number('0812-3456-7890'), '6281234567890')
        self.assertEqual(app.clean_phone_number('0857-1234-5678'), '6285712345678')
        # build_vcard produces valid +62821xxx
        card, valid = app.build_vcard('ADMIN A1 001', '0821-1234-5678')
        self.assertTrue(valid)
        self.assertIn('TEL;TYPE=CELL:+6282112345678\r\n', card)

    def test_invalid_phone_is_retained_and_reported(self):
        card, valid = app.build_vcard('Invalid', '123')
        self.assertFalse(valid)
        self.assertIn('TEL;TYPE=CELL:+123\r\n', card)

    def test_unicode_escaping_and_folding(self):
        name = 'Grup, A;B\\C\r\n' + '\U0001f600\u540d' * 40
        card, _ = app.build_vcard(name, '+6281234567890')
        for line in card.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75)
        unfolded = card.replace('\r\n ', '')
        expected = 'Grup\\, A\\;B\\\\C\\n' + '\U0001f600\u540d' * 40
        self.assertIn('FN:' + expected + '\r\n', unfolded)
        self.assertEqual(len(unfolded.splitlines()), 6)

    def test_1000_contacts_smaller_than_original_output(self):
        phone = '+6281234567890'
        cards = [app.build_vcard(f'REY {i:03d}', phone)[0]
                 for i in range(1, 1001)]
        old = ''.join(
            f'BEGIN:VCARD\r\nVERSION:3.0\r\nFN:REY {i:03d}\r\n'
            f'TEL;TYPE=CELL:{app.format_phone_number(phone)}\r\n'
            f'NOTE:Country: {app.detect_country(phone)}\r\nEND:VCARD\r\n'
            for i in range(1, 1001))
        new = ''.join(cards)
        self.assertEqual(new.count('BEGIN:VCARD\r\n'), 1000)
        self.assertEqual(new.count('TEL;TYPE=CELL:' + phone), 1000)
        self.assertLess(len(new.encode()), len(old.encode()) * 0.85)


class BulkOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.folder_patch = patch.object(app, 'get_output_folder', return_value=self.temp.name)
        self.folder_patch.start()
        self.addCleanup(self.folder_patch.stop)
        self.ui = SimpleNamespace(bulk_log_w=None, _log=Mock(),
                                  bulk_prog=SimpleNamespace(set=Mock()), after=Mock())

    def write(self, **kwargs):
        args = dict(contacts=['6281234567890', '+6281234567891', '123'],
                    per_file=2, base_name='Kontak', start=50, digits=3,
                    rename_names=None)
        args.update(kwargs)
        app.VCFToolsApp._bulk_write_files(self.ui, **args)

    def read(self, filename):
        raw = (self.output / filename).read_bytes()
        self.assertNotIn(b'\r\r\n', raw)
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
        return raw.decode('utf-8')

    def test_split_synced_names_and_sequence(self):
        self.write(file_name='Tim', sync_names=True)
        first = self.read('Tim-1.vcf')
        second = self.read('Tim-2.vcf')
        self.assertEqual(first.count('BEGIN:VCARD'), 2)
        self.assertEqual(second.count('BEGIN:VCARD'), 1)
        self.assertIn('FN:Tim-1 050\r\n', first)
        self.assertIn('FN:Tim-1 051\r\n', first)
        self.assertIn('FN:Tim-2 052\r\n', second)
        self.assertIn('TEL;TYPE=CELL:+123\r\n', second)

    def test_single_output_and_sync_off(self):
        self.write(per_file=10, file_name='File', sync_names=False)
        card = self.read('File.vcf')
        self.assertIn('FN:Kontak 050\r\n', card)
        self.assertEqual(card.count('BEGIN:VCARD'), 3)

    def test_rename_list_collision_and_missing_names(self):
        (self.output / 'Grup.vcf').write_bytes(b'keep existing')
        self.write(rename_names=['Grup'], sync_names=True)
        self.assertEqual((self.output / 'Grup.vcf').read_bytes(), b'keep existing')
        self.assertIn('FN:Grup_1 050\r\n', self.read('Grup_1.vcf'))
        self.assertIn('FN:Z2 052\r\n', self.read('Z2.vcf'))

    def test_default_filenames_and_no_name_mode(self):
        self.write(no_name=True)
        self.assertIn('FN:6281234567890\r\n', self.read('Z1.vcf'))
        self.assertIn('FN:123\r\n', self.read('Z2.vcf'))

    def test_invalid_name_rejected_before_any_output(self):
        for name in ('../escape', 'CON', 'NUL.txt', 'bad:name', 'bad.', 'LPT1'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.write(rename_names=['Okay', name])
        self.assertEqual(list(self.output.iterdir()), [])

    def test_parse_contact_line_variants(self):
        cases = [
            ('Budi Santoso - 081234567890', ('081234567890', 'Budi Santoso')),
            ('081234567890 - Budi Santoso', ('081234567890', 'Budi Santoso')),
            ('Andi-6281234567890', ('6281234567890', 'Andi')),
            ('6281234567890-Andi', ('6281234567890', 'Andi')),
            ('CS - 01 - +62 812-3456-7890', ('+62 812-3456-7890', 'CS - 01')),
            ('+6281234567890 Budi 01', ('+6281234567890', 'Budi 01')),
            ('Budi 01 +6281234567890', ('+6281234567890', 'Budi 01')),
            ('Siti : 081299998888', ('081299998888', 'Siti')),
            ('+62 812-3456-7890', ('+62 812-3456-7890', '')),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(app.parse_contact_line(raw), expected)

    def test_custom_split_5000_to_2000_2000_1000_and_name_phone(self):
        self.assertEqual(app.parse_chunk_sizes(5000, '2000,2000,1000'), [2000, 2000, 1000])
        self.assertEqual(app.parse_chunk_sizes(5500, '2000, 2000, 1000'), [2000, 2000, 1000, 500])
        contacts = [
            '6281234567890',
            '6281234567891',
            '6281234567892',
            '6281234567893',
            '6281234567894',
        ]
        self.write(contacts=contacts, per_file='2,2,1', base_name='REY',
                   start=1, digits=3, file_name='Part', name_phone=True)
        part1 = self.read('Part-1.vcf')
        part2 = self.read('Part-2.vcf')
        part3 = self.read('Part-3.vcf')
        self.assertEqual(part1.count('BEGIN:VCARD'), 2)
        self.assertEqual(part2.count('BEGIN:VCARD'), 2)
        self.assertEqual(part3.count('BEGIN:VCARD'), 1)
        self.assertIn('N:REY-6281234567890\r\n', part1)
        self.assertIn('FN:REY-6281234567890\r\n', part1)
        self.assertIn('N:REY-6281234567891\r\n', part1)
        self.assertIn('FN:REY-6281234567891\r\n', part1)
        self.assertIn('N:REY-6281234567892\r\n', part2)
        self.assertIn('FN:REY-6281234567892\r\n', part2)
        self.assertIn('N:REY-6281234567893\r\n', part2)
        self.assertIn('FN:REY-6281234567893\r\n', part2)
        self.assertIn('N:REY-6281234567894\r\n', part3)
        self.assertIn('FN:REY-6281234567894\r\n', part3)


class DesktopUITests(unittest.TestCase):
    def test_get_admin_tag(self):
        self.assertEqual(app.get_admin_tag('A1', 0), 'A1')
        self.assertEqual(app.get_admin_tag('A1', 1), 'A2')
        self.assertEqual(app.get_admin_tag('A1', 2), 'A3')
        self.assertEqual(app.get_admin_tag('B01', 1), 'B02')
        self.assertEqual(app.get_admin_tag('GRUP 1', 1), 'GRUP 2')
        self.assertEqual(app.get_admin_tag('', 0), '1')
        self.assertEqual(app.get_admin_tag('A', 0), 'A1')

    def test_build_extra_vcards_multiple_admin_navy(self):
        vcf, count, invalid = app.build_extra_vcards(
            '6281234567890\n\nBos Besar - 6281299998888\n6281234567891\n', 'ADMIN')
        self.assertEqual(count, 3)
        self.assertEqual(invalid, 0)
        self.assertIn('FN:ADMIN 001\r\n', vcf)
        self.assertIn('FN:Bos Besar\r\n', vcf)
        self.assertIn('FN:ADMIN 003\r\n', vcf)
        self.assertEqual(app.build_extra_vcards('', 'NAVY'), ('', 0, 0))

    def test_hidden_window_name_sync_and_mode_switches(self):
        # Withdraw immediately so this smoke test never opens a visible window.
        original_init = app.ctk.CTk.__init__

        def hidden_init(window, *args, **kwargs):
            original_init(window, *args, **kwargs)
            window.withdraw()

        with tempfile.TemporaryDirectory() as cache_dir:
            cache_path = str(Path(cache_dir) / 'cache.json')
            with patch.object(app.ctk.CTk, '__init__', hidden_init):
                window = app.VCFToolsApp(cache_file=cache_path, load_cache=False)
            try:
                window.bulk_sync_checkbox.toggle()
                self.assertTrue(window.bulk_sync_names.get())
                window.bulk_name.set('Nama Kontak')
                self.assertEqual(window.bulk_filename.get(), 'Nama Kontak')
                window.bulk_filename.set('Nama File')
                self.assertEqual(window.bulk_name.get(), 'Nama File')
                window.bulk_sync_checkbox.toggle()
                window.bulk_filename.set('Terpisah')
                self.assertEqual(window.bulk_name.get(), 'Nama File')
                window.bulk_no_name.set(True)
                window._toggle_no_name()
                window.bulk_sync_checkbox.toggle()
                self.assertFalse(window.bulk_no_name.get())
                self.assertEqual(window.bulk_name_entry.cget('state'), 'normal')
                window.bulk_no_name.set(True)
                window._toggle_no_name()
                self.assertFalse(window.bulk_sync_names.get())
                window.bulk_name_phone_checkbox.toggle()
                self.assertTrue(window.bulk_name_phone.get())
                self.assertFalse(window.bulk_no_name.get())
                self.assertEqual(window.bulk_name_entry.cget('state'), 'normal')
                window.bulk_name.set('REY')
                self.assertIn('REY-081234567890', window.bulk_preview.cget('text'))
                window.bulk_name_phone_checkbox.toggle()
                self.assertFalse(window.bulk_name_phone.get())
                window.bulk_tab.set('\U0001f4cb Paste Langsung')
                window.bulk_paste_box.insert('1.0', '6281234567890\n6281234567891\n')
                window._rename_tab.set('\U0001f4cb Paste Nama')
                window.bulk_rename_paste.insert('1.0', 'Grup Satu\nGrup Dua\n')
                window.bulk_rename_on.set(True)
                window._toggle_rename_input()
                window.bulk_sync_checkbox.toggle()
                self.assertEqual(window.bulk_per.get(), '1')
                self.assertIn('Grup Satu 001', window.bulk_preview.cget('text'))
                window._show_frame('txt')
                window.txt_tab.set('Paste VCF')
                card, _ = app.build_vcard('Nama Asli', '6281234567890')
                window.txt_paste.insert('1.0', card * 3)
                window.txt_mode.set('split')
                window._txt_mode_changed()
                self.assertEqual(window.txt_per_entry.cget('state'), 'normal')
                window.txt_per.set('2')
                window.txt_include_name.set(True)
                window.txt_rename_on.set(True)
                window.txt_rename_paste.insert('1.0', 'Pertama\nKedua')
                plan, summary = window._txt_review()
                self.assertEqual([stem for stem, _ in plan], ['Pertama', 'Kedua'])
                self.assertEqual([len(rows) for _, rows in plan], [2, 1])
                self.assertIn('+6281234567890 Nama Asli', window.txt_preview.get('1.0', 'end'))
                window.txt_mode.set('combined')
                window._txt_mode_changed()
                self.assertEqual(window.txt_per_entry.cget('state'), 'disabled')
                with tempfile.TemporaryDirectory() as folder:
                    window.txt_output_folder = folder
                    with patch.object(app.messagebox, 'askyesno', return_value=True), \
                            patch.object(app.messagebox, 'showinfo') as success:
                        window._txt_go()
                        import time
                        deadline = time.monotonic() + 5
                        while window._txt_running and time.monotonic() < deadline:
                            window.update()
                            time.sleep(0.01)
                        self.assertFalse(window._txt_running)
                        success.assert_called_once()
                    self.assertEqual((Path(folder) / 'Pertama.txt').read_text(encoding='utf-8'),
                                     '+6281234567890 Nama Asli\n' * 3)
                window._show_frame('xlsx')
                window.xlsx_tab.set('Paste Langsung')
                window.xlsx_paste.insert('1.0', '081234567890\n+6281234567890\n12345678901234567890\n')
                with tempfile.TemporaryDirectory() as folder:
                    window.xlsx_output_folder = folder
                    window.xlsx_filename.set('Nomor.xlsx')
                    rows, output = window._xlsx_review()
                    self.assertEqual(len(rows), 3)
                    self.assertEqual(Path(output).name, 'Nomor.xlsx')
                    with patch.object(app.messagebox, 'showinfo') as success:
                        window._xlsx_go()
                        deadline = time.monotonic() + 10
                        while window._xlsx_running and time.monotonic() < deadline:
                            window.update()
                            time.sleep(0.01)
                        self.assertFalse(window._xlsx_running)
                        success.assert_called_once()
                    from openpyxl import load_workbook
                    book = load_workbook(output)
                    try:
                        self.assertEqual([cell.value for cell in book.active['A']], rows)
                    finally:
                        book.close()
                    source = Path(folder) / 'Dari TXT.txt'
                    source.write_text('00123\n+62456\n', encoding='utf-8-sig')
                    window._xlsx_drop(SimpleNamespace(data=window.tk.call('list', str(source))))
                    window.xlsx_filename.set('')
                    rows, output = window._xlsx_review()
                    self.assertEqual(rows, ['00123', '+62456'])
                    self.assertEqual(Path(output).name, 'Dari TXT.xlsx')

                # Multi-TXT bulk test
                with tempfile.TemporaryDirectory() as m_folder:
                    m_path = Path(m_folder)
                    (m_path / 'Grup A.txt').write_text('6281234567890\n6281234567891\n', encoding='utf-8')
                    (m_path / 'Grup B.txt').write_text('6281299990000\n', encoding='utf-8')
                    window._bulk_set_paths([str(m_path / 'Grup A.txt'), str(m_path / 'Grup B.txt')])
                    self.assertEqual(len(window._bulk_paths()), 2)
                    self.assertEqual(len(window._get_bulk_contacts_silent()), 3)
                    self.assertIn('2 file TXT', window._bulk_drop_label.cget('text'))
                    jobs = window._bulk_txt_jobs()
                    self.assertEqual(len(jobs), 2)
                    self.assertEqual(jobs[0][0], 'Grup A')
                    self.assertEqual(jobs[1][0], 'Grup B')

                # Admin Creator test with '.' and ',' plus extra admin/navy
                with tempfile.TemporaryDirectory() as adm_folder:
                    adm_path = Path(adm_folder)
                    window._show_frame('admin')
                    window.admin_tab.set('📋 Paste Langsung')
                    window.admin_paste_box.delete('1.0', 'end')
                    window.admin_paste_box.insert('1.0', '0821-1111-2222\n.\n0821 2222 3333\n,\n')
                    window._admin_load()
                    self.assertEqual(len(window._admin_groups), 3)

                    window.admin_extra_admin_box.delete('1.0', 'end')
                    window.admin_extra_admin_box.insert('1.0', '0821-3333-4444\n')
                    window.admin_extra_navy_box.delete('1.0', 'end')
                    window.admin_extra_navy_box.insert('1.0', '0821-4444-5555\n')

                    with patch.object(app, 'get_output_folder', return_value=str(adm_path)), \
                            patch.object(app.messagebox, 'showinfo'):
                        dialog = window._admin_process()
                        dialog.go()

                    saved_files = list(adm_path.glob('*.vcf'))
                    self.assertEqual(len(saved_files), 1)
                    self.assertEqual(saved_files[0].name, 'ADMINNAVY A1.vcf')
                    content = saved_files[0].read_text(encoding='utf-8')
                    self.assertIn('FN:ADMIN A1 001', content)
                    self.assertIn('TEL;TYPE=CELL:+6282111112222', content)
                    self.assertIn('FN:ADMIN A1 002', content)
                    self.assertIn('TEL;TYPE=CELL:+6282133334444', content)
                    self.assertIn('FN:NAVY A1 001', content)
                    self.assertIn('TEL;TYPE=CELL:+6282122223333', content)
                    self.assertIn('FN:NAVY A1 002', content)
                    self.assertIn('TEL;TYPE=CELL:+6282144445555', content)

                # Test 30-minute session cache save on close and restore within 30 minutes
                window.bulk_sync_names.set(False)
                window.bulk_name.set('CACHED_USER')
                window.bulk_per.set('2000,2000,1000')
                window.bulk_name_phone.set(True)
                window._save_session_cache(now=1000.0)
                self.assertTrue(Path(cache_path).is_file())

                window.bulk_name.set('RESET')
                window.bulk_per.set('')
                window.bulk_name_phone.set(False)
                # Within 30 minutes (e.g. +10 minutes = 1600.0): restores state
                self.assertTrue(window._load_session_cache(now=1600.0))
                self.assertEqual(window.bulk_name.get(), 'CACHED_USER')
                self.assertEqual(window.bulk_per.get(), '2000,2000,1000')
                self.assertTrue(window.bulk_name_phone.get())

                # After 30 minutes (e.g. +31 minutes = 2861.0): expires and deletes cache file
                self.assertFalse(window._load_session_cache(now=2861.0))
                self.assertFalse(Path(cache_path).exists())
                window.update_idletasks()
            finally:
                window.destroy()


if __name__ == '__main__':
    unittest.main()
