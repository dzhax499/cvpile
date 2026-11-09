"""Export pasted or TXT lines to a plain, single-column Excel workbook."""

from io import BytesIO
from pathlib import Path
import re


def parse_number_lines(text):
    rows = [line.strip() for line in text.lstrip('\ufeff').splitlines() if line.strip()]
    if not rows:
        raise ValueError('Daftar nomor kosong. Pilih TXT atau paste nomor terlebih dahulu.')
    if len(rows) > 1_048_576:
        raise ValueError('Maksimal 1.048.576 baris dalam satu file XLSX.')
    for index, row in enumerate(rows, 1):
        if len(row) > 32767 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', row):
            raise ValueError(f'Baris {index} terlalu panjang atau mengandung karakter yang tidak didukung Excel.')
    return rows


def read_number_txt(path):
    raw = Path(path).read_bytes()
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    return parse_number_lines(raw.decode(encoding))


def write_numbers_xlsx(rows, output_path):
    # Import only when needed so other tools remain usable without this package.
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet('Sheet1')
    for number in rows:
        cell = WriteOnlyCell(sheet, value=number)
        # Preserve leading zeros, '+' and long numbers; never interpret formulas.
        cell.data_type = 's'
        sheet.append([cell])
    data = BytesIO()
    try:
        workbook.save(data)
    finally:
        workbook.close()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = 0
    while True:
        path = destination if suffix == 0 else destination.with_name(f'{destination.stem}_{suffix}.xlsx')
        try:
            target = path.open('xb')
            break
        except FileExistsError:
            suffix += 1
    with target:
        target.write(data.getbuffer())
    return str(path)
