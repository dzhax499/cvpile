"""VCF reading and bulk TXT export, independent of the desktop UI."""

import os
import quopri
import re


def _unescape(value):
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1].lower() == 'n' else m[1], value)


def parse_vcf_text(text):
    """Return (phone, name) rows, retaining every TEL and unnamed contact."""
    lines = []
    for line in text.lstrip('\ufeff').splitlines():
        if (lines and lines[-1].endswith('=')
                and 'ENCODING=QUOTED-PRINTABLE' in lines[-1].split(':', 1)[0].upper()):
            lines[-1] = lines[-1][:-1] + line.lstrip(' \t')
        elif line.startswith((' ', '\t')) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)

    rows, phones = [], []
    active = False
    name = fallback = ''
    for line in lines:
        if line.upper() == 'BEGIN:VCARD':
            if active:
                raise ValueError('VCF tidak lengkap: END:VCARD tidak ditemukan.')
            active, name, fallback, phones = True, '', '', []
            continue
        if line.upper() == 'END:VCARD':
            if active:
                rows.extend((phone, name or fallback) for phone in phones)
            active = False
            continue
        if not active or ':' not in line:
            continue
        header, value = line.split(':', 1)
        prop = header.split(';', 1)[0].rsplit('.', 1)[-1].upper()
        if prop not in ('FN', 'N', 'TEL'):
            continue
        if 'ENCODING=QUOTED-PRINTABLE' in header.upper():
            charset = re.search(r'CHARSET="?([^;"\s]+)', header, re.I)
            encoding = charset[1] if charset else 'utf-8'
            try:
                value = quopri.decodestring(value.encode('utf-8')).decode(encoding)
            except (LookupError, UnicodeError) as exc:
                raise ValueError('Encoding nama kontak tidak dapat dibaca.') from exc
        if prop == 'N':
            # Split structured N fields while keeping escaped semicolons intact.
            parts = re.findall(r'((?:\\.|[^;\\])*)(?:;|$)', value)
            fallback = ' '.join(_unescape(p).strip() for p in parts if p.strip())
        elif prop == 'FN':
            name = _unescape(value).strip()
        else:
            phone = _unescape(value).strip()
            if phone.lower().startswith('tel:'):
                phone = phone[4:]
            # Keep country prefixes, leading zeros and extensions as supplied.
            phone = ' '.join(phone.split())
            if phone:
                phones.append(phone)
    if active:
        raise ValueError('VCF tidak lengkap: END:VCARD tidak ditemukan.')
    return rows


def read_vcf(path):
    with open(path, 'rb') as source:
        raw = source.read()
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    return parse_vcf_text(raw.decode(encoding))


def format_txt_row(row, include_name=False):
    phone, name = (' '.join(value.split()) for value in row)
    return f'{phone} {name}' if include_name and name else phone


def _parse_split_sizes(total, per_file):
    if isinstance(per_file, int) and not isinstance(per_file, bool):
        if per_file <= 0:
            raise ValueError('Nomor per TXT harus angka positif.')
        return [min(per_file, total - i) for i in range(0, total, per_file)]
    if isinstance(per_file, str) and per_file.strip():
        raw = per_file.strip()
        if ',' in raw:
            parts = [p.strip() for p in raw.split(',')]
            if any(not p for p in parts):
                raise ValueError('Nomor per TXT harus angka positif.')
            try:
                custom = [int(p) for p in parts]
            except ValueError:
                raise ValueError('Nomor per TXT harus angka positif.') from None
            if any(c <= 0 for c in custom):
                raise ValueError('Nomor per TXT harus angka positif.')
            chunks, rem = [], total
            for c in custom:
                if rem <= 0:
                    break
                take = min(c, rem)
                chunks.append(take)
                rem -= take
            if rem > 0:
                chunks.append(rem)
            return chunks
        try:
            val = int(raw)
        except ValueError:
            raise ValueError('Nomor per TXT harus angka positif.') from None
        if val <= 0:
            raise ValueError('Nomor per TXT harus angka positif.')
        return [min(val, total - i) for i in range(0, total, val)]
    if isinstance(per_file, (list, tuple)) and per_file:
        if any(not isinstance(c, int) or isinstance(c, bool) or c <= 0 for c in per_file):
            raise ValueError('Nomor per TXT harus angka positif.')
        chunks, rem = [], total
        for c in per_file:
            if rem <= 0:
                break
            take = min(c, rem)
            chunks.append(take)
            rem -= take
        if rem > 0:
            chunks.append(rem)
        return chunks
    raise ValueError('Nomor per TXT harus angka positif.')


def plan_txt_files(sources, mode='combined', per_file=None, file_name='', rename_names=None):
    """Plan (filename stem, rows) outputs before any files are created."""
    if mode not in ('combined', 'split', 'source'):
        raise ValueError('Mode keluaran TXT tidak valid.')
    if mode == 'split':
        _parse_split_sizes(1, per_file)
    if mode == 'source':
        chunks = [(stem, rows) for stem, rows in sources if rows]
    else:
        rows = [row for _, contacts in sources for row in contacts]
        if not rows:
            chunks = []
        elif mode == 'split':
            sizes = _parse_split_sizes(len(rows), per_file)
            chunks = []
            idx = 0
            for sz in sizes:
                chunks.append(('', rows[idx:idx + sz]))
                idx += sz
        else:
            chunks = [('', rows)]
    if not chunks:
        raise ValueError('Tidak ada nomor telepon dalam input VCF.')
    planned = []
    for i, (source_stem, rows) in enumerate(chunks):
        if rename_names and i < len(rename_names):
            stem = rename_names[i]
        elif file_name:
            stem = file_name if len(chunks) == 1 else f'{file_name}-{i + 1}'
        else:
            stem = source_stem or ('contacts' if len(chunks) == 1 else f'Z{i + 1}')
        validate_txt_stem(stem)
        planned.append((stem, rows))
    return planned


def validate_txt_stem(stem):
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    reserved.update(f'{prefix}{n}' for prefix in ('COM', 'LPT') for n in '123456789¹²³')
    if (not stem or stem.endswith(('.', ' '))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', stem)
            or stem.split('.')[0].upper() in reserved):
        raise ValueError(f'Nama file TXT tidak valid: {stem!r}. Isi nama tanpa ekstensi atau karakter <>:"/\\|?*.')


def write_txt_files(plan, output_folder, include_name=False, progress=None):
    for stem, _ in plan:
        validate_txt_stem(stem)
    os.makedirs(output_folder, exist_ok=True)
    written = []
    for stem, rows in plan:
        suffix = 0
        while True:
            final_stem = f'{stem}_{suffix}' if suffix else stem
            path = os.path.join(output_folder, final_stem + '.txt')
            try:
                target = open(path, 'x', encoding='utf-8', newline='')
                break
            except FileExistsError:
                suffix += 1
        with target:
            for row in rows:
                target.write(format_txt_row(row, include_name) + '\r\n')
        written.append(path)
        if progress:
            progress(path, len(rows), len(written) / len(plan))
    return written
