"""Check Excel output using an independent workbook readback."""

from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook
from xlsx_tools import parse_number_lines, read_number_txt, write_numbers_xlsx


class ExcelExportTests(unittest.TestCase):
    def test_plain_column_preserves_phone_text_and_duplicates(self):
        rows = parse_number_lines('\ufeff08123456789\r\n+628123456789\n\n12345678901234567890\n08123456789\n=1+1\n')
        with tempfile.TemporaryDirectory() as folder:
            path = write_numbers_xlsx(rows, Path(folder) / 'numbers.xlsx')
            workbook = load_workbook(path)
            try:
                self.assertEqual(workbook.sheetnames, ['Sheet1'])
                sheet = workbook.active
                self.assertEqual(sheet.max_column, 1)
                self.assertEqual(sheet.max_row, len(rows))
                self.assertEqual([cell.value for cell in sheet['A']], rows)
                self.assertTrue(all(cell.data_type == 's' for cell in sheet['A']))
                self.assertFalse(sheet.tables)
                self.assertTrue(all(not cell.has_style for cell in sheet['A']))
            finally:
                workbook.close()

    def test_file_encodings_and_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.txt'
            for encoding in ('utf-8-sig', 'utf-16'):
                source.write_text('00123\n+456\n', encoding=encoding)
                self.assertEqual(read_number_txt(source), ['00123', '+456'])
            output = Path(folder) / 'input.xlsx'
            output.write_bytes(b'keep')
            new_path = write_numbers_xlsx(['00123'], output)
            self.assertEqual(Path(new_path).name, 'input_1.xlsx')
            self.assertEqual(output.read_bytes(), b'keep')

    def test_empty_and_unrepresentable_input_is_rejected(self):
        for text in (' \n\t', '\ufeff', '123\x00', '1' * 32768):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                parse_number_lines(text)


if __name__ == '__main__':
    unittest.main()
