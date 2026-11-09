import argparse
import re
from pathlib import Path

DEFAULT_INPUT = Path("raw_groups.txt")
DEFAULT_OUTPUT = Path("contacts_with_admin.txt")
DEFAULT_ADMIN = "6283164320479"


def extract_groups(text):
    groups = []
    current = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                groups.append(current)
                current = []
            continue

        if line.startswith("[") or line.startswith("【") or line.lower().startswith("admin"):
            continue

        numbers = re.findall(r"\d{9,}", line)
        if numbers:
            current.extend(numbers)
        else:
            continue

    if current:
        groups.append(current)
    return groups


def normalize_group(group, admin_number, replace_existing=None):
    normalized = []
    for number in group:
        if replace_existing and number == replace_existing:
            continue
        normalized.append(number)

    if admin_number not in normalized:
        normalized.append(admin_number)

    return normalized


def format_groups(groups):
    lines = []
    for group in groups:
        for number in group:
            lines.append(number)
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Parse WA group text and add admin number to each group.")
    parser.add_argument("--input", "-i", type=Path, default=DEFAULT_INPUT, help="Path ke file teks sumber.")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Path file output.")
    parser.add_argument("--admin", "-a", default=DEFAULT_ADMIN, help="Nomor admin yang akan ditambahkan ke setiap grup.")
    parser.add_argument("--replace-existing", "-r", default="5515981746370",
                        help="Jika ada nomor admin placeholder lama, ganti dengan nomor admin baru.")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"File input tidak ditemukan: {args.input}")
        return

    text = args.input.read_text(encoding="utf-8")
    groups = extract_groups(text)

    if not groups:
        print("Tidak ada grup kontak yang ditemukan di file input.")
        return

    groups = [normalize_group(group, args.admin, replace_existing=args.replace_existing) for group in groups]
    output_text = format_groups(groups)
    args.output.write_text(output_text, encoding="utf-8")

    print(f"Selesai. {len(groups)} grup diproses dan disimpan ke: {args.output}")
    print(f"- Admin ditambahkan: {args.admin}")
    print(f"- Placeholder lama diganti: {args.replace_existing}")


if __name__ == "__main__":
    main()
