"""
VCF Tools Pro — Desktop Application
Combines: admincuy.py, cvcobabaru.py, changename.py
Features: Drag & Drop, Copy-Paste, Integrated Rename
"""

import os
import re
import sys
import json
import time
import shutil
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import phonenumbers
from phonenumbers import geocoder
from vcf_txt_tools import read_vcf, parse_vcf_text, format_txt_row, plan_txt_files, write_txt_files, validate_txt_stem
from xlsx_tools import parse_number_lines, read_number_txt, write_numbers_xlsx

# Drag-and-drop support
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ============================================================
#  Shared Utility Functions
# ============================================================

def clean_phone_number(phone):
    """Normalize phone numbers:
    - Removes whitespace, dashes (-/–/—), dots, parentheses.
    - Converts Indonesian local prefixes '08...' (e.g. 0821xxx) -> '628...'.
    - Handles variants like '+08...', '6208...', '+6208...', '+628...'.
    """
    if not phone:
        return ''
    s = str(phone).strip()
    s = re.sub(r'[\s\-–—().]+', '', s)
    if not s:
        return ''

    # Handle +08... -> 628...
    if re.match(r'^\+08\d+', s):
        s = '628' + s[3:]
    # Handle +6208... -> 628... or 6208... -> 628...
    elif re.match(r'^\+?6208\d+', s):
        digits = s.lstrip('+')
        s = '628' + digits[4:]
    # Handle 08... -> 628... (e.g. 0821xxx -> 62821xxx)
    elif re.match(r'^08\d+', s):
        s = '628' + s[2:]
    # Normalize +628... -> 628... for uniform representation
    elif re.match(r'^\+628\d+', s):
        s = s[1:]

    return s


def is_valid_phone_number(phone_number):
    try:
        phone_number = clean_phone_number(phone_number)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        phone_obj = phonenumbers.parse(phone_number, None)
        return phonenumbers.is_valid_number(phone_obj)
    except phonenumbers.NumberParseException:
        return False


def detect_country(phone_number):
    try:
        phone_number = clean_phone_number(phone_number)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        phone_obj = phonenumbers.parse(phone_number, None)
        country = geocoder.description_for_number(phone_obj, "en")
        return country if country else "Unknown"
    except phonenumbers.NumberParseException:
        return "Unknown"


def format_phone_number(phone_number):
    try:
        phone_number = clean_phone_number(phone_number)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        phone_obj = phonenumbers.parse(phone_number, None)
        return phonenumbers.format_number(
            phone_obj, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
    except phonenumbers.NumberParseException:
        return phone_number


def escape_vcard_text(value):
    """Escape text without allowing names to create extra vCard properties."""
    return (value.replace('\\', '\\\\').replace('\r\n', '\n')
            .replace('\r', '\n').replace('\n', '\\n')
            .replace(';', '\\;').replace(',', '\\,'))


def fold_vcard_line(line):
    """Fold at 75 UTF-8 bytes without splitting a multibyte character."""
    parts = []
    current = ''
    size = 0
    for char in line:
        char_size = len(char.encode('utf-8'))
        if size + char_size > 75:
            parts.append(current)
            current, size = ' ', 1
        current += char
        size += char_size
    parts.append(current)
    return '\r\n'.join(parts)


def build_vcard(name, phone_number):
    """Compact vCard 3.0: retain names, cell numbers and validation status."""
    phone_number = clean_phone_number(phone_number)
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    valid = is_valid_phone_number(phone_number)
    escaped_name = escape_vcard_text(name)
    # N, FN and VERSION are mandatory in vCard 3.0 (RFC 2426).
    # Trailing empty N components are optional. Country/status NOTES are not
    # needed to import a contact; invalid counts remain available in the log.
    lines = [
        'BEGIN:VCARD', 'VERSION:3.0',
        f'N:{escaped_name}', f'FN:{escaped_name}',
        f'TEL;TYPE=CELL:{escape_vcard_text(phone_number)}', 'END:VCARD',
    ]
    return '\r\n'.join(fold_vcard_line(line) for line in lines) + '\r\n', valid


class SyncedNames:
    """Link Tk name variables while enabled, using the last edited field."""

    def __init__(self, enabled, *variables):
        self.enabled = enabled
        self.variables = variables
        self.last = variables[0]
        self.updating = False
        for var in variables:
            var.trace_add('write', lambda *_, source=var: self._changed(source))
        enabled.trace_add('write', self._toggled)

    def _changed(self, source):
        if self.updating:
            return
        self.last = source
        if self.enabled.get():
            self.updating = True
            try:
                for var in self.variables:
                    if var is not source and var.get() != source.get():
                        var.set(source.get())
            finally:
                self.updating = False

    def _toggled(self, *_):
        if self.enabled.get():
            source = self.last
            if not source.get().strip():
                source = next((v for v in self.variables if v.get().strip()), source)
            self._changed(source)


_PHONE_CHARS_RE = re.compile(r'^\+?[\d\s().-]+$')


def _digit_count(text):
    return len(re.sub(r'\D', '', text))


def _is_phone_candidate(text, min_digits=3):
    text = text.strip()
    if not text or re.search(r'\s+[-–—]\s+', text):
        return False
    return bool(_PHONE_CHARS_RE.match(text) and _digit_count(text) >= min_digits)


def parse_contact_line(line):
    """Extract (phone, name) from 'Nama - Nomor', 'Nomor - Nama', 'Nomor Nama', or plain number."""
    line = line.strip()
    if not line:
        return '', ''

    # 1. Explicit delimiters: ' - ' (with spaces), ':', '\t', ';', '|', ','
    for sep_pattern in (r'\s+[-–—]\s+', r'\s*[:\t;|,]\s*'):
        parts_all = re.split(sep_pattern, line)
        if len(parts_all) >= 2:
            # Try splitting at first delimiter and last delimiter (handles names containing ' - ')
            candidates = [
                (parts_all[0].strip(), ' - '.join(parts_all[1:]).strip()),
                (' - '.join(parts_all[:-1]).strip(), parts_all[-1].strip()),
            ]
            for left, right in candidates:
                left_is_phone = _is_phone_candidate(left, 3)
                right_is_phone = _is_phone_candidate(right, 3)
                if right_is_phone and not left_is_phone:
                    return right, left
                if left_is_phone and not right_is_phone:
                    return left, right
                if left_is_phone and right_is_phone:
                    if _digit_count(right) >= _digit_count(left):
                        return right, left
                    return left, right

    # 2. Pure phone number (e.g. '+62 812-3456-7890', '081234567890', '123')
    if _is_phone_candidate(line, 1):
        return line, ''

    # 3. Tight dash separator without spaces, e.g. 'Budi-081234567890' or '081234567890-Budi'
    m = re.match(r'^(.+?)\s*[-–—]\s*(\+?\d[\d\s().-]{4,})$', line)
    if m and _is_phone_candidate(m.group(2), 5):
        return m.group(2).strip(), m.group(1).strip()

    m = re.match(r'^(\+?\d[\d\s().-]{4,}?)\s*[-–—]\s*(.+)$', line)
    if m and _is_phone_candidate(m.group(1), 5):
        return m.group(1).strip(), m.group(2).strip()

    # 4. Space-separated: 'Nomor Nama' (e.g. '+6281234567890 Budi 01') or 'Nama Nomor' ('Budi 081234567890')
    m = re.match(r'^(\+?\d[\d().-]{4,})\s+(.+)$', line)
    if m and _is_phone_candidate(m.group(1), 5):
        return m.group(1).strip(), m.group(2).strip()

    m = re.match(r'^(.+?)\s+(\+?\d[\d\s().-]{4,})$', line)
    if m and _is_phone_candidate(m.group(2), 5):
        return m.group(2).strip(), m.group(1).strip()

    # Fallback: first token as phone, rest as name
    tokens = line.split(maxsplit=1)
    return tokens[0].strip(), (tokens[1].strip() if len(tokens) > 1 else '')


def format_name_phone(base_name, phone):
    """Combine base contact name from program input with phone number from TXT/paste without spaces around '-'."""
    base = base_name.strip().rstrip('-–—').strip()
    phone_clean = phone.strip()
    if not base:
        return phone_clean
    return f'{base}-{phone_clean}'


def parse_chunk_sizes(total, per_spec):
    """Return a list of contact counts per output VCF file.

    per_spec can be:
    - None or '': all contacts in a single file ([total])
    - int: fixed maximum contacts per file (e.g. 1000 -> [1000, 1000, ...])
    - str: single integer ('1000') or comma-separated custom sizes ('2000,2000,1000')
    - list/tuple of ints: custom sizes ([2000, 2000, 1000])
    """
    if isinstance(per_spec, (list, tuple)):
        custom = []
        for item in per_spec:
            if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
                raise ValueError('Setiap pembagian kontak/file harus angka positif.')
            custom.append(item)
        if not custom:
            raise ValueError('Kontak/file harus angka positif.')
        is_custom = True
    elif isinstance(per_spec, int) and not isinstance(per_spec, bool):
        if per_spec <= 0:
            raise ValueError('Kontak/file harus angka positif.')
        custom = [per_spec]
        is_custom = False
    elif per_spec is None or (isinstance(per_spec, str) and not per_spec.strip()):
        return [total] if total > 0 else []
    elif isinstance(per_spec, str):
        raw = per_spec.strip()
        if ',' in raw:
            parts = [p.strip() for p in raw.split(',')]
            if any(not p for p in parts):
                raise ValueError('Format pembagian custom tidak valid (contoh: 2000,2000,1000).')
            custom = []
            for p in parts:
                try:
                    val = int(p)
                except ValueError:
                    raise ValueError('Format pembagian custom harus angka positif dipisah koma (contoh: 2000,2000,1000).') from None
                if val <= 0:
                    raise ValueError('Setiap pembagian kontak/file harus angka positif.')
                custom.append(val)
            is_custom = True
        else:
            try:
                val = int(raw)
            except ValueError:
                raise ValueError('Kontak/file harus angka positif atau dipisah koma (contoh: 2000,2000,1000).') from None
            if val <= 0:
                raise ValueError('Kontak/file harus angka positif.')
            custom = [val]
            is_custom = False
    else:
        raise ValueError('Kontak/file harus angka positif.')

    if total <= 0:
        return []

    if not is_custom:
        size = custom[0]
        return [min(size, total - i) for i in range(0, total, size)]

    chunks = []
    remaining = total
    for size in custom:
        if remaining <= 0:
            break
        take = min(size, remaining)
        chunks.append(take)
        remaining -= take
    if remaining > 0:
        chunks.append(remaining)
    return chunks


def validate_file_stem(name):
    """Reject invalid Windows filenames before creating any output."""
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    reserved.update(f'{prefix}{n}' for prefix in ('COM', 'LPT')
                    for n in '123456789¹²³')
    if (not name or name.endswith(('.', ' '))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.split('.')[0].upper() in reserved):
        raise ValueError(f'Nama file tidak valid: {name!r}. Gunakan nama tanpa ekstensi atau karakter <>:"/\\|?*.')


def bulk_file_stems(total, per_file, file_name='', rename_names=None):
    chunks = parse_chunk_sizes(total, per_file)
    count = len(chunks)
    stems = []
    for i in range(count):
        if rename_names and i < len(rename_names):
            stem = rename_names[i]
        elif file_name:
            stem = file_name if count == 1 else f'{file_name}-{i + 1}'
        else:
            stem = f'Z{i + 1}'
        validate_file_stem(stem)
        stems.append(stem)
    return stems


CACHE_TTL_SECONDS = 30 * 60  # 30 minutes


def split_bulk_paths(value):
    """Split the Bulk TXT path field ('a.txt; b.txt') into a list of paths."""
    return [p.strip().strip('"') for p in (value or '').split(';') if p.strip().strip('"')]


def read_contact_lines(path):
    """Read non-empty, stripped lines from a TXT file (BOM tolerant)."""
    with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
        return [l.strip() for l in f if l.strip()]


def build_extra_vcards(text, base_name, start_index=1):
    """Build vCards for extra Admin/Navy numbers pasted one per line.

    Each line may be a plain number or 'Nama - Nomor'. Lines without a name use
    '<base_name> <start_index:03d>', ... Returns (vcf_text, count, invalid).
    """
    base = (base_name or '').strip()
    out = []
    invalid = 0
    seq = start_index - 1
    for raw in (text or '').splitlines():
        phone, name = parse_contact_line(raw)
        if not phone:
            continue
        phone = clean_phone_number(phone)
        seq += 1
        if not name:
            name = f"{base} {seq:03d}" if base else phone
        card, valid = build_vcard(name, phone)
        out.append(card)
        if not valid:
            invalid += 1
    return ''.join(out), len(out), invalid


def get_admin_tag(base_tag, file_index):
    """Generate sequential tag from a base code (e.g. 'A1' -> 'A1', 'A2', 'A3')."""
    base = (base_tag or "").strip()
    if not base:
        return str(file_index + 1)
    m = re.match(r'^(.*?)(\d+)$', base)
    if m:
        prefix_str = m.group(1)
        start_num = int(m.group(2))
        num_digits = len(m.group(2))
        curr_num = start_num + file_index
        curr_num_str = str(curr_num).zfill(num_digits)
        return f"{prefix_str}{curr_num_str}"
    else:
        return f"{base}{file_index + 1}"


def get_cache_file():
    """Return path to the 30-minute session cache file in the script directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, ".vcf_tools_cache.json")


def get_output_folder():
    """Always output to vcf_output in the script directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(script_dir, "vcf_output")
    os.makedirs(out, exist_ok=True)
    return out


# ============================================================
#  Color Palette
# ============================================================

C = {
    "bg":             "#0c0c18",
    "bg_card":        "#14142a",
    "bg_card_hover":  "#1c1c38",
    "accent":         "#7c6cff",
    "accent_hover":   "#9488ff",
    "accent_dim":     "#3d3570",
    "success":        "#00d68f",
    "success_hover":  "#00b878",
    "warning":        "#ffaa00",
    "error":          "#ff6b6b",
    "text":           "#eaeaff",
    "text2":          "#7878a0",
    "border":         "#252548",
    "input":          "#0e0e1e",
    "sidebar":        "#100f24",
    "sidebar_active": "#1e1d40",
    "drop_zone":      "#181838",
    "drop_zone_hl":   "#252550",
}




# ============================================================
#  Main Application
# ============================================================

class VCFToolsApp(ctk.CTk, TkinterDnD.DnDWrapper if HAS_DND else object):
    def __init__(self, cache_file=None, load_cache=True):
        super().__init__()
        if HAS_DND:
            self.TkdndVersion = TkinterDnD._require(self)

        self._cache_file = cache_file or get_cache_file()
        self._active_frame = "bulk"

        self.title("VCF Tools Pro")
        self.geometry("1100x750")
        self.minsize(1000, 680)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=C["bg"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._frames = {}
        self._build_admin_frame()
        self._build_bulk_frame()
        self._build_txt_frame()
        self._build_xlsx_frame()
        self._build_rename_frame()
        self._show_frame("bulk")

        if load_cache:
            self._load_session_cache()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Save session cache (valid for 30 minutes) before closing the window."""
        try:
            self._save_session_cache()
        except Exception:
            pass
        self.destroy()

    def _collect_session_state(self, now=None):
        """Collect current UI state across all tabs for 30-minute session caching."""
        return {
            "saved_at": time.time() if now is None else float(now),
            "active_frame": getattr(self, "_active_frame", "bulk"),
            # Bulk VCF Converter
            "bulk_tab": self.bulk_tab.get(),
            "bulk_file_var": self.bulk_file_var.get(),
            "bulk_multi_separate": self.bulk_multi_separate.get(),
            "bulk_paste": self.bulk_paste_box.get("1.0", "end-1c"),
            "bulk_name": self.bulk_name.get(),
            "bulk_no_name": self.bulk_no_name.get(),
            "bulk_name_phone": self.bulk_name_phone.get(),
            "bulk_per": self.bulk_per.get(),
            "bulk_start": self.bulk_start.get(),
            "bulk_digit": self.bulk_digit.get(),
            "bulk_filename": self.bulk_filename.get(),
            "bulk_sync_names": self.bulk_sync_names.get(),
            "bulk_rename_on": self.bulk_rename_on.get(),
            "bulk_rename_use_txt": self.bulk_rename_use_txt.get(),
            "rename_tab": self._rename_tab.get(),
            "bulk_rename_file_var": self.bulk_rename_file_var.get(),
            "bulk_rename_paste": self.bulk_rename_paste.get("1.0", "end-1c"),
            "ren_gen_prefix": self.ren_gen_prefix.get(),
            "ren_gen_start": self.ren_gen_start_var.get(),
            "ren_gen_end": self.ren_gen_end.get(),
            "ren_gen_no_space": self.ren_gen_no_space.get(),
            # VCF ke TXT
            "txt_tab": self.txt_tab.get(),
            "txt_paths": list(self._txt_paths),
            "txt_paste": self.txt_paste.get("1.0", "end-1c"),
            "txt_include_name": self.txt_include_name.get(),
            "txt_mode": self.txt_mode.get(),
            "txt_per": self.txt_per.get(),
            "txt_filename": self.txt_filename.get(),
            "txt_rename_on": self.txt_rename_on.get(),
            "txt_rename_tab": self.txt_rename_tab.get(),
            "txt_rename_paste": self.txt_rename_paste.get("1.0", "end-1c"),
            "txt_gen_prefix": self.txt_gen_prefix.get(),
            "txt_gen_start": self.txt_gen_start.get(),
            "txt_gen_end": self.txt_gen_end.get(),
            "txt_gen_no_space": self.txt_gen_no_space.get(),
            # TXT ke XLSX
            "xlsx_tab": self.xlsx_tab.get(),
            "xlsx_file": self.xlsx_file.get(),
            "xlsx_paste": self.xlsx_paste.get("1.0", "end-1c"),
            "xlsx_filename": self.xlsx_filename.get(),
            # Admin VCF Creator
            "admin_tab": self.admin_tab.get(),
            "admin_file_var": self.admin_file_var.get(),
            "admin_paste": self.admin_paste_box.get("1.0", "end-1c"),
            "admin_extra_admin": self.admin_extra_admin_box.get("1.0", "end-1c"),
            "admin_extra_navy": self.admin_extra_navy_box.get("1.0", "end-1c"),
            # Rename VCF Files
            "ren_src_var": self.ren_src_var.get(),
            "ren_name_tab": self.ren_name_tab.get(),
            "ren_name_file_var": self.ren_name_file_var.get(),
            "ren_name_paste": self.ren_name_paste.get("1.0", "end-1c"),
            "rn_pref": self._rn_pref.get(),
            "rn_start": self._rn_start.get(),
            "rn_end": self._rn_end.get(),
            "rn_gen_no_space": self.rn_gen_no_space.get(),
            "ren_move": self.ren_move.get(),
        }

    def _save_session_cache(self, now=None):
        """Write current UI state to disk cache."""
        state = self._collect_session_state(now=now)
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return state

    def _load_session_cache(self, now=None, ttl_seconds=CACHE_TTL_SECONDS):
        """Restore UI state if cache exists and was saved within ttl_seconds (default 30 min)."""
        if not self._cache_file or not os.path.isfile(self._cache_file):
            return False
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_at = float(data.get("saved_at", 0))
        except Exception:
            try:
                os.remove(self._cache_file)
            except OSError:
                pass
            return False

        current_time = time.time() if now is None else float(now)
        if current_time - saved_at > ttl_seconds:
            try:
                os.remove(self._cache_file)
            except OSError:
                pass
            return False

        self._apply_session_state(data)
        return True

    def _apply_session_state(self, data):
        """Apply cached dictionary values back to UI controls."""
        def _set_textbox(tb, val):
            if val is not None:
                tb.delete("1.0", "end")
                if val:
                    tb.insert("1.0", str(val))

        def _set_entry(entry, val):
            if val is not None:
                entry.delete(0, "end")
                entry.insert(0, str(val))

        def _set_tab(tabview, val):
            if val:
                try:
                    tabview.set(val)
                except Exception:
                    pass

        # Temporarily disable sync so bulk_name and bulk_filename restore independently
        self.bulk_sync_names.set(False)
        if "bulk_name" in data:
            self.bulk_name.set(str(data["bulk_name"]))
        if "bulk_filename" in data:
            self.bulk_filename.set(str(data["bulk_filename"]))
        if "bulk_start" in data:
            self.bulk_start.set(str(data["bulk_start"]))
        if "bulk_digit" in data:
            try:
                self.bulk_digit.set(int(data["bulk_digit"]))
            except (TypeError, ValueError):
                pass
        if "bulk_no_name" in data:
            self.bulk_no_name.set(bool(data["bulk_no_name"]))
        if "bulk_name_phone" in data:
            self.bulk_name_phone.set(bool(data["bulk_name_phone"]))
        if "bulk_sync_names" in data:
            self.bulk_sync_names.set(bool(data["bulk_sync_names"]))

        _set_tab(self.bulk_tab, data.get("bulk_tab"))
        _set_textbox(self.bulk_paste_box, data.get("bulk_paste"))
        if "bulk_file_var" in data:
            self.bulk_file_var.set(str(data["bulk_file_var"]))
            if self._bulk_paths():
                self._bulk_show_file_preview()
        if "bulk_multi_separate" in data:
            self.bulk_multi_separate.set(bool(data["bulk_multi_separate"]))

        _set_tab(self._rename_tab, data.get("rename_tab"))
        if "bulk_rename_file_var" in data:
            self.bulk_rename_file_var.set(str(data["bulk_rename_file_var"]))
        _set_textbox(self.bulk_rename_paste, data.get("bulk_rename_paste"))
        _set_entry(self.ren_gen_prefix, data.get("ren_gen_prefix"))
        if "ren_gen_start" in data:
            self.ren_gen_start_var.set(str(data["ren_gen_start"]))
        _set_entry(self.ren_gen_end, data.get("ren_gen_end"))
        if "ren_gen_no_space" in data:
            self.ren_gen_no_space.set(bool(data["ren_gen_no_space"]))
        if "bulk_rename_use_txt" in data:
            self.bulk_rename_use_txt.set(bool(data["bulk_rename_use_txt"]))
        if "bulk_rename_on" in data:
            self.bulk_rename_on.set(bool(data["bulk_rename_on"]))
        self._toggle_rename_input()

        # Restore bulk_per after _toggle_rename_input so custom or user value is kept
        if "bulk_per" in data:
            self.bulk_per.set(str(data["bulk_per"]))

        self._update_name_controls_state()
        self._update_prediction()
        self._update_bulk_preview()

        # VCF ke TXT
        _set_tab(self.txt_tab, data.get("txt_tab"))
        if "txt_paths" in data and isinstance(data["txt_paths"], list):
            self._txt_paths = [str(p) for p in data["txt_paths"] if isinstance(p, str) and os.path.isfile(p)]
            self._txt_update_file_list()
        _set_textbox(self.txt_paste, data.get("txt_paste"))
        if "txt_include_name" in data:
            self.txt_include_name.set(bool(data["txt_include_name"]))
        if "txt_mode" in data:
            self.txt_mode.set(str(data["txt_mode"]))
            self._txt_mode_changed()
        if "txt_per" in data:
            self.txt_per.set(str(data["txt_per"]))
        if "txt_filename" in data:
            self.txt_filename.set(str(data["txt_filename"]))
        if "txt_rename_on" in data:
            self.txt_rename_on.set(bool(data["txt_rename_on"]))
        _set_tab(self.txt_rename_tab, data.get("txt_rename_tab"))
        _set_textbox(self.txt_rename_paste, data.get("txt_rename_paste"))
        if "txt_gen_prefix" in data:
            self.txt_gen_prefix.set(str(data["txt_gen_prefix"]))
        if "txt_gen_start" in data:
            self.txt_gen_start.set(str(data["txt_gen_start"]))
        if "txt_gen_end" in data:
            self.txt_gen_end.set(str(data["txt_gen_end"]))
        if "txt_gen_no_space" in data:
            self.txt_gen_no_space.set(bool(data["txt_gen_no_space"]))
        self._txt_update_generator_preview()

        # TXT ke XLSX
        _set_tab(self.xlsx_tab, data.get("xlsx_tab"))
        if "xlsx_file" in data:
            self.xlsx_file.set(str(data["xlsx_file"]))
        _set_textbox(self.xlsx_paste, data.get("xlsx_paste"))
        if "xlsx_filename" in data:
            self.xlsx_filename.set(str(data["xlsx_filename"]))

        # Admin VCF Creator
        _set_tab(self.admin_tab, data.get("admin_tab"))
        if "admin_file_var" in data:
            self.admin_file_var.set(str(data["admin_file_var"]))
        _set_textbox(self.admin_paste_box, data.get("admin_paste"))
        _set_textbox(self.admin_extra_admin_box, data.get("admin_extra_admin"))
        _set_textbox(self.admin_extra_navy_box, data.get("admin_extra_navy"))

        # Rename VCF Files
        if "ren_src_var" in data:
            self.ren_src_var.set(str(data["ren_src_var"]))
        _set_tab(self.ren_name_tab, data.get("ren_name_tab"))
        if "ren_name_file_var" in data:
            self.ren_name_file_var.set(str(data["ren_name_file_var"]))
        _set_textbox(self.ren_name_paste, data.get("ren_name_paste"))
        _set_entry(self._rn_pref, data.get("rn_pref"))
        _set_entry(self._rn_start, data.get("rn_start"))
        _set_entry(self._rn_end, data.get("rn_end"))
        if "rn_gen_no_space" in data:
            self.rn_gen_no_space.set(bool(data["rn_gen_no_space"]))
        if "ren_move" in data:
            self.ren_move.set(bool(data["ren_move"]))

        active = data.get("active_frame")
        if active in self._frames:
            self._show_frame(active)

    # ───────────────────── SIDEBAR ─────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=C["sidebar"],
                          border_width=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(20, weight=1)

        # Logo
        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.grid(row=0, column=0, padx=20, pady=(26, 6), sticky="ew")
        ctk.CTkLabel(logo, text="⚡", font=ctk.CTkFont(size=30),
                     text_color=C["accent"]).pack(side="left", padx=(0, 8))
        tframe = ctk.CTkFrame(logo, fg_color="transparent")
        tframe.pack(side="left")
        ctk.CTkLabel(tframe, text="VCF Tools",
                     font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(tframe, text="Pro Edition",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=C["accent"]).pack(anchor="w")

        ctk.CTkFrame(sb, height=1, fg_color=C["border"]).grid(
            row=1, column=0, padx=16, pady=14, sticky="ew")

        ctk.CTkLabel(sb, text="  MENU", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=C["text2"], anchor="w").grid(
            row=2, column=0, padx=20, pady=(0, 4), sticky="ew")

        self._nav = {}
        nav_items = [
            ("bulk",   "📦  Bulk VCF Converter"),
            ("txt",    "📄  VCF ke TXT"),
            ("xlsx",   "📊  TXT ke XLSX"),
            ("admin",  "📋  Admin VCF Creator"),
            ("rename", "✏️  Rename VCF Files"),
        ]
        for i, (key, label) in enumerate(nav_items):
            btn = ctk.CTkButton(
                sb, text=label, font=ctk.CTkFont(size=13), anchor="w", height=42,
                corner_radius=10, fg_color="transparent",
                hover_color=C["sidebar_active"], text_color=C["text"],
                command=lambda k=key: self._show_frame(k),
            )
            btn.grid(row=3 + i, column=0, padx=12, pady=3, sticky="ew")
            self._nav[key] = btn

        # Cleanup
        ctk.CTkButton(
            sb, text="🧹  Bersihkan vcf_output", font=ctk.CTkFont(size=12, weight="bold"),
            height=38, corner_radius=10, fg_color=C["border"],
            hover_color=C["error"], text_color=C["text"],
            command=self._clean_output_folder
        ).grid(row=19, column=0, padx=12, pady=(0, 20), sticky="ew")

        # Footer
        ctk.CTkLabel(sb, text="v2.0  •  Made with 💜",
                     font=ctk.CTkFont(size=11), text_color=C["text2"]).grid(
            row=20, column=0, padx=20, pady=(0, 18), sticky="s")

    def _show_frame(self, name):
        self._active_frame = name
        for f in self._frames.values():
            f.grid_forget()
        self._frames[name].grid(row=0, column=1, sticky="nsew")
        for k, btn in self._nav.items():
            if k == name:
                btn.configure(fg_color=C["accent"], text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=C["text"])

    def _clean_output_folder(self):
        folder = get_output_folder()
        if not os.path.exists(folder):
            messagebox.showinfo("Info", "Folder vcf_output tidak ditemukan.")
            return
            
        vcfs = [f for f in os.listdir(folder) if f.endswith(".vcf")]
        if not vcfs:
            messagebox.showinfo("Info", "Tidak ada file VCF di folder vcf_output saat ini.")
            return
            
        ans = messagebox.askyesno("Konfirmasi", f"Apakah Anda yakin ingin menghapus {len(vcfs)} file VCF di folder vcf_output?\nTindakan ini tidak dapat dibatalkan.")
        if ans:
            count = 0
            for f in vcfs:
                try:
                    os.remove(os.path.join(folder, f))
                    count += 1
                except: pass
            messagebox.showinfo("Sukses", f"Berhasil menghapus {count} file VCF dari folder vcf_output.")

    # ───────────────────── HELPERS ─────────────────────

    def _card(self, parent, row, title, expand=False):
        card = ctk.CTkFrame(parent, fg_color=C["bg_card"], corner_radius=14,
                            border_width=1, border_color=C["border"])
        card.grid(row=row, column=0, padx=28, pady=(10, 4),
                  sticky="nsew" if expand else "new")
        if expand:
            parent.grid_rowconfigure(row, weight=1)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=C["text"]).pack(anchor="w", padx=16, pady=(14, 6))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        return inner

    def _make_log(self, parent):
        log = ctk.CTkTextbox(
            parent, corner_radius=10, fg_color=C["input"],
            border_color=C["border"], text_color=C["text2"],
            font=ctk.CTkFont(family="Consolas", size=11), state="disabled")
        return log

    def _log(self, widget, msg):
        def _do():
            widget.configure(state="normal")
            widget.insert("end", msg + "\n")
            widget.see("end")
            widget.configure(state="disabled")
        self.after(0, _do)

    def _browse_file(self, var, filetypes=None):
        if filetypes is None:
            filetypes = [("Text Files", "*.txt"), ("All Files", "*.*")]
        path = filedialog.askopenfilename(title="Pilih File", filetypes=filetypes)
        if path:
            var.set(path)

    def _enable_drop(self, widget, callback):
        """Enable file drag-and-drop on a widget using tkinterdnd2."""
        if not HAS_DND:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', callback)
        except Exception:
            pass

    def _parse_drop_path(self, event):
        """Extract first file path from a tkdnd drop event."""
        data = event.data.strip()
        if data.startswith('{') and data.endswith('}'):
            data = data[1:-1]
        return data

    # ──────────────────────────────────────────────────────────
    #  FEATURE 1 : BULK VCF CONVERTER  (from cvcobabaru.py)
    #  + integrated changename + copy-paste + drag-drop
    # ──────────────────────────────────────────────────────────

    def _build_bulk_frame(self):
        frame = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._frames["bulk"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        scroll_page = ctk.CTkScrollableFrame(
            frame, fg_color=C["bg"], corner_radius=0,
            scrollbar_button_color=C["accent_dim"],
            scrollbar_button_hover_color=C["accent"])
        scroll_page.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll_page.grid_columnconfigure(0, weight=1)
        
        self.bulk_scroll_page = scroll_page

        # Header
        hdr = ctk.CTkFrame(scroll_page, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=28, pady=(20, 2), sticky="ew")
        ctk.CTkLabel(hdr, text="Bulk VCF Converter",
                     font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Konversi TXT → VCF  •  Drag & Drop  •  Copy-Paste  •  Auto Rename",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(anchor="w", pady=(2, 0))

        # ── Input card: drag-drop zone + paste ──
        card_input = self._card(self.bulk_scroll_page, 1, "📥  Input Nomor — Pilih File / Drag & Drop / Paste Langsung")

        # Tabview for file vs paste
        self.bulk_tab = ctk.CTkTabview(card_input, fg_color=C["bg_card"],
                                       segmented_button_fg_color=C["accent_dim"],
                                       segmented_button_selected_color=C["accent"],
                                       segmented_button_unselected_color=C["border"],
                                       corner_radius=10, height=220)
        self.bulk_tab.pack(fill="x", padx=2, pady=(0, 4))
        tab_file = self.bulk_tab.add("📂 File / Drag & Drop")
        tab_paste = self.bulk_tab.add("📋 Paste Langsung")

        # --- Tab File ---
        self.bulk_file_var = ctk.StringVar()

        drop_zone = ctk.CTkFrame(tab_file, fg_color=C["drop_zone"], corner_radius=12,
                                  border_width=2, border_color=C["border"], height=90)
        drop_zone.pack(fill="x", padx=4, pady=4)
        drop_zone.pack_propagate(False)

        self._bulk_drop_label = ctk.CTkLabel(
            drop_zone,
            text="🗂️  Drag & drop satu atau BANYAK file TXT ke sini\natau klik Browse (bisa pilih banyak)",
            font=ctk.CTkFont(size=13), text_color=C["text2"], justify="center")
        self._bulk_drop_label.pack(expand=True)

        # Enable DnD on the drop zone
        self._enable_drop(drop_zone, self._bulk_on_drop)
        self._enable_drop(self._bulk_drop_label, self._bulk_on_drop)

        file_row = ctk.CTkFrame(tab_file, fg_color="transparent")
        file_row.pack(fill="x", padx=4, pady=(4, 2))
        ctk.CTkEntry(file_row, textvariable=self.bulk_file_var,
                     placeholder_text="Path file .txt … (banyak file dipisah ;)", height=38, corner_radius=10,
                     fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"]).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(file_row, text="Kosongkan", width=90, height=38, corner_radius=10,
                      fg_color=C["border"], hover_color=C["error"], text_color=C["text"],
                      command=self._bulk_clear_files).pack(side="right", padx=(6, 0))
        ctk.CTkButton(file_row, text="Browse", width=90, height=38, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=self._bulk_browse_and_preview).pack(side="right")

        self.bulk_multi_separate = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(tab_file, text="Banyak TXT: tiap TXT jadi VCF sendiri (nama file VCF = nama TXT). "
                                       "Matikan untuk menggabungkan semua TXT.",
                        variable=self.bulk_multi_separate, font=ctk.CTkFont(size=11),
                        text_color=C["text"], fg_color=C["accent"], hover_color=C["accent_hover"],
                        border_color=C["border"]).pack(anchor="w", padx=4, pady=(2, 0))
                      
        self.bulk_number_preview = ctk.CTkTextbox(
            tab_file, height=70, corner_radius=8,
            fg_color=C["input"], border_color=C["border"],
            text_color=C["text2"], font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled")
        self.bulk_number_preview.pack(fill="x", padx=4, pady=(2, 2))
        self.bulk_number_preview.pack_forget()

        # --- Tab Paste ---
        ctk.CTkLabel(tab_paste, text="Paste kontak di bawah (1 per baris — Nomor saja, Nama - Nomor, atau Nomor - Nama):",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(anchor="w", padx=4, pady=(4, 2))
        self.bulk_paste_box = ctk.CTkTextbox(
            tab_paste, height=100, corner_radius=10,
            fg_color=C["input"], border_color=C["border"],
            text_color=C["text"], font=ctk.CTkFont(family="Consolas", size=12))
        self.bulk_paste_box.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # ── Settings card ──
        card_set = self._card(self.bulk_scroll_page, 2, "⚙️  Pengaturan")
        sg = ctk.CTkFrame(card_set, fg_color="transparent")
        sg.pack(fill="x", padx=2)
        sg.grid_columnconfigure((1, 3), weight=1)

        # Row 0: name + per file
        ctk.CTkLabel(sg, text="Nama Kontak:", font=ctk.CTkFont(size=13),
                     text_color=C["text"]).grid(row=0, column=0, padx=(0, 8), pady=5, sticky="w")
        
        name_frame = ctk.CTkFrame(sg, fg_color="transparent")
        name_frame.grid(row=0, column=1, padx=(0, 16), pady=5, sticky="ew")
        
        self.bulk_name = ctk.StringVar(value="REY")
        self.bulk_name_entry = ctk.CTkEntry(name_frame, textvariable=self.bulk_name, height=36, corner_radius=10, width=110,
                     fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"])
        self.bulk_name_entry.pack(side="left")
        
        self.bulk_no_name = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(name_frame, text="Tanpa Nama", variable=self.bulk_no_name, 
                        font=ctk.CTkFont(size=12), text_color=C["text"], 
                        fg_color=C["accent"], hover_color=C["accent_hover"],
                        border_color=C["border"], command=self._toggle_no_name).pack(side="left", padx=(8, 4))

        self.bulk_name_phone = ctk.BooleanVar(value=False)
        self.bulk_use_input_name = self.bulk_name_phone
        self.bulk_name_phone_checkbox = ctk.CTkCheckBox(
            name_frame, text="Nama-Nomor", variable=self.bulk_name_phone,
            font=ctk.CTkFont(size=12), text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            border_color=C["border"], command=self._toggle_name_phone)
        self.bulk_name_phone_checkbox.pack(side="left", padx=4)

        ctk.CTkLabel(sg, text="Kontak/File (Opsional):", font=ctk.CTkFont(size=12),
                     text_color=C["text"]).grid(row=0, column=2, padx=(0, 8), pady=5, sticky="w")
        self.bulk_per = ctk.StringVar(value="")
        ctk.CTkEntry(sg, textvariable=self.bulk_per, height=36, corner_radius=10, width=140,
                     placeholder_text="Semua / 1000 / 2000,2000,1000", fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"]).grid(row=0, column=3, pady=5, sticky="ew")

        # Row 1: start number + digit format
        ctk.CTkLabel(sg, text="Nomor Awalan:", font=ctk.CTkFont(size=13),
                     text_color=C["text"]).grid(row=1, column=0, padx=(0, 8), pady=5, sticky="w")

        sn_frame = ctk.CTkFrame(sg, fg_color="transparent")
        sn_frame.grid(row=1, column=1, padx=(0, 16), pady=5, sticky="ew")
        self.bulk_start = ctk.StringVar(value="1")
        self.bulk_start_entry = ctk.CTkEntry(sn_frame, textvariable=self.bulk_start, height=36, corner_radius=10,
                     width=70, fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"])
        self.bulk_start_entry.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(sn_frame, text="(1→001, 50→050)",
                     font=ctk.CTkFont(size=11), text_color=C["text2"]).pack(side="left")

        ctk.CTkLabel(sg, text="Format Digit:", font=ctk.CTkFont(size=13),
                     text_color=C["text"]).grid(row=1, column=2, padx=(0, 8), pady=5, sticky="w")
        dig_frame = ctk.CTkFrame(sg, fg_color="transparent")
        dig_frame.grid(row=1, column=3, pady=5, sticky="ew")
        self.bulk_digit = ctk.IntVar(value=3)
        self.bulk_digit_radios = []
        for d in [2, 3, 4]:
            rb = ctk.CTkRadioButton(dig_frame, text=f"{d}", variable=self.bulk_digit, value=d,
                               font=ctk.CTkFont(size=12), text_color=C["text"],
                               fg_color=C["accent"], hover_color=C["accent_hover"],
                               border_color=C["border"], width=50)
            rb.pack(side="left", padx=(0, 8))
            self.bulk_digit_radios.append(rb)

        # Row 2: output name and bidirectional name synchronization
        self.bulk_filename = ctk.StringVar(value="")
        self.bulk_sync_names = ctk.BooleanVar(value=False)
        ctk.CTkLabel(sg, text="Nama File VCF:", font=ctk.CTkFont(size=13),
                     text_color=C["text"]).grid(row=2, column=0, padx=(0, 8), pady=5, sticky="w")
        ctk.CTkEntry(sg, textvariable=self.bulk_filename,
                     placeholder_text="Tanpa .vcf (kosong: Z1, Z2, ...)",
                     height=36, corner_radius=10, fg_color=C["input"],
                     border_color=C["border"], text_color=C["text"]).grid(
                         row=2, column=1, padx=(0, 16), pady=5, sticky="ew")
        self.bulk_sync_checkbox = ctk.CTkCheckBox(
            sg, text="Samakan nama file dan kontak", variable=self.bulk_sync_names,
            font=ctk.CTkFont(size=12), text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            border_color=C["border"], command=self._toggle_sync_names)
        self.bulk_sync_checkbox.grid(row=2, column=2, columnspan=2, pady=5, sticky="w")
        self._bulk_name_link = SyncedNames(
            self.bulk_sync_names, self.bulk_name, self.bulk_filename)

        # Rename integration
        ctk.CTkFrame(sg, height=1, fg_color=C["border"]).grid(
            row=3, column=0, columnspan=4, pady=8, sticky="ew")

        self.bulk_rename_on = ctk.BooleanVar(value=False)
        self.bulk_rename_use_txt = ctk.BooleanVar(value=False)
        
        ar_frame = ctk.CTkFrame(sg, fg_color="transparent")
        ar_frame.grid(row=4, column=0, columnspan=4, padx=0, pady=(0, 4), sticky="w")
        
        ctk.CTkCheckBox(
            ar_frame, text="  ✏️  Auto rename file VCF setelah generate",
            variable=self.bulk_rename_on, font=ctk.CTkFont(size=13),
            text_color=C["text"], fg_color=C["accent"], hover_color=C["accent_hover"],
            border_color=C["border"], command=self._toggle_rename_input,
        ).pack(side="left")
        
        ctk.CTkCheckBox(
            ar_frame, text="Samakan dengan nama file TXT input",
            variable=self.bulk_rename_use_txt, font=ctk.CTkFont(size=12),
            text_color=C["success"], fg_color=C["success"], hover_color=C["success_hover"],
            border_color=C["border"], command=self._toggle_rename_input,
        ).pack(side="left", padx=(20, 0))

        self._rename_input_frame = ctk.CTkFrame(sg, fg_color="transparent")
        self._rename_input_frame.grid(row=5, column=0, columnspan=4, pady=(0, 2), sticky="ew")

        # Rename names can come from paste or file
        self._rename_tab = ctk.CTkTabview(
            self._rename_input_frame, fg_color=C["bg_card"],
            segmented_button_fg_color=C["accent_dim"],
            segmented_button_selected_color=C["accent"],
            segmented_button_unselected_color=C["border"],
            corner_radius=10, height=110)

        rt_file = self._rename_tab.add("📂 File nama_baru.txt")
        rt_paste = self._rename_tab.add("📋 Paste Nama")
        rt_gen = self._rename_tab.add("✨ Generate List")

        self.bulk_rename_file_var = ctk.StringVar()
        rf_row = ctk.CTkFrame(rt_file, fg_color="transparent")
        rf_row.pack(fill="x", padx=4, pady=4)
        ctk.CTkEntry(rf_row, textvariable=self.bulk_rename_file_var,
                     placeholder_text="Path file nama_baru.txt …", height=34, corner_radius=10,
                     fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"]).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(rf_row, text="Browse", width=80, height=34, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=self._bulk_browse_rename_file).pack(side="right")

        # Enable DnD on rename file input
        self._enable_drop(rf_row, self._bulk_rename_on_drop)

        self.bulk_rename_paste = ctk.CTkTextbox(
            rt_paste, height=60, corner_radius=10,
            fg_color=C["input"], border_color=C["border"],
            text_color=C["text"], font=ctk.CTkFont(family="Consolas", size=12))
        self.bulk_rename_paste.pack(fill="both", expand=True, padx=4, pady=4)

        # Generate Tab UI
        gen_row = ctk.CTkFrame(rt_gen, fg_color="transparent")
        gen_row.pack(fill="x", padx=4, pady=8)
        ctk.CTkLabel(gen_row, text="Prefix:", font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left")
        self.ren_gen_prefix = ctk.CTkEntry(gen_row, placeholder_text="Cth: GRUP", width=80, height=30, fg_color=C["input"], border_color=C["border"])
        self.ren_gen_prefix.pack(side="left", padx=6)
        self.ren_gen_prefix.insert(0, "GRUP")
        
        ctk.CTkLabel(gen_row, text="Rentang:", font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left", padx=(10, 0))
        
        self.ren_gen_start_var = ctk.StringVar(value="1")
        self.ren_gen_start = ctk.CTkEntry(gen_row, textvariable=self.ren_gen_start_var, placeholder_text="1", width=40, height=30, fg_color=C["input"], border_color=C["border"])
        self.ren_gen_start.pack(side="left", padx=4)
        
        ctk.CTkLabel(gen_row, text="-", font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left")
        
        self.ren_gen_end = ctk.CTkEntry(gen_row, placeholder_text="5", width=40, height=30, fg_color=C["input"], border_color=C["border"])
        self.ren_gen_end.pack(side="left", padx=4)
        self.ren_gen_end.insert(0, "5")
        
        self.ren_gen_no_space = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(gen_row, text="Tanpa Spasi", variable=self.ren_gen_no_space, 
                        font=ctk.CTkFont(size=11), text_color=C["text"], 
                        fg_color=C["accent"], hover_color=C["accent_hover"],
                        border_color=C["border"], width=10).pack(side="left", padx=8)
        
        def _do_generate():
            try:
                s = int(self.ren_gen_start.get())
                e = int(self.ren_gen_end.get())
                pref = self.ren_gen_prefix.get().strip()
                nospace = self.ren_gen_no_space.get()
                lines = [f"{pref}{'' if nospace else ' '}{i}" for i in range(s, e+1)]
                self.bulk_rename_paste.delete("1.0", "end")
                self.bulk_rename_paste.insert("end", "\n".join(lines) + "\n")
                self._rename_tab.set("📋 Paste Nama")
                self._bulk_update_rename_info()
            except Exception as ex:
                messagebox.showwarning("Peringatan", "Pastikan rentang berupa angka yang valid.")
                
        ctk.CTkButton(gen_row, text="Generate", width=70, height=30, corner_radius=8, fg_color=C["accent"], hover_color=C["accent_hover"], command=_do_generate).pack(side="right", padx=(4, 0))

        self.ren_pred_label = ctk.CTkLabel(rt_gen, text="💡 Prediksi belum tersedia. Muat nomor kontak dulu.", font=ctk.CTkFont(size=11), text_color=C["success"])
        self.ren_pred_label.pack(anchor="w", padx=4, pady=0)

        self.bulk_rename_info = ctk.CTkLabel(self._rename_input_frame, text="", font=ctk.CTkFont(size=11), text_color=C["warning"], justify="left")
        self.bulk_rename_info.pack(anchor="w", padx=4, pady=(2,0))
        self.bulk_rename_preview = ctk.CTkLabel(self._rename_input_frame, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color=C["success"], justify="left")
        self.bulk_rename_preview.pack(anchor="w", padx=4, pady=(2,4))
        self._rename_input_frame.grid_remove()  # Hidden by default

        # Preview
        self.bulk_preview = ctk.CTkLabel(
            card_set, text="", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C["accent"])
        self.bulk_preview.pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(card_set,
                     text="Tips: Centang 'Nama-Nomor' agar nama kontak otomatis menggabungkan Nama Kontak di atas + Nomor Telepon dari TXT/Paste (contoh: REY-0812345). Isi Kontak/File dengan angka (cth: 1000) atau bagi custom dipisah koma (cth: 2000,2000,1000).",
                     wraplength=690, justify="left", font=ctk.CTkFont(size=11),
                     text_color=C["text2"]).pack(anchor="w", padx=8, pady=(4, 0))

        def _update_pred(*_):
            if hasattr(self, 'ren_pred_label'):
                cl = self._get_bulk_contacts_silent()
                if cl:
                    try:
                        per_str = self.bulk_per.get().strip()
                        chunks = parse_chunk_sizes(len(cl), per_str) if per_str else [len(cl)]
                        req = len(chunks)
                        if req > 0:
                            try: s_val = int(self.ren_gen_start.get())
                            except: s_val = 1
                            e_val = s_val + req - 1
                            self.ren_pred_label.configure(text=f"💡 Butuh {req} file (dari {len(cl)} kontak). Atur rentang: {s_val} - {e_val}")
                    except: pass
                    
        self._update_prediction = _update_pred
        self.bulk_per.trace_add("write", _update_pred)
        self.bulk_file_var.trace_add("write", _update_pred)
        self.ren_gen_start_var.trace_add("write", _update_pred)
        self.bulk_per.trace_add("write", lambda *_: self._bulk_update_rename_info() if self.bulk_rename_on.get() else None)

        def upd(*_):
            if self.bulk_no_name.get():
                self.bulk_preview.configure(text="📛 Preview Nama Kontak:  (Sesuai dengan Nomor Telepon Masing-masing)")
            else:
                try: s = int(self.bulk_start.get())
                except: s = 1
                d = self.bulk_digit.get()
                n = self.bulk_name.get() or "REY"
                contacts = self._get_bulk_contacts_silent() or []
                if self.bulk_sync_names.get():
                    names = self._get_rename_names() if self.bulk_rename_on.get() else None
                    try:
                        per_str = self.bulk_per.get().strip()
                        total_est = max(len(contacts), 1)
                        n = bulk_file_stems(total_est, per_str or total_est,
                                            self.bulk_filename.get().strip(), names)[0]
                    except ValueError:
                        n = self.bulk_filename.get().strip() or n
                if self.bulk_name_phone.get():
                    phones = [parse_contact_line(l)[0] for l in contacts[:3] if parse_contact_line(l)[0]]
                    if not phones:
                        phones = ["081234567890", "081234567891", "081234567892"]
                    ex = [format_name_phone(n, p) for p in phones[:3]]
                    self.bulk_preview.configure(
                        text=f"📛 Preview Nama Kontak (Nama-Nomor):  {'  →  '.join(ex)}  → …")
                else:
                    ex = [f"{n} {str(s+i).zfill(d)}" for i in range(3)]
                    self.bulk_preview.configure(text=f"📛 Preview Nama Kontak:  {ex[0]}  →  {ex[1]}  →  {ex[2]}  → …")
        for v in (self.bulk_start, self.bulk_name): v.trace_add("write", upd)
        self.bulk_digit.trace_add("write", upd)
        for v in (self.bulk_filename, self.bulk_sync_names, self.bulk_name_phone, self.bulk_per,
                  self.bulk_rename_on, self.bulk_rename_use_txt, self.bulk_file_var,
                  self.bulk_rename_file_var):
            v.trace_add("write", upd)
        self._update_bulk_preview = upd
        self.bulk_rename_paste.bind('<KeyRelease>', lambda _: upd())
        self.bulk_paste_box.bind('<KeyRelease>', lambda _: (_update_pred(), upd()))
        self._rename_tab.configure(command=self._bulk_update_rename_info)
        self.bulk_tab.configure(command=lambda: (_update_pred(), upd()))
        upd()

        # ── Action row ──
        act = ctk.CTkFrame(card_set, fg_color="transparent")
        act.pack(fill="x", padx=2, pady=(8, 0))

        ctk.CTkButton(act, text="▶️  Review & Konversi ke VCF", height=42, corner_radius=10,
                      fg_color=C["success"], hover_color=C["success_hover"],
                      text_color="#000", font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._bulk_go).pack(side="left", padx=(0, 10))

        self.bulk_prog = ctk.CTkProgressBar(act, corner_radius=8, height=12,
                                             fg_color=C["input"], progress_color=C["accent"])
        self.bulk_prog.pack(side="left", fill="x", expand=True, pady=4)
        self.bulk_prog.set(0)

        # ── Log ──
        card_log = self._card(self.bulk_scroll_page, 4, "📝  Log", expand=True)
        self.bulk_log_w = self._make_log(card_log)
        self.bulk_log_w.pack(fill="both", expand=True, padx=2)

    def _build_txt_frame(self):
        frame = ctk.CTkFrame(self, fg_color=C['bg'], corner_radius=0)
        self._frames['txt'] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        page = ctk.CTkScrollableFrame(frame, fg_color=C['bg'], corner_radius=0)
        page.grid(row=0, column=0, sticky='nsew')
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(page, text='VCF ke TXT', font=ctk.CTkFont(size=24, weight='bold'),
                     text_color=C['text']).grid(row=0, column=0, padx=28, pady=(20, 2), sticky='w')
        source = self._card(page, 1, '📥  Input VCF — Banyak File / Folder / Paste')
        self.txt_tab = ctk.CTkTabview(source, height=190, fg_color=C['bg_card'])
        self.txt_tab.pack(fill='x')
        files = self.txt_tab.add('File VCF')
        paste = self.txt_tab.add('Paste VCF')
        self._txt_paths = []
        self._txt_running = False
        self.txt_drop = ctk.CTkLabel(files, text='Drag & drop satu atau beberapa VCF / folder ke sini',
                                    height=45, fg_color=C['drop_zone'], corner_radius=10)
        self.txt_drop.pack(fill='x', pady=4)
        self._enable_drop(self.txt_drop, self._txt_on_drop)
        buttons = ctk.CTkFrame(files, fg_color='transparent')
        buttons.pack(fill='x', pady=4)
        for label, command in [('Tambah VCF', self._txt_browse),
                               ('Tambah Folder', self._txt_browse_folder),
                               ('Kosongkan', self._txt_clear)]:
            ctk.CTkButton(buttons, text=label, width=120, command=command).pack(side='left', padx=4)
        self.txt_file_list = ctk.CTkTextbox(files, height=85, state='disabled', fg_color=C['input'])
        self.txt_file_list.pack(fill='x', pady=4)
        ctk.CTkLabel(paste, text='Tempel isi VCF lengkap (BEGIN:VCARD sampai END:VCARD).',
                     text_color=C['text2']).pack(anchor='w')
        self.txt_paste = ctk.CTkTextbox(paste, height=130, fg_color=C['input'])
        self.txt_paste.pack(fill='x')

        settings = self._card(page, 2, '⚙️  Format & Pembagian TXT')
        self.txt_include_name = ctk.BooleanVar(value=False)
        format_row = ctk.CTkFrame(settings, fg_color='transparent')
        format_row.pack(fill='x', pady=6)
        for label, value in [('Tanpa nama (nomor saja)', False), ('Dengan nama (nomor + nama asli)', True)]:
            ctk.CTkRadioButton(format_row, text=label, variable=self.txt_include_name,
                               value=value).pack(side='left', padx=8)
        self.txt_mode = ctk.StringVar(value='combined')
        mode_row = ctk.CTkFrame(settings, fg_color='transparent')
        mode_row.pack(fill='x', pady=6)
        for label, value in [('Gabung 1 TXT', 'combined'), ('Pecah beberapa TXT', 'split'),
                             ('1 TXT per VCF', 'source')]:
            ctk.CTkRadioButton(mode_row, text=label, variable=self.txt_mode, value=value,
                               command=self._txt_mode_changed).pack(side='left', padx=8)
        fields = ctk.CTkFrame(settings, fg_color='transparent')
        fields.pack(fill='x', padx=8, pady=6)
        fields.grid_columnconfigure(1, weight=1)
        self.txt_per = ctk.StringVar(value='100')
        self.txt_filename = ctk.StringVar()
        ctk.CTkLabel(fields, text='Nomor per TXT:').grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.txt_per_entry = ctk.CTkEntry(fields, textvariable=self.txt_per, state='disabled')
        self.txt_per_entry.grid(row=0, column=1, sticky='ew', pady=4)
        ctk.CTkLabel(fields, text='Nama file TXT:').grid(row=1, column=0, sticky='w', padx=(0, 12))
        ctk.CTkEntry(fields, textvariable=self.txt_filename,
                     placeholder_text='Tanpa .txt; kosong = otomatis / nama VCF sumber').grid(
                         row=1, column=1, sticky='ew', pady=4)
        ctk.CTkLabel(settings, text='Satu nomor per baris. Kontak dengan beberapa nomor menghasilkan beberapa baris.\n'
                     'Nama mengikuti VCF; kontak tanpa nama tetap disimpan. Urutan dan nomor duplikat dipertahankan.',
                     justify='left', text_color=C['text2'], font=ctk.CTkFont(size=11)).pack(anchor='w', padx=8, pady=4)

        rename = self._card(page, 3, '✏️  Auto Rename TXT (Opsional)')
        self.txt_rename_on = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(rename, text='Gunakan daftar nama file, satu nama per baris (tanpa .txt)',
                        variable=self.txt_rename_on).pack(anchor='w', padx=8, pady=4)
        self.txt_rename_tab = ctk.CTkTabview(rename, height=160, fg_color=C['bg_card'])
        self.txt_rename_tab.pack(fill='x', padx=8, pady=4)
        names_tab = self.txt_rename_tab.add('Paste Nama')
        generate_tab = self.txt_rename_tab.add('Generate List')
        ctk.CTkButton(names_tab, text='Muat daftar dari TXT', command=self._txt_load_names).pack(anchor='w', padx=8, pady=4)
        self.txt_rename_paste = ctk.CTkTextbox(names_tab, height=80, fg_color=C['input'])
        self.txt_rename_paste.pack(fill='x', padx=8, pady=4)
        gen_row = ctk.CTkFrame(generate_tab, fg_color='transparent')
        gen_row.pack(fill='x', padx=4, pady=8)
        self.txt_gen_prefix = ctk.StringVar(value='GRUP')
        self.txt_gen_start = ctk.StringVar(value='1')
        self.txt_gen_end = ctk.StringVar(value='5')
        self.txt_gen_no_space = ctk.BooleanVar(value=False)
        for label, variable, width in [('Prefix:', self.txt_gen_prefix, 110),
                                       ('Rentang:', self.txt_gen_start, 60),
                                       ('-', self.txt_gen_end, 60)]:
            ctk.CTkLabel(gen_row, text=label, text_color=C['text']).pack(side='left', padx=(4, 0))
            ctk.CTkEntry(gen_row, textvariable=variable, width=width, height=30,
                         fg_color=C['input'], border_color=C['border']).pack(side='left', padx=4)
        ctk.CTkCheckBox(gen_row, text='Tanpa Spasi', variable=self.txt_gen_no_space,
                        width=100).pack(side='left', padx=8)
        ctk.CTkButton(gen_row, text='Generate', width=80, height=30,
                      command=self._txt_generate_names).pack(side='left', padx=4)
        self.txt_gen_preview = ctk.CTkLabel(generate_tab, text='', text_color=C['text2'],
                                           anchor='w', justify='left', wraplength=650)
        self.txt_gen_preview.pack(fill='x', padx=8, pady=4)
        for variable in (self.txt_gen_prefix, self.txt_gen_start, self.txt_gen_end, self.txt_gen_no_space):
            variable.trace_add('write', self._txt_update_generator_preview)
        self._txt_update_generator_preview()

        review = self._card(page, 4, '👁  Preview & Konversi')
        self.txt_preview = ctk.CTkTextbox(review, height=150, state='disabled', fg_color=C['input'])
        self.txt_preview.pack(fill='x', pady=4)
        actions = ctk.CTkFrame(review, fg_color='transparent')
        actions.pack(fill='x', pady=6)
        ctk.CTkButton(actions, text='Perbarui Preview', command=self._txt_review).pack(side='left', padx=4)
        self.txt_go_button = ctk.CTkButton(actions, text='Review & Konversi ke TXT',
                                          fg_color=C['success'], text_color='#081810', command=self._txt_go)
        self.txt_go_button.pack(side='left', padx=4)
        self.txt_prog = ctk.CTkProgressBar(review)
        self.txt_prog.pack(fill='x', pady=8)
        self.txt_prog.set(0)
        self.txt_output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'txt_output')
        ctk.CTkLabel(review, text='Output: ' + self.txt_output_folder,
                     text_color=C['text2'], anchor='w').pack(fill='x')
        log = self._card(page, 5, '📝  Log')
        self.txt_log = self._make_log(log)
        self.txt_log.configure(height=120)
        self.txt_log.pack(fill='x')

    def _txt_mode_changed(self):
        self.txt_per_entry.configure(state='normal' if self.txt_mode.get() == 'split' else 'disabled')

    def _txt_add_paths(self, paths):
        candidates = []
        try:
            for path in paths:
                if os.path.isdir(path):
                    candidates.extend(os.path.join(path, name) for name in sorted(os.listdir(path), key=str.casefold)
                                      if name.lower().endswith('.vcf') and os.path.isfile(os.path.join(path, name)))
                elif os.path.isfile(path) and path.lower().endswith('.vcf'):
                    candidates.append(path)
                else:
                    raise ValueError('Pilih file .vcf atau folder berisi VCF.')
            if not candidates:
                raise ValueError('Tidak ada file VCF di folder yang dipilih.')
        except (OSError, ValueError) as exc:
            messagebox.showwarning('Input VCF', str(exc))
            return
        known = {os.path.normcase(os.path.abspath(path)) for path in self._txt_paths}
        for path in candidates:
            absolute = os.path.abspath(path)
            key = os.path.normcase(absolute)
            if key not in known:
                self._txt_paths.append(absolute)
                known.add(key)
        self.txt_tab.set('File VCF')
        self._txt_update_file_list()

    def _txt_update_file_list(self):
        self.txt_file_list.configure(state='normal')
        self.txt_file_list.delete('1.0', 'end')
        self.txt_file_list.insert('end', '\n'.join(f'{i}. {path}' for i, path in enumerate(self._txt_paths, 1)))
        self.txt_file_list.configure(state='disabled')
        self.txt_drop.configure(text=f'{len(self._txt_paths)} file VCF dipilih • Drag & drop untuk menambah')

    def _txt_clear(self):
        self._txt_paths.clear()
        self._txt_update_file_list()

    def _txt_browse(self):
        paths = filedialog.askopenfilenames(title='Pilih satu atau beberapa VCF', filetypes=[('VCF', '*.vcf')])
        if paths:
            self._txt_add_paths(paths)

    def _txt_browse_folder(self):
        path = filedialog.askdirectory(title='Pilih folder berisi VCF')
        if path:
            self._txt_add_paths([path])

    def _txt_on_drop(self, event):
        self._txt_add_paths(self.tk.splitlist(event.data))

    def _txt_generator_settings(self):
        try:
            start = int(self.txt_gen_start.get())
            end = int(self.txt_gen_end.get())
        except ValueError:
            raise ValueError('Rentang awal dan akhir harus berupa angka bulat.') from None
        if start < 0 or end < start:
            raise ValueError('Rentang harus dimulai dari 0 atau lebih, dan akhir tidak boleh lebih kecil dari awal.')
        if end - start + 1 > 100000:
            raise ValueError('Maksimal 100.000 nama dalam satu kali generate.')
        prefix = self.txt_gen_prefix.get().strip()
        separator = '' if self.txt_gen_no_space.get() or not prefix else ' '
        base = prefix + separator
        validate_txt_stem(f'{base}{start}')
        return base, start, end

    def _txt_update_generator_preview(self, *_):
        try:
            base, start, end = self._txt_generator_settings()
            examples = ', '.join(f'{base}{i}.txt' for i in range(start, min(end + 1, start + 3)))
            text = f'{end - start + 1} nama: {examples}' + (' …' if end - start >= 3 else '')
        except ValueError as exc:
            text = str(exc)
        self.txt_gen_preview.configure(text=text)

    def _txt_generate_names(self):
        try:
            base, start, end = self._txt_generator_settings()
        except ValueError as exc:
            messagebox.showwarning('Generate List TXT', str(exc))
            return
        names = '\n'.join(f'{base}{i}' for i in range(start, end + 1))
        self.txt_rename_paste.delete('1.0', 'end')
        self.txt_rename_paste.insert('1.0', names + '\n')
        self.txt_rename_on.set(True)
        self.txt_rename_tab.set('Paste Nama')

    def _txt_load_names(self):
        path = filedialog.askopenfilename(title='Daftar nama TXT', filetypes=[('Text', '*.txt')])
        if path:
            try:
                with open(path, encoding='utf-8-sig') as source:
                    names = source.read()
                self.txt_rename_paste.delete('1.0', 'end')
                self.txt_rename_paste.insert('1.0', names)
                self.txt_rename_on.set(True)
                self.txt_rename_tab.set('Paste Nama')
            except (OSError, UnicodeError) as exc:
                messagebox.showerror('Daftar nama', str(exc))

    def _txt_make_plan(self):
        sources = []
        if self.txt_tab.get() == 'Paste VCF':
            sources.append(('pasted_contacts', parse_vcf_text(self.txt_paste.get('1.0', 'end'))))
        else:
            for path in self._txt_paths:
                try:
                    rows = read_vcf(path)
                except (OSError, ValueError) as exc:
                    raise ValueError(f'{os.path.basename(path)}: {exc}') from exc
                if not rows:
                    raise ValueError(f'{os.path.basename(path)}: tidak ada nomor telepon. Keluarkan file ini dari input.')
                sources.append((os.path.splitext(os.path.basename(path))[0], rows))
        per = None
        if self.txt_mode.get() == 'split':
            raw_per = self.txt_per.get().strip()
            if ',' in raw_per:
                per = raw_per
            else:
                try:
                    per = int(raw_per)
                except ValueError:
                    raise ValueError('Nomor per TXT harus angka positif.') from None
        names = None
        if self.txt_rename_on.get():
            names = [name.strip() for name in self.txt_rename_paste.get('1.0', 'end').splitlines() if name.strip()]
            if not names:
                raise ValueError('Auto rename aktif tetapi daftar nama kosong.')
        plan = plan_txt_files(sources, self.txt_mode.get(), per, self.txt_filename.get().strip(), names)
        total = sum(len(rows) for _, rows in plan)
        summary = f'{len(sources)} input VCF → {total} nomor → {len(plan)} file TXT\n'
        summary += 'Format: ' + ('nomor + nama asli' if self.txt_include_name.get() else 'nomor saja') + '\n'
        summary += '\n'.join(f'{stem}.txt — {len(rows)} nomor' for stem, rows in plan[:8])
        if len(plan) > 8:
            summary += f'\n… dan {len(plan) - 8} file lainnya'
        if names and len(names) != len(plan):
            summary += f'\nDaftar rename: {len(names)} nama untuk {len(plan)} file. '
            summary += 'Nama kurang: gunakan nama otomatis.' if len(names) < len(plan) else 'Nama berlebih tidak digunakan.'
        summary += '\nNama file yang sudah ada akan diberi akhiran _1, _2, dan seterusnya.'
        return plan, summary

    def _txt_review(self):
        try:
            plan, summary = self._txt_make_plan()
        except (OSError, ValueError) as exc:
            self.txt_preview.configure(state='normal')
            self.txt_preview.delete('1.0', 'end')
            self.txt_preview.configure(state='disabled')
            messagebox.showwarning('Periksa input TXT', str(exc))
            return None
        preview = summary + '\n\nContoh isi TXT pertama:\n'
        preview += '\n'.join(format_txt_row(row, self.txt_include_name.get()) for row in plan[0][1][:5])
        self.txt_preview.configure(state='normal')
        self.txt_preview.delete('1.0', 'end')
        self.txt_preview.insert('1.0', preview)
        self.txt_preview.configure(state='disabled')
        return plan, summary

    def _txt_go(self):
        if self._txt_running:
            return
        result = self._txt_review()
        if result is None:
            return
        plan, summary = result
        if not messagebox.askyesno('Review VCF ke TXT', summary + '\n\nLanjutkan konversi?'):
            return
        self._txt_running = True
        self.txt_go_button.configure(state='disabled')
        self.txt_prog.set(0)
        events = queue.Queue()
        include_name = self.txt_include_name.get()
        output_folder = self.txt_output_folder

        def process():
            try:
                written = write_txt_files(plan, output_folder, include_name,
                    lambda path, count, progress: events.put(('progress', (path, count, progress))))
                events.put(('done', len(written)))
            except Exception as exc:
                events.put(('error', str(exc)))

        def poll():
            while True:
                try:
                    event, data = events.get_nowait()
                except queue.Empty:
                    self.after(80, poll)
                    return
                if event == 'progress':
                    path, count, progress = data
                    self.txt_prog.set(progress)
                    self._log(self.txt_log, f'✅ {os.path.basename(path)} — {count} nomor')
                    continue
                self._txt_running = False
                self.txt_go_button.configure(state='normal')
                if event == 'done':
                    self._log(self.txt_log, f'Selesai: {data} TXT tersimpan di {output_folder}')
                    messagebox.showinfo('Sukses', f'{data} file TXT berhasil dibuat.\nOutput: {output_folder}')
                else:
                    self._log(self.txt_log, 'Konversi gagal: ' + data)
                    messagebox.showerror('Konversi gagal', data + '\nPeriksa log untuk file yang sudah tersimpan.')
                return

        threading.Thread(target=process, daemon=True).start()
        self.after(80, poll)

    def _build_xlsx_frame(self):
        frame = ctk.CTkFrame(self, fg_color=C['bg'], corner_radius=0)
        self._frames['xlsx'] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        page = ctk.CTkScrollableFrame(frame, fg_color=C['bg'], corner_radius=0)
        page.grid(row=0, column=0, sticky='nsew')
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(page, text='TXT / Paste ke XLSX', font=ctk.CTkFont(size=24, weight='bold'),
                     text_color=C['text']).grid(row=0, column=0, padx=28, pady=(20, 2), sticky='w')
        source = self._card(page, 1, '📥  Input Nomor')
        self.xlsx_tab = ctk.CTkTabview(source, height=230, fg_color=C['bg_card'])
        self.xlsx_tab.pack(fill='x')
        files = self.xlsx_tab.add('File TXT')
        paste = self.xlsx_tab.add('Paste Langsung')
        self.xlsx_file = ctk.StringVar()
        drop = ctk.CTkLabel(files, text='Drag & drop file TXT ke sini', height=75,
                            fg_color=C['drop_zone'], corner_radius=10)
        drop.pack(fill='x', pady=8)
        self._enable_drop(drop, self._xlsx_drop)
        ctk.CTkEntry(files, textvariable=self.xlsx_file, placeholder_text='Path file .txt').pack(fill='x', pady=6)
        ctk.CTkButton(files, text='Pilih TXT', command=lambda: self._browse_file(self.xlsx_file)).pack(anchor='w')
        ctk.CTkLabel(paste, text='Paste nomor di sini, satu nomor per baris.', text_color=C['text2']).pack(anchor='w')
        self.xlsx_paste = ctk.CTkTextbox(paste, height=160, fg_color=C['input'])
        self.xlsx_paste.pack(fill='x')

        settings = self._card(page, 2, '📊  File Excel Sederhana')
        ctk.CTkLabel(settings, text='Satu nomor per baris di kolom A, mulai A1. Tanpa header atau tabel.\n'
                     'Awalan 0, tanda +, nomor panjang, urutan, dan duplikat tetap dipertahankan.\n'
                     'Baris kosong dilewati. Nomor disimpan sebagai teks agar tidak berubah di Excel.',
                     justify='left', text_color=C['text2']).pack(anchor='w', padx=8, pady=6)
        self.xlsx_filename = ctk.StringVar()
        ctk.CTkEntry(settings, textvariable=self.xlsx_filename,
                     placeholder_text='Nama file (kosong = nama TXT / contacts.xlsx)').pack(fill='x', padx=8, pady=6)
        self.xlsx_output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xlsx_output')
        ctk.CTkLabel(settings, text='Output: ' + self.xlsx_output_folder,
                     text_color=C['text2']).pack(anchor='w', padx=8)

        review = self._card(page, 3, '👁  Preview & Konversi')
        self.xlsx_preview = ctk.CTkTextbox(review, height=160, state='disabled', fg_color=C['input'])
        self.xlsx_preview.pack(fill='x', pady=6)
        actions = ctk.CTkFrame(review, fg_color='transparent')
        actions.pack(fill='x', pady=6)
        ctk.CTkButton(actions, text='Perbarui Preview', command=self._xlsx_review).pack(side='left', padx=4)
        self.xlsx_go_button = ctk.CTkButton(actions, text='Konversi ke XLSX', command=self._xlsx_go,
                                           fg_color=C['success'], text_color='#081810')
        self.xlsx_go_button.pack(side='left', padx=4)
        self.xlsx_status = ctk.CTkLabel(review, text='', text_color=C['text2'], wraplength=650)
        self.xlsx_status.pack(anchor='w', padx=4, pady=6)
        self._xlsx_running = False

    def _xlsx_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if len(paths) != 1 or not paths[0].lower().endswith('.txt') or not os.path.isfile(paths[0]):
            messagebox.showwarning('Input TXT', 'Pilih satu file .txt.')
            return
        self.xlsx_file.set(paths[0])
        self.xlsx_tab.set('File TXT')
        self._xlsx_review()

    def _xlsx_review(self):
        self.xlsx_preview.configure(state='normal')
        self.xlsx_preview.delete('1.0', 'end')
        self.xlsx_preview.configure(state='disabled')
        try:
            if self.xlsx_tab.get() == 'Paste Langsung':
                rows = parse_number_lines(self.xlsx_paste.get('1.0', 'end'))
                default_name = 'contacts'
            else:
                path = self.xlsx_file.get().strip()
                if not path or not path.lower().endswith('.txt'):
                    raise ValueError('Pilih file TXT terlebih dahulu.')
                rows = read_number_txt(path)
                default_name = os.path.splitext(os.path.basename(path))[0]
            name = self.xlsx_filename.get().strip()
            if name.lower().endswith('.xlsx'):
                name = name[:-5]
            name = name or default_name
            validate_file_stem(name)
        except (OSError, ValueError) as exc:
            messagebox.showwarning('Periksa input XLSX', str(exc))
            return None
        preview = f'{len(rows)} nomor → {name}.xlsx\nKolom A, tanpa header. Preview 10 baris pertama:\n\n'
        preview += '\n'.join(rows[:10])
        self.xlsx_preview.configure(state='normal')
        self.xlsx_preview.insert('1.0', preview)
        self.xlsx_preview.configure(state='disabled')
        return rows, os.path.join(self.xlsx_output_folder, name + '.xlsx')

    def _xlsx_go(self):
        if self._xlsx_running:
            return
        result = self._xlsx_review()
        if result is None:
            return
        rows, output_path = result
        self._xlsx_running = True
        self.xlsx_go_button.configure(state='disabled')
        self.xlsx_status.configure(text=f'Menyimpan {len(rows)} nomor ke XLSX…')
        events = queue.Queue()

        def process():
            try:
                events.put(('done', write_numbers_xlsx(rows, output_path)))
            except ImportError:
                events.put(('error', 'Paket openpyxl belum tersedia. Instal dengan: python -m pip install openpyxl'))
            except Exception as exc:
                events.put(('error', str(exc)))

        def poll():
            try:
                event, data = events.get_nowait()
            except queue.Empty:
                self.after(80, poll)
                return
            self._xlsx_running = False
            self.xlsx_go_button.configure(state='normal')
            if event == 'done':
                self.xlsx_status.configure(text=f'Selesai: {len(rows)} nomor → {data}')
                messagebox.showinfo('Sukses', f'{len(rows)} nomor tersimpan di:\n{data}')
            else:
                self.xlsx_status.configure(text='Konversi gagal: ' + data)
                messagebox.showerror('Konversi gagal', data)

        threading.Thread(target=process, daemon=True).start()
        self.after(80, poll)

    def _update_name_controls_state(self):
        no_name = self.bulk_no_name.get()
        name_phone = hasattr(self, 'bulk_name_phone') and self.bulk_name_phone.get()
        self.bulk_name_entry.configure(state="disabled" if no_name else "normal")
        seq_state = "disabled" if (no_name or name_phone) else "normal"
        self.bulk_start_entry.configure(state=seq_state)
        for rb in self.bulk_digit_radios:
            rb.configure(state=seq_state)

    def _toggle_no_name(self):
        if self.bulk_no_name.get():
            self.bulk_sync_names.set(False)
            if hasattr(self, 'bulk_name_phone'):
                self.bulk_name_phone.set(False)
        self._update_name_controls_state()
        # trigger preview update
        self.bulk_name.set(self.bulk_name.get())

    def _toggle_name_phone(self):
        if self.bulk_name_phone.get():
            self.bulk_no_name.set(False)
        self._update_name_controls_state()
        self._update_bulk_preview()

    def _toggle_sync_names(self):
        if self.bulk_sync_names.get() and self.bulk_no_name.get():
            self.bulk_no_name.set(False)
            self._update_name_controls_state()
        self._update_bulk_preview()
        
    def _toggle_rename_input(self):
        if self.bulk_rename_on.get():
            self._rename_input_frame.grid()
            if self.bulk_rename_use_txt.get():
                self._rename_tab.pack_forget()
            else:
                self._rename_tab.pack(fill="x", padx=0, pady=0)
            self._bulk_update_rename_info()
        else:
            self._rename_tab.pack_forget()
            self._rename_input_frame.grid_remove()
            self.bulk_rename_info.configure(text="")
            self.bulk_rename_preview.configure(text="")

    def _bulk_paths(self):
        """Return the list of existing TXT paths in the Bulk file field."""
        return [p for p in split_bulk_paths(self.bulk_file_var.get()) if os.path.isfile(p)]

    def _bulk_set_paths(self, paths, append=False):
        current = split_bulk_paths(self.bulk_file_var.get()) if append else []
        known = {os.path.normcase(os.path.abspath(p)) for p in current}
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key not in known and os.path.isfile(p):
                current.append(p)
                known.add(key)
        self.bulk_file_var.set('; '.join(current))
        self.bulk_tab.set("📂 File / Drag & Drop")
        self._bulk_show_file_preview()

    def _bulk_clear_files(self):
        self.bulk_file_var.set('')
        self._bulk_drop_label.configure(
            text="🗂️  Drag & drop satu atau BANYAK file TXT ke sini\natau klik Browse (bisa pilih banyak)",
            text_color=C["text2"])
        self.bulk_number_preview.pack_forget()
        self._update_prediction()
        self._update_bulk_preview()

    def _bulk_browse_and_preview(self):
        paths = filedialog.askopenfilenames(title="Pilih satu atau banyak File TXT",
                                            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if paths:
            self._bulk_set_paths(list(paths))

    def _bulk_show_file_preview(self, path=None):
        paths = self._bulk_paths()
        if not paths:
            return
        try:
            per_file = [(p, read_contact_lines(p)) for p in paths]
            total = sum(len(lines) for _, lines in per_file)
            if len(per_file) == 1:
                label = f"✅  {os.path.basename(paths[0])}  —  {total} nomor"
            else:
                label = f"✅  {len(per_file)} file TXT  —  total {total} nomor"
            self._bulk_drop_label.configure(text=label, text_color=C["success"])

            self.bulk_number_preview.pack(fill="x", padx=4, pady=(2, 2))
            self.bulk_number_preview.configure(state="normal")
            self.bulk_number_preview.delete("1.0", "end")
            if len(per_file) == 1:
                lines = per_file[0][1]
                self.bulk_number_preview.insert("end", f"📞 Preview {total} nomor:\n")
                for i, l in enumerate(lines[:5]):
                    self.bulk_number_preview.insert("end", f"  {i+1}. {l}\n")
                if total > 5:
                    self.bulk_number_preview.insert("end", f"  … +{total - 5} lainnya\n")
            else:
                self.bulk_number_preview.insert("end", f"📂 {len(per_file)} file TXT ({total} nomor):\n")
                for i, (p, lines) in enumerate(per_file, 1):
                    first = f"  (cth: {lines[0]})" if lines else ""
                    self.bulk_number_preview.insert(
                        "end", f"  {i}. {os.path.basename(p)} — {len(lines)} nomor{first}\n")
            self.bulk_number_preview.configure(state="disabled")

            if self.bulk_rename_on.get():
                self._bulk_update_rename_info()
            self._update_prediction()
            self._update_bulk_preview()
        except Exception:
            self._bulk_drop_label.configure(text="❌ Error membaca file TXT", text_color=C["error"])

    def _bulk_on_drop(self, event):
        try:
            paths = list(self.tk.splitlist(event.data))
        except Exception:
            paths = [self._parse_drop_path(event)]
        files = []
        for p in paths:
            if os.path.isdir(p):
                files.extend(os.path.join(p, n) for n in sorted(os.listdir(p), key=str.casefold)
                             if n.lower().endswith('.txt') and os.path.isfile(os.path.join(p, n)))
            elif os.path.isfile(p):
                files.append(p)
        if files:
            # Dropping adds to the existing list so several drops can be combined
            self._bulk_set_paths(files, append=True)

    def _bulk_browse_rename_file(self):
        path = filedialog.askopenfilename(title="Pilih File", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if path:
            self.bulk_rename_file_var.set(path)
            self._bulk_update_rename_info()

    def _bulk_rename_on_drop(self, event):
        path = self._parse_drop_path(event)
        if path and os.path.isfile(path):
            self.bulk_rename_file_var.set(path)
            self._bulk_update_rename_info()
            
    def _bulk_update_rename_info(self):
        self._update_prediction()
        names = self._get_rename_names()
        if names:
            count = len(names)
            preview = names[:4]
            p_txt = ", ".join([f"{n}.vcf" for n in preview])
            if count > 4: p_txt += f", … +{count-4} lainnya"
            
            # calculate recommendation
            c_lines = self._get_bulk_contacts_silent()
            if c_lines:
                per_raw = self.bulk_per.get().strip()
                if ',' in per_raw:
                    try:
                        chunks = parse_chunk_sizes(len(c_lines), per_raw)
                        msg = (f"📊 Ditemukan {count} nama file VCF.\n"
                               f"💡 Pembagian custom aktif: {len(chunks)} file ({', '.join(map(str, chunks))} kontak).")
                    except ValueError as exc:
                        msg = f"⚠️ {exc}"
                else:
                    import math
                    per = math.ceil(len(c_lines) / count)
                    if self.bulk_per.get() != str(per):
                        self.bulk_per.set(str(per))
                    msg = f"📊 Ditemukan {count} nama file VCF.\n💡 {len(c_lines)} kontak dibagi {count} file → otomatis set {per} kontak/file."
            else:
                msg = f"📊 Ditemukan {count} nama file VCF.\n💡 Muat daftar nomor kontak untuk menghitung rekomendasi."
                
            self.bulk_rename_info.configure(text=msg)
            self.bulk_rename_preview.configure(text=f"📁 Preview Nama File VCF: {p_txt}")
        else:
            self.bulk_rename_info.configure(text="")
            self.bulk_rename_preview.configure(text="")
        if hasattr(self, '_update_bulk_preview'):
            self._update_bulk_preview()
            
    def _get_bulk_contacts_silent(self):
        current_tab = self.bulk_tab.get()
        if "Paste" in current_tab:
            raw = self.bulk_paste_box.get("1.0", "end").strip()
            return [l.strip() for l in raw.splitlines() if l.strip()] if raw else None
        else:
            paths = self._bulk_paths()
            if paths:
                lines = []
                for p in paths:
                    lines.extend(read_contact_lines(p))
                return lines
        return None

    def _get_bulk_contacts(self):
        """Get contact list from file(s) or paste, returns list of strings."""
        current_tab = self.bulk_tab.get()
        if "Paste" in current_tab:
            raw = self.bulk_paste_box.get("1.0", "end").strip()
            if not raw:
                messagebox.showwarning("Peringatan", "Paste nomor telepon terlebih dahulu.")
                return None
            return [l.strip() for l in raw.splitlines() if l.strip()]
        else:
            paths = self._bulk_paths()
            if not paths:
                messagebox.showwarning("Peringatan", "Pilih file TXT yang valid.")
                return None
            lines = []
            for p in paths:
                lines.extend(read_contact_lines(p))
            return lines

    def _bulk_txt_jobs(self):
        """Return [(txt_stem, contacts)] when several TXT files should be converted separately."""
        if "Paste" in self.bulk_tab.get() or not self.bulk_multi_separate.get():
            return None
        paths = self._bulk_paths()
        if len(paths) < 2:
            return None
        return [(os.path.splitext(os.path.basename(p))[0], read_contact_lines(p)) for p in paths]

    def _get_rename_names(self):
        """Get rename names from file or paste."""
        if hasattr(self, 'bulk_rename_use_txt') and self.bulk_rename_use_txt.get():
            paths = self._bulk_paths()
            if paths:
                base = os.path.splitext(os.path.basename(paths[0]))[0]
            else:
                base = "output"
            c_lines = self._get_bulk_contacts_silent()
            req = 1
            if c_lines:
                try:
                    per_str = self.bulk_per.get().strip()
                    chunks = parse_chunk_sizes(len(c_lines), per_str) if per_str else [len(c_lines)]
                    req = max(len(chunks), 1)
                except: pass
            if req <= 1:
                return [base]
            else:
                return [f"{base}-{i}" for i in range(1, req+1)]
                
        current_tab = self._rename_tab.get()
        if "Paste" in current_tab:
            raw = self.bulk_rename_paste.get("1.0", "end").strip()
            if not raw:
                return None
            return [l.strip() for l in raw.splitlines() if l.strip()]
        else:
            path = self.bulk_rename_file_var.get().strip()
            if not path or not os.path.isfile(path):
                return None
            with open(path, 'r', encoding='utf-8') as f:
                return [l.rstrip('\n') for l in f if l.strip()]

    def _bulk_go(self):
        contacts = self._get_bulk_contacts()
        if not contacts:
            if contacts is not None:
                messagebox.showwarning("Peringatan", "Daftar nomor kontak kosong.")
            return

        total = len(contacts)
        per_str = self.bulk_per.get().strip()
        per_file = per_str if per_str else total
        try:
            chunks = parse_chunk_sizes(total, per_file)
        except ValueError as exc:
            messagebox.showwarning("Peringatan", str(exc))
            return
            
        no_name = self.bulk_no_name.get()
        name_phone = hasattr(self, 'bulk_name_phone') and self.bulk_name_phone.get() and not no_name
        start = 1
        name = ""
        digits = 3
        
        if not no_name:
            name = self.bulk_name.get().strip()
            if not name:
                messagebox.showwarning("Peringatan", "Isi nama kontak."); return
            if not name_phone:
                try:
                    start = int(self.bulk_start.get()); assert start >= 0
                except:
                    messagebox.showwarning("Peringatan", "Nomor awalan harus angka ≥ 0."); return
                digits = self.bulk_digit.get()

        jobs = self._bulk_txt_jobs()
        if jobs:
            self._bulk_go_multi(jobs, per_str, name, start, digits, no_name, name_phone)
            return

        rename_names = None
        if self.bulk_rename_on.get():
            rename_names = self._get_rename_names()
            if not rename_names:
                messagebox.showwarning("Peringatan",
                    "Auto rename aktif tapi daftar nama kosong.\nIsi nama atau matikan opsi rename.")
                return

        num_files = len(chunks)
        sync_names = self.bulk_sync_names.get() and not no_name
        file_name = self.bulk_filename.get().strip()
        try:
            stems = bulk_file_stems(total, per_file, file_name, rename_names)
        except ValueError as exc:
            messagebox.showwarning("Peringatan", str(exc))
            return
        
        msg = f"📊 REVIEW KONVERSI\n\n"
        msg += f"Total kontak: {total}\n"
        if isinstance(per_file, str) and ',' in per_file:
            chunks_str = ", ".join(str(c) for c in chunks[:8])
            if len(chunks) > 8:
                chunks_str += f", … ({len(chunks)} bagian)"
            msg += f"Pembagian custom: {chunks_str}\n"
            req_sum = sum(int(x.strip()) for x in per_file.split(',') if x.strip())
            if req_sum < total:
                msg += f"ℹ️ Total custom ({req_sum}) < {total} kontak: sisa {total - req_sum} kontak masuk ke file terakhir.\n"
            elif req_sum > total:
                msg += f"ℹ️ Total custom ({req_sum}) > {total} kontak: disesuaikan dengan jumlah kontak.\n"
        else:
            msg += f"Kontak per file: {per_file}\n"
        msg += f"Jumlah file VCF: {num_files}\n\n"
        preview_name = stems[0] if sync_names else name
        if no_name:
            msg += f"📛 Nama Kontak: (Gunakan Nomor HP Langsung)\n"
        elif name_phone:
            first_phone = parse_contact_line(contacts[0])[0] or contacts[0].strip()
            msg += f"📛 Contoh Nama Kontak: {format_name_phone(preview_name, first_phone)}\n"
        else:
            msg += f"📛 Contoh Nama Kontak: {preview_name} {str(start).zfill(digits)}\n"
        msg += f"📁 Nama File: {stems[0]}.vcf"
        if num_files > 1:
            msg += f" → {stems[-1]}.vcf"
        msg += "\nVCF ringan: tanpa catatan negara/status.\n"
        if sync_names:
            suffix_desc = "nomor telepon" if name_phone else "nomor urut"
            msg += f"Nama kontak mengikuti nama file masing-masing + {suffix_desc}.\n"
        
        if rename_names:
            msg += f"\n✏️ Auto Rename Aktif\n"
            msg += f"Jumlah nama file disediakan: {len(rename_names)}\n"
            if len(rename_names) < num_files:
                msg += f"⚠️ PERHATIAN: Kekurangan {num_files - len(rename_names)} nama. Sebagian file tidak akan dinamai ulang!\n"
            elif len(rename_names) > num_files:
                msg += f"ℹ️ INFO: Sisa {len(rename_names) - num_files} nama tidak akan terpakai.\n"
            else:
                msg += f"✅ SEMPURNA: Jumlah nama pas dengan jumlah file.\n"
                
        msg += "\nLanjutkan proses konversi?"
        
        if not messagebox.askyesno("Review & Konfirmasi", msg):
            return

        threading.Thread(
            target=self._bulk_process,
            args=(contacts, per_file, name, start, digits, rename_names,
                  no_name, file_name, sync_names, name_phone),
            daemon=True,
        ).start()

    def _bulk_process(self, contacts, per_file, base_name, start, digits, rename_names,
                      no_name=False, file_name='', sync_names=False, name_phone=False):
        try:
            self._bulk_write_files(contacts, per_file, base_name, start, digits,
                                   rename_names, no_name, file_name, sync_names, name_phone)
        except Exception as exc:
            self._log(self.bulk_log_w, f"❌ Konversi gagal: {exc}")
            self.after(0, lambda error=str(exc): messagebox.showerror(
                "Konversi gagal", f"Proses dihentikan: {error}\nPeriksa log untuk file yang sudah tersimpan."))

    def _bulk_write_files(self, contacts, per_file, base_name, start, digits, rename_names,
                          no_name=False, file_name='', sync_names=False, name_phone=False,
                          notify=True):
        output_folder = get_output_folder()
        total = len(contacts)
        chunks = parse_chunk_sizes(total, per_file)
        stems = bulk_file_stems(total, per_file, file_name, rename_names)
        self._log(self.bulk_log_w, f"📄 Memproses {total} kontak …")

        idx = 0
        fi = 0
        nc = start
        inv = 0
        total_bytes = 0

        for chunk_size in chunks:
            if idx >= total:
                break
            fi += 1
            stem = stems[fi - 1]
            final_stem = stem
            suffix = 1
            # Write directly under the final name, including auto-rename names.
            # Exclusive creation also prevents overwriting an earlier output.
            while True:
                fpath = os.path.join(output_folder, f'{final_stem}.vcf')
                try:
                    vf = open(fpath, 'x', encoding='utf-8', newline='')
                    break
                except FileExistsError:
                    final_stem = f'{stem}_{suffix}'
                    suffix += 1
            fname = os.path.basename(fpath)
            contact_base = final_stem if sync_names else base_name
            written_in_file = 0
            with vf:
                for _ in range(chunk_size):
                    if idx >= total:
                        break
                    phone, _ = parse_contact_line(contacts[idx])
                    if not phone:
                        idx += 1
                        continue
                    if no_name:
                        cname = phone
                    elif name_phone:
                        cname = format_name_phone(contact_base, phone)
                    else:
                        cname = f"{contact_base} {str(nc).zfill(digits)}"
                        nc += 1
                    card, valid = build_vcard(cname, phone)
                    vf.write(card)
                    written_in_file += 1
                    if not valid:
                        inv += 1
                    idx += 1

            file_bytes = os.path.getsize(fpath)
            total_bytes += file_bytes
            prog = idx / total
            self.after(0, lambda p=prog: self.bulk_prog.set(p))
            self._log(self.bulk_log_w, f"  ✅ {fname} — {written_in_file} kontak ({file_bytes / 1024:.1f} KiB)")

        self._log(self.bulk_log_w, f"\n🎉 {total} kontak → {fi} file VCF  (invalid: {inv})")

        self._log(self.bulk_log_w, f"📦 Total ukuran: {total_bytes / 1024:.1f} KiB")
        self._log(self.bulk_log_w, f"📁 Output: {output_folder}")
        if notify:
            self.after(0, lambda: messagebox.showinfo("Sukses",
                f"Berhasil! {total} kontak → {fi} file VCF\nOutput: {output_folder}"))
        return total, fi, inv

    def _bulk_go_multi(self, jobs, per_str, name, start, digits, no_name, name_phone):
        """Review & convert several TXT files, each into its own VCF file(s)."""
        jobs = [(stem, contacts) for stem, contacts in jobs]
        empty = [stem for stem, contacts in jobs if not contacts]
        jobs = [(stem, contacts) for stem, contacts in jobs if contacts]
        if not jobs:
            messagebox.showwarning("Peringatan", "Semua file TXT kosong.")
            return
        sync_names = self.bulk_sync_names.get() and not no_name
        plan = []
        try:
            for stem, contacts in jobs:
                per_file = per_str if per_str else len(contacts)
                stems = bulk_file_stems(len(contacts), per_file, stem)
                plan.append((stem, contacts, per_file, stems))
        except ValueError as exc:
            messagebox.showwarning("Peringatan", str(exc))
            return

        total = sum(len(c) for _, c, _, _ in plan)
        total_files = sum(len(s) for _, _, _, s in plan)
        msg = "📊 REVIEW KONVERSI — BANYAK TXT\n\n"
        msg += f"{len(plan)} file TXT → {total} kontak → {total_files} file VCF\n"
        msg += f"Kontak per file: {per_str or 'semua (1 VCF per TXT)'}\n\n"
        for stem, contacts, _, stems in plan[:8]:
            tail = f"{stems[0]}.vcf" + (f" → {stems[-1]}.vcf" if len(stems) > 1 else "")
            msg += f"• {stem}.txt ({len(contacts)}) → {tail}\n"
        if len(plan) > 8:
            msg += f"… dan {len(plan) - 8} TXT lainnya\n"
        if empty:
            msg += f"⚠️ Dilewati (kosong): {', '.join(empty[:5])}\n"
        first_stem, first_contacts, _, first_stems = plan[0]
        contact_base = first_stems[0] if sync_names else name
        if no_name:
            msg += "\n📛 Nama Kontak: (Gunakan Nomor HP Langsung)\n"
        elif name_phone:
            first_phone = parse_contact_line(first_contacts[0])[0] or first_contacts[0]
            msg += f"\n📛 Contoh Nama Kontak: {format_name_phone(contact_base, first_phone)}\n"
        else:
            msg += f"\n📛 Contoh Nama Kontak: {contact_base} {str(start).zfill(digits)}\n"
        if self.bulk_rename_on.get():
            msg += "ℹ️ Auto rename diabaikan: nama file VCF mengikuti nama TXT.\n"
        msg += "\nLanjutkan proses konversi?"
        if not messagebox.askyesno("Review & Konfirmasi", msg):
            return
        threading.Thread(
            target=self._bulk_process_multi,
            args=(plan, name, start, digits, no_name, sync_names, name_phone),
            daemon=True,
        ).start()

    def _bulk_process_multi(self, plan, base_name, start, digits, no_name=False,
                            sync_names=False, name_phone=False):
        output_folder = get_output_folder()
        try:
            grand_total = grand_files = grand_inv = 0
            for i, (stem, contacts, per_file, _) in enumerate(plan, 1):
                self._log(self.bulk_log_w, f"\n📂 [{i}/{len(plan)}] {stem}.txt")
                t, f, inv = self._bulk_write_files(
                    contacts, per_file, base_name, start, digits, None,
                    no_name, stem, sync_names, name_phone, notify=False)
                grand_total += t; grand_files += f; grand_inv += inv
            self._log(self.bulk_log_w,
                      f"\n🏁 SELESAI: {len(plan)} TXT → {grand_total} kontak → {grand_files} file VCF (invalid: {grand_inv})")
            self.after(0, lambda: self.bulk_prog.set(1))
            self.after(0, lambda: messagebox.showinfo("Sukses",
                f"Berhasil! {len(plan)} file TXT → {grand_files} file VCF\n"
                f"Total {grand_total} kontak\nOutput: {output_folder}"))
        except Exception as exc:
            self._log(self.bulk_log_w, f"❌ Konversi gagal: {exc}")
            self.after(0, lambda error=str(exc): messagebox.showerror(
                "Konversi gagal", f"Proses dihentikan: {error}\nPeriksa log untuk file yang sudah tersimpan."))

    # ──────────────────────────────────────────────────────────
    #  FEATURE 2 : ADMIN VCF CREATOR  (from admincuy.py)
    #  + copy-paste + drag-drop
    # ──────────────────────────────────────────────────────────

    def _build_admin_frame(self):
        frame = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._frames["admin"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=32, pady=(24, 2), sticky="ew")
        ctk.CTkLabel(hdr, text="Admin VCF Creator",
                     font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Pemisah:  .  = Admin grup  |  ,  = Navy grup + simpan file  •  Drag & Drop / Paste",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(anchor="w", pady=(2, 0))

        # ── Input card ──
        card_in = self._card(frame, 1, "📥  Input — File / Drag & Drop / Paste")

        self.admin_tab = ctk.CTkTabview(card_in, fg_color=C["bg_card"],
                                         segmented_button_fg_color=C["accent_dim"],
                                         segmented_button_selected_color=C["accent"],
                                         segmented_button_unselected_color=C["border"],
                                         corner_radius=10, height=160)
        self.admin_tab.pack(fill="x", padx=2, pady=(0, 4))
        tab_f = self.admin_tab.add("📂 File / Drag & Drop")
        tab_p = self.admin_tab.add("📋 Paste Langsung")

        # File tab
        self.admin_file_var = ctk.StringVar()
        drop_z = ctk.CTkFrame(tab_f, fg_color=C["drop_zone"], corner_radius=12,
                               border_width=2, border_color=C["border"], height=70)
        drop_z.pack(fill="x", padx=4, pady=4)
        drop_z.pack_propagate(False)
        self._admin_drop_label = ctk.CTkLabel(
            drop_z, text="🗂️  Drag & drop file contacts.txt ke sini",
            font=ctk.CTkFont(size=13), text_color=C["text2"])
        self._admin_drop_label.pack(expand=True)
        self._enable_drop(drop_z, self._admin_on_drop)
        self._enable_drop(self._admin_drop_label, self._admin_on_drop)

        fr = ctk.CTkFrame(tab_f, fg_color="transparent")
        fr.pack(fill="x", padx=4, pady=(2, 2))
        ctk.CTkEntry(fr, textvariable=self.admin_file_var,
                     placeholder_text="Path file .txt …", height=36, corner_radius=10,
                     fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"]).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(fr, text="Browse", width=80, height=36, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=lambda: self._browse_file(self.admin_file_var)).pack(side="right")

        # Paste tab
        ctk.CTkLabel(tab_p, text="Paste isi contacts.txt (nomor + pemisah . dan ,):",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(anchor="w", padx=4, pady=(4, 2))
        self.admin_paste_box = ctk.CTkTextbox(
            tab_p, height=90, corner_radius=10,
            fg_color=C["input"], border_color=C["border"],
            text_color=C["text"], font=ctk.CTkFont(family="Consolas", size=12))
        self.admin_paste_box.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # Action
        act = ctk.CTkFrame(card_in, fg_color="transparent")
        act.pack(fill="x", padx=2, pady=(4, 0))
        ctk.CTkButton(act, text="🔍 Muat & Analisis", height=38, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=self._admin_load).pack(side="left", padx=(0, 8))
        ctk.CTkButton(act, text="▶️  Proses & Simpan VCF", height=38, corner_radius=10,
                      fg_color=C["success"], hover_color=C["success_hover"],
                      text_color="#000", font=ctk.CTkFont(weight="bold"),
                      command=self._admin_process).pack(side="left")

        # ── Extra Admin / Navy (diselipkan ke setiap file) ──
        card_extra = self._card(frame, 2, "➕  Admin / Navy Tambahan (Opsional — Diselipkan ke Setiap File VCF)")
        self.admin_extra_on = ctk.BooleanVar(value=True)
        extra_grid = ctk.CTkFrame(card_extra, fg_color="transparent")
        extra_grid.pack(fill="x", padx=2, pady=(2, 0))
        extra_grid.grid_columnconfigure((0, 1), weight=1)

        for col, (title, attr) in enumerate([
                ("👑 Admin Tambahan (1 per baris):", "admin_extra_admin_box"),
                ("⚓ Navy Tambahan (1 per baris):", "admin_extra_navy_box")]):
            box_frame = ctk.CTkFrame(extra_grid, fg_color="transparent")
            box_frame.grid(row=0, column=col, padx=(0 if col == 0 else 6, 6 if col == 0 else 0), sticky="nsew")
            ctk.CTkLabel(box_frame, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=C["text"]).pack(anchor="w", pady=(0, 2))
            tb = ctk.CTkTextbox(box_frame, height=70, corner_radius=10,
                                fg_color=C["input"], border_color=C["border"],
                                text_color=C["text"], font=ctk.CTkFont(family="Consolas", size=12))
            tb.pack(fill="x")
            setattr(self, attr, tb)
        ctk.CTkLabel(card_extra,
                     text="💡 Opsional: Paste nomor di atas jika ingin diselipkan ke SETIAP file VCF (otomatis diselipkan jika diisi, kosongkan jika tidak perlu).\n"
                          "Nama kontak otomatis mengikuti nama ADMIN / NAVY file masing-masing (contoh: ADMIN A1, NAVY A1).",
                     wraplength=690, justify="left", font=ctk.CTkFont(size=11),
                     text_color=C["text2"]).pack(anchor="w", padx=4, pady=(6, 2))

        # ── Log ──
        card_log = self._card(frame, 3, "📝  Log", expand=True)
        self.admin_log_w = self._make_log(card_log)
        self.admin_log_w.pack(fill="both", expand=True, padx=2)

        self._admin_groups = []

    def _admin_on_drop(self, event):
        path = self._parse_drop_path(event)
        if path and os.path.isfile(path):
            self.admin_file_var.set(path)
            self._admin_drop_label.configure(
                text=f"✅  {os.path.basename(path)}", text_color=C["success"])
            self.admin_tab.set("📂 File / Drag & Drop")

    def _admin_get_lines(self):
        current = self.admin_tab.get()
        if "Paste" in current:
            raw = self.admin_paste_box.get("1.0", "end").strip()
            if not raw:
                messagebox.showwarning("Peringatan", "Paste data terlebih dahulu."); return None
            return [l.strip() for l in raw.splitlines()]
        else:
            path = self.admin_file_var.get().strip()
            if not path or not os.path.isfile(path):
                messagebox.showwarning("Peringatan", "Pilih file TXT yang valid."); return None
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return [l.strip() for l in f.readlines()]

    def _admin_load(self):
        lines = self._admin_get_lines()
        if lines is None:
            return

        self._admin_groups = []
        current = []
        for line in lines:
            line_str = line.strip()
            if line_str == '.':
                if current:
                    self._admin_groups.append(("admin", list(current)))
                    current = []
            elif line_str == ',':
                if current:
                    self._admin_groups.append(("navy", list(current)))
                    current = []
                self._admin_groups.append(("SAVE", []))
            else:
                if line_str:
                    phone, name = parse_contact_line(line_str)
                    cleaned_p = clean_phone_number(phone if phone else line_str)
                    if name:
                        current.append(f"{name} - {cleaned_p}")
                    else:
                        current.append(cleaned_p)
        if current:
            self._admin_groups.append(("remaining", list(current)))

        self._log(self.admin_log_w, f"✅ Dimuat: {len(lines)} baris")
        for gt, cts in self._admin_groups:
            if gt == "SAVE":
                self._log(self.admin_log_w, "   💾 [SAVE FILE]")
            else:
                e = "👑" if gt == "admin" else ("⚓" if gt == "navy" else "📌")
                self._log(self.admin_log_w, f"   {e} {gt.upper()}: {len(cts)} kontak")

    def _admin_process(self):
        if not self._admin_groups:
            # Try loading first
            self._admin_load()
            if not self._admin_groups:
                return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Nama Grup & File")
        dialog.geometry("520x540")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="Tentukan Nama Kontak & File",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=C["text"]).pack(pady=(18, 2))
        ctk.CTkLabel(dialog, text="Masukkan nama untuk setiap grup yang ditemukan",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(pady=(0, 10))

        # Auto fill section
        af_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        af_frame.pack(fill="x", padx=18, pady=(0, 8))
        ctk.CTkLabel(af_frame, text="Auto-fill Kode:", font=ctk.CTkFont(size=12, weight="bold"), text_color=C["text"]).pack(side="left")
        af_entry = ctk.CTkEntry(af_frame, placeholder_text="Kode (misal: A1)", height=28, corner_radius=6, fg_color=C["input"], border_color=C["border"], text_color=C["text"])
        af_entry.pack(side="left", fill="x", expand=True, padx=8)
        af_entry.insert(0, "A1")
        
        scroll = ctk.CTkScrollableFrame(dialog, fg_color=C["bg_card"], corner_radius=12)
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        entries = []
        file_entries = []

        for i, (gt, cts) in enumerate(self._admin_groups):
            if gt == "SAVE":
                row = ctk.CTkFrame(scroll, fg_color=C["sidebar_active"], corner_radius=10)
                row.pack(fill="x", padx=4, pady=3)
                ctk.CTkLabel(row, text=f"💾 Nama File VCF #{len(file_entries)+1}",
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=C["warning"]).pack(side="left", padx=10, pady=8)
                e = ctk.CTkEntry(row, placeholder_text="Nama file (tanpa .vcf)", height=32,
                                 corner_radius=8, fg_color=C["input"], border_color=C["border"],
                                 text_color=C["text"])
                e.pack(side="right", padx=10, pady=8, fill="x", expand=True)
                file_entries.append((i, e))
                entries.append(None)
            else:
                row = ctk.CTkFrame(scroll, fg_color=C["bg_card_hover"], corner_radius=10)
                row.pack(fill="x", padx=4, pady=3)
                lbl = "ADMIN" if gt == "admin" else ("NAVY" if gt == "navy" else "GROUP")
                em = "👑" if gt == "admin" else ("⚓" if gt == "navy" else "📌")
                ctk.CTkLabel(row, text=f"{em} {lbl} ({len(cts)})",
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color=C["text"]).pack(side="left", padx=10, pady=8)
                e = ctk.CTkEntry(row, placeholder_text=f"Nama {lbl}", height=32,
                                 corner_radius=8, fg_color=C["input"], border_color=C["border"],
                                 text_color=C["text"])
                e.pack(side="right", padx=10, pady=8, fill="x", expand=True)
                entries.append(e)

        def do_autofill():
            tag_input = af_entry.get().strip() or "A1"
            file_counts = {}
            f_idx = 0
            for gt, _ in self._admin_groups:
                if gt == "SAVE":
                    f_idx += 1
                else:
                    file_counts[f_idx] = file_counts.get(f_idx, {})
                    file_counts[f_idx][gt] = file_counts[f_idx].get(gt, 0) + 1

            f_idx = 0
            curr_type_idx = {}
            fe_i = 0
            for idx, (gt, _) in enumerate(self._admin_groups):
                tag = get_admin_tag(tag_input, f_idx)
                if gt == "SAVE":
                    counts = file_counts.get(f_idx, {})
                    has_adm = counts.get("admin", 0) > 0
                    has_nvy = counts.get("navy", 0) > 0
                    if has_adm and has_nvy:
                        fname = f"ADMINNAVY {tag}"
                    elif has_adm:
                        fname = f"ADMIN {tag}"
                    elif has_nvy:
                        fname = f"NAVY {tag}"
                    else:
                        fname = f"FILE {tag}"

                    fe = file_entries[fe_i][1]
                    fe.delete(0, "end")
                    fe.insert(0, fname)
                    fe_i += 1
                    f_idx += 1
                    curr_type_idx.clear()
                else:
                    e = entries[idx]
                    if e is not None:
                        curr_type_idx[gt] = curr_type_idx.get(gt, 0) + 1
                        total_of_type = file_counts.get(f_idx, {}).get(gt, 1)
                        suffix = f" {curr_type_idx[gt]}" if total_of_type > 1 else ""
                        if gt == "admin":
                            val = f"ADMIN {tag}{suffix}"
                        elif gt == "navy":
                            val = f"NAVY {tag}{suffix}"
                        else:
                            val = f"GROUP {tag}{suffix}"
                        e.delete(0, "end")
                        e.insert(0, val)

        af_entry.bind("<Return>", lambda _: do_autofill())
        ctk.CTkButton(af_frame, text="Terapkan", width=60, height=28, corner_radius=6,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=do_autofill).pack(side="right")
        do_autofill()

        def go():
            for idx, entry in enumerate(entries):
                if entry is not None and not entry.get().strip():
                    messagebox.showwarning("Peringatan", "Isi semua nama grup!", parent=dialog); return
            for _, fe in file_entries:
                if not fe.get().strip():
                    messagebox.showwarning("Peringatan", "Isi semua nama file!", parent=dialog); return

            output_folder = get_output_folder()
            extra_admin_raw = self.admin_extra_admin_box.get("1.0", "end").strip() if hasattr(self, 'admin_extra_admin_box') else ""
            extra_navy_raw = self.admin_extra_navy_box.get("1.0", "end").strip() if hasattr(self, 'admin_extra_navy_box') else ""

            fe_iter = iter(file_entries)
            total_c = 0
            inv = 0
            current_segment = []
            file_num = 1

            def save_file_segment(fname):
                nonlocal total_c, inv, file_num
                adm_name = None
                nvy_name = None
                for gt, bn, _ in current_segment:
                    if gt == "admin" and not adm_name:
                        adm_name = bn
                    elif gt == "navy" and not nvy_name:
                        nvy_name = bn

                tag_guess = get_admin_tag(af_entry.get().strip() or "A1", file_num - 1)
                if not adm_name:
                    adm_name = f"ADMIN {tag_guess}".strip()
                if not nvy_name:
                    nvy_name = f"NAVY {tag_guess}".strip()

                file_vcf = ""
                extra_added = 0

                # 1. Emit admin group(s) + extra admin
                admin_extra_done = False
                for gt, bn, cts in current_segment:
                    if gt == "admin":
                        for ci, ct in enumerate(cts):
                            phone, custom_name = parse_contact_line(ct)
                            c_phone = clean_phone_number(phone if phone else ct)
                            c_name = custom_name if custom_name else f"{bn} {ci+1:03d}"
                            card, valid = build_vcard(c_name, c_phone)
                            file_vcf += card
                            total_c += 1
                            if not valid: inv += 1
                        if extra_admin_raw and not admin_extra_done:
                            evcf, ecnt, einv = build_extra_vcards(extra_admin_raw, bn, start_index=len(cts)+1)
                            file_vcf += evcf
                            total_c += ecnt
                            inv += einv
                            extra_added += ecnt
                            admin_extra_done = True

                if extra_admin_raw and not admin_extra_done:
                    evcf, ecnt, einv = build_extra_vcards(extra_admin_raw, adm_name, start_index=1)
                    file_vcf += evcf
                    total_c += ecnt
                    inv += einv
                    extra_added += ecnt

                # 2. Emit navy group(s) + extra navy
                navy_extra_done = False
                for gt, bn, cts in current_segment:
                    if gt == "navy":
                        for ci, ct in enumerate(cts):
                            phone, custom_name = parse_contact_line(ct)
                            c_phone = clean_phone_number(phone if phone else ct)
                            c_name = custom_name if custom_name else f"{bn} {ci+1:03d}"
                            card, valid = build_vcard(c_name, c_phone)
                            file_vcf += card
                            total_c += 1
                            if not valid: inv += 1
                        if extra_navy_raw and not navy_extra_done:
                            evcf, ecnt, einv = build_extra_vcards(extra_navy_raw, bn, start_index=len(cts)+1)
                            file_vcf += evcf
                            total_c += ecnt
                            inv += einv
                            extra_added += ecnt
                            navy_extra_done = True

                if extra_navy_raw and not navy_extra_done:
                    evcf, ecnt, einv = build_extra_vcards(extra_navy_raw, nvy_name, start_index=1)
                    file_vcf += evcf
                    total_c += ecnt
                    inv += einv
                    extra_added += ecnt

                # 3. Emit any remaining / other groups
                for gt, bn, cts in current_segment:
                    if gt not in ("admin", "navy"):
                        for ci, ct in enumerate(cts):
                            phone, custom_name = parse_contact_line(ct)
                            c_phone = clean_phone_number(phone if phone else ct)
                            c_name = custom_name if custom_name else f"{bn} {ci+1:03d}"
                            card, valid = build_vcard(c_name, c_phone)
                            file_vcf += card
                            total_c += 1
                            if not valid: inv += 1

                op = os.path.join(output_folder, f"{fname}.vcf")
                c = 1
                while os.path.exists(op):
                    op = os.path.join(output_folder, f"{fname}_{c}.vcf")
                    c += 1
                with open(op, 'w', encoding='utf-8', newline='') as f:
                    f.write(file_vcf)

                extra_note = f" (+{extra_added} nomor tambahan diselipkan)" if extra_added else ""
                self._log(self.admin_log_w, f"💾 Tersimpan: {os.path.basename(op)}{extra_note}")
                current_segment.clear()
                file_num += 1

            for idx, (gt, cts) in enumerate(self._admin_groups):
                if gt == "SAVE":
                    _, fentry = next(fe_iter)
                    fn = fentry.get().strip()
                    save_file_segment(fn)
                else:
                    bn = entries[idx].get().strip()
                    current_segment.append((gt, bn, cts))

            if current_segment:
                save_file_segment("output_sisa")

            self._log(self.admin_log_w, f"\n🎉 {total_c} kontak diproses ({inv} invalid)")
            self._log(self.admin_log_w, f"📁 Output: {output_folder}")
            
            dialog.destroy()
            messagebox.showinfo("Sukses", f"{total_c} kontak diproses.\nOutput: {output_folder}")

        dialog.go = go
        ctk.CTkButton(dialog, text="✅ Proses Sekarang", height=42, corner_radius=10,
                      fg_color=C["success"], hover_color=C["success_hover"],
                      text_color="#000", font=ctk.CTkFont(size=14, weight="bold"),
                      command=go).pack(pady=(6, 14))
        return dialog

    # ──────────────────────────────────────────────────────────
    #  FEATURE 3 : RENAME VCF FILES  (from changename.py)
    #  standalone rename with drag-drop + paste
    # ──────────────────────────────────────────────────────────

    def _build_rename_frame(self):
        frame = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self._frames["rename"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=32, pady=(24, 2), sticky="ew")
        ctk.CTkLabel(hdr, text="Rename VCF Files",
                     font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Rename batch file VCF di vcf_output berdasarkan daftar nama",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(anchor="w", pady=(2, 0))

        # ── Source folder ──
        card_src = self._card(frame, 1, "📂  Folder VCF (sumber)")
        src_row = ctk.CTkFrame(card_src, fg_color="transparent")
        src_row.pack(fill="x", padx=2)

        self.ren_src_var = ctk.StringVar(value=get_output_folder())
        ctk.CTkEntry(src_row, textvariable=self.ren_src_var,
                     height=36, corner_radius=10, fg_color=C["input"],
                     border_color=C["border"], text_color=C["text"]).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(src_row, text="Browse", width=80, height=36, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=self._ren_browse_folder).pack(side="right")

        # Preview files
        self.ren_file_list = ctk.CTkTextbox(
            card_src, height=60, corner_radius=10,
            fg_color=C["input"], border_color=C["border"],
            text_color=C["text2"], font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled")
        self.ren_file_list.pack(fill="x", padx=2, pady=(6, 0))

        ctk.CTkButton(card_src, text="🔄 Scan File VCF", height=32, corner_radius=10,
                      fg_color=C["accent_dim"], hover_color=C["accent"],
                      text_color=C["text"], command=self._ren_scan).pack(anchor="w", padx=2, pady=(6, 0))

        # ── Names ──
        card_names = self._card(frame, 2, "📝  Daftar Nama Baru — File / Drag & Drop / Paste")

        self.ren_name_tab = ctk.CTkTabview(card_names, fg_color=C["bg_card"],
                                            segmented_button_fg_color=C["accent_dim"],
                                            segmented_button_selected_color=C["accent"],
                                            segmented_button_unselected_color=C["border"],
                                            corner_radius=10, height=130)
        self.ren_name_tab.pack(fill="x", padx=2, pady=(0, 4))
        tn_f = self.ren_name_tab.add("📂 File")
        tn_p = self.ren_name_tab.add("📋 Paste")
        tn_g = self.ren_name_tab.add("✨ Generate List")

        self.ren_name_file_var = ctk.StringVar()
        nf_row = ctk.CTkFrame(tn_f, fg_color="transparent")
        nf_row.pack(fill="x", padx=4, pady=8)

        drop_n = ctk.CTkFrame(tn_f, fg_color=C["drop_zone"], corner_radius=10,
                               border_width=2, border_color=C["border"], height=40)
        drop_n.pack(fill="x", padx=4, pady=(0, 4))
        drop_n.pack_propagate(False)
        self._ren_drop_label = ctk.CTkLabel(drop_n, text="🗂️ Drag & drop nama_baru.txt",
                     font=ctk.CTkFont(size=12), text_color=C["text2"])
        self._ren_drop_label.pack(expand=True)
        self._enable_drop(drop_n, self._ren_name_on_drop)
        self._enable_drop(self._ren_drop_label, self._ren_name_on_drop)

        ctk.CTkEntry(nf_row, textvariable=self.ren_name_file_var,
                     placeholder_text="Path file nama_baru.txt …", height=34, corner_radius=10,
                     fg_color=C["input"], border_color=C["border"],
                     text_color=C["text"]).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(nf_row, text="Browse", width=80, height=34, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      command=lambda: self._browse_file(self.ren_name_file_var)).pack(side="right")

        ctk.CTkLabel(tn_p, text="Satu nama per baris:",
                     font=ctk.CTkFont(size=12), text_color=C["text2"]).pack(anchor="w", padx=4, pady=(4, 2))
        self.ren_name_paste = ctk.CTkTextbox(
            tn_p, height=70, corner_radius=10,
            fg_color=C["input"], border_color=C["border"],
            text_color=C["text"], font=ctk.CTkFont(family="Consolas", size=12))
        self.ren_name_paste.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # Generate Tab UI
        g_row = ctk.CTkFrame(tn_g, fg_color="transparent")
        g_row.pack(fill="x", padx=4, pady=8)
        ctk.CTkLabel(g_row, text="Prefix:", font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left")
        self._rn_pref = ctk.CTkEntry(g_row, placeholder_text="Cth: GRUP", width=80, height=30, fg_color=C["input"], border_color=C["border"])
        self._rn_pref.pack(side="left", padx=6)
        self._rn_pref.insert(0, "GRUP")
        
        ctk.CTkLabel(g_row, text="Rentang:", font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left", padx=(10, 0))
        self._rn_start = ctk.CTkEntry(g_row, placeholder_text="1", width=40, height=30, fg_color=C["input"], border_color=C["border"])
        self._rn_start.pack(side="left", padx=4)
        self._rn_start.insert(0, "1")
        ctk.CTkLabel(g_row, text="-", font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left")
        self._rn_end = ctk.CTkEntry(g_row, placeholder_text="5", width=40, height=30, fg_color=C["input"], border_color=C["border"])
        self._rn_end.pack(side="left", padx=4)
        self._rn_end.insert(0, "5")
        
        self.rn_gen_no_space = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(g_row, text="Tanpa Spasi", variable=self.rn_gen_no_space, 
                        font=ctk.CTkFont(size=11), text_color=C["text"], 
                        fg_color=C["accent"], hover_color=C["accent_hover"],
                        border_color=C["border"], width=10).pack(side="left", padx=8)
        
        def _rn_gen():
            try:
                s = int(self._rn_start.get())
                e = int(self._rn_end.get())
                pref = self._rn_pref.get().strip()
                nospace = self.rn_gen_no_space.get()
                lines = [f"{pref}{'' if nospace else ' '}{i}" for i in range(s, e+1)]
                self.ren_name_paste.delete("1.0", "end")
                self.ren_name_paste.insert("end", "\n".join(lines) + "\n")
                self.ren_name_tab.set("📋 Paste")
            except Exception:
                messagebox.showwarning("Peringatan", "Pastikan rentang berupa angka yang valid.")
                
        ctk.CTkButton(g_row, text="Generate", width=70, height=30, corner_radius=8, fg_color=C["accent"], hover_color=C["accent_hover"], command=_rn_gen).pack(side="right", padx=(4, 0))

        # ── Options ──
        opt_row = ctk.CTkFrame(card_names, fg_color="transparent")
        opt_row.pack(fill="x", padx=2, pady=(4, 0))

        self.ren_move = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_row, text="Pindahkan ke folder vcf_output_renamed",
                        variable=self.ren_move, font=ctk.CTkFont(size=12),
                        text_color=C["text"], fg_color=C["accent"],
                        hover_color=C["accent_hover"], border_color=C["border"]).pack(side="left")

        ctk.CTkButton(opt_row, text="✏️  Rename Sekarang", height=40, corner_radius=10,
                      fg_color=C["success"], hover_color=C["success_hover"],
                      text_color="#000", font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._ren_go).pack(side="right")

        # ── Log ──
        card_log = self._card(frame, 3, "📝  Log", expand=True)
        self.ren_log_w = self._make_log(card_log)
        self.ren_log_w.pack(fill="both", expand=True, padx=2)

        self._ren_files = []

    def _ren_browse_folder(self):
        path = filedialog.askdirectory(title="Pilih Folder VCF")
        if path:
            self.ren_src_var.set(path)

    def _ren_name_on_drop(self, event):
        path = self._parse_drop_path(event)
        if path and os.path.isfile(path):
            self.ren_name_file_var.set(path)
            self._ren_drop_label.configure(
                text=f"✅ {os.path.basename(path)}", text_color=C["success"])

    def _ren_scan(self):
        folder = self.ren_src_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Peringatan", "Folder tidak ditemukan."); return

        self._ren_files = sorted(
            [f for f in os.listdir(folder) if f.endswith(".vcf")],
            key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
        )
        self.ren_file_list.configure(state="normal")
        self.ren_file_list.delete("1.0", "end")
        if self._ren_files:
            self.ren_file_list.insert("end", f"Ditemukan {len(self._ren_files)} file VCF:\n")
            for f in self._ren_files:
                self.ren_file_list.insert("end", f"  • {f}\n")
        else:
            self.ren_file_list.insert("end", "Tidak ada file .vcf ditemukan.")
        self.ren_file_list.configure(state="disabled")

    def _ren_go(self):
        folder = self.ren_src_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Peringatan", "Folder sumber tidak valid."); return

        # Get names
        cur = self.ren_name_tab.get()
        if "Paste" in cur or "Generate" in cur:
            raw = self.ren_name_paste.get("1.0", "end").strip()
            if not raw:
                messagebox.showwarning("Peringatan", "Paste daftar nama atau Generate list terlebih dahulu."); return
            names = [l.strip() for l in raw.splitlines() if l.strip()]
        else:
            path = self.ren_name_file_var.get().strip()
            if not path or not os.path.isfile(path):
                messagebox.showwarning("Peringatan", "Pilih file nama."); return
            with open(path, 'r', encoding='utf-8') as f:
                names = [l.rstrip('\n') for l in f if l.strip()]

        if not names:
            messagebox.showwarning("Peringatan", "Daftar nama kosong."); return

        # Scan files
        files = sorted(
            [f for f in os.listdir(folder) if f.endswith(".vcf")],
            key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
        )

        if not files:
            messagebox.showwarning("Peringatan", "Tidak ada file VCF di folder."); return

        if len(names) < len(files):
            self._log(self.ren_log_w,
                f"⚠️ Nama ({len(names)}) < file ({len(files)}). Hanya sebagian di-rename.")

        move = self.ren_move.get()
        dest_folder = folder
        if move:
            dest_folder = os.path.join(os.path.dirname(folder), "vcf_output_renamed")
            os.makedirs(dest_folder, exist_ok=True)

        count = 0
        for fname, new_name in zip(files, names):
            old = os.path.join(folder, fname)
            new = os.path.join(dest_folder, f"{new_name}.vcf")
            try:
                if move:
                    shutil.move(old, new)
                else:
                    os.rename(old, new)
                self._log(self.ren_log_w, f"  📝 {fname} → {new_name}.vcf")
                count += 1
            except Exception as e:
                self._log(self.ren_log_w, f"  ❌ {fname}: {e}")

        self._log(self.ren_log_w, f"\n✅ {count} file di-rename.")
        self._log(self.ren_log_w, f"📁 Output: {dest_folder}")
        messagebox.showinfo("Sukses", f"{count} file berhasil di-rename.\nOutput: {dest_folder}")


# ============================================================
#  Entry Point
# ============================================================

if __name__ == "__main__":
    app = VCFToolsApp()
    app.mainloop()
