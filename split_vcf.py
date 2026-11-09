import os
from pathlib import Path


def read_vcf_records(vcf_path):
    records = []
    current_record = []
    inside_vcard = False

    with open(vcf_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n\r")
            if line.strip().upper() == "BEGIN:VCARD":
                inside_vcard = True
                current_record = [line]
                continue

            if inside_vcard:
                current_record.append(line)
                if line.strip().upper() == "END:VCARD":
                    records.append("\n".join(current_record) + "\n")
                    inside_vcard = False
                    current_record = []

    return records


def write_split_vcfs(records, chunk_size, output_folder, base_name):
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)

    files_created = []
    for index in range(0, len(records), chunk_size):
        chunk = records[index:index + chunk_size]
        part_number = index // chunk_size + 1
        output_filename = f"{base_name}_part{part_number}.vcf"
        output_path = output_folder_path / output_filename
        with output_path.open("w", encoding="utf-8", newline="\n") as out_file:
            out_file.writelines(chunk)
        files_created.append(output_path)
        print(f"Created {output_filename} ({len(chunk)} contacts)")

    return files_created


def choose_vcf_file(vcf_files):
    if len(vcf_files) == 1:
        print(f"Detected single VCF file: {vcf_files[0].name}")
        return vcf_files[0]

    print("Multiple VCF files found:")
    for idx, file in enumerate(vcf_files, start=1):
        print(f"{idx}. {file.name}")

    while True:
        choice = input("Pilih nomor file VCF yang ingin dibagi: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(vcf_files):
            return vcf_files[int(choice) - 1]
        print("Pilihan tidak valid. Masukkan angka yang benar.")


def ask_with_default(prompt, default):
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer if answer else default


def main():
    script_folder = Path(__file__).resolve().parent
    default_vcf_folder = script_folder / "split_vcf"

    if default_vcf_folder.exists() and default_vcf_folder.is_dir():
        vcf_folder = default_vcf_folder
        print(f"Menggunakan folder VCF otomatis: {vcf_folder}")
    else:
        current_folder = Path.cwd()
        print(f"Folder default 'split_vcf' tidak ditemukan. Folder kerja saat ini: {current_folder}")
        folder_input = input("Masukkan folder tempat file VCF (tekan Enter untuk folder saat ini): ").strip()
        if folder_input:
            vcf_folder = Path(folder_input).expanduser()
        else:
            vcf_folder = current_folder

    if not vcf_folder.exists() or not vcf_folder.is_dir():
        raise SystemExit(f"Folder tidak ditemukan: {vcf_folder}")

    vcf_files = sorted(vcf_folder.glob("*.vcf"))
    if not vcf_files:
        raise SystemExit(f"Tidak ada file VCF ditemukan di folder: {vcf_folder}")

    print(f"Ditemukan {len(vcf_files)} file VCF di folder {vcf_folder}.")
    chunk_size_input = ask_with_default("Masukkan jumlah kontak per file VCF", "100")

    try:
        chunk_size = int(chunk_size_input)
        if chunk_size <= 0:
            raise ValueError
    except ValueError:
        raise SystemExit("Jumlah kontak per file harus berupa angka positif.")

    current_folder = Path.cwd()
    default_output_folder = current_folder / "vcf_split_output"
    output_folder_input = ask_with_default("Masukkan folder output untuk file hasil split", str(default_output_folder))
    output_folder = Path(output_folder_input).expanduser()

    total_files_created = 0
    for input_path in vcf_files:
        base_name = input_path.stem
        records = read_vcf_records(input_path)
        if not records:
            print(f"Peringatan: Tidak ditemukan rekord VCF di file: {input_path.name}. Lewati file ini.")
            continue

        print(f"\nMemproses file: {input_path.name}")
        print(f"Ditemukan {len(records)} kontak.")
        print(f"Membagi menjadi file VCF dengan maksimal {chunk_size} kontak per file...")

        files_created = write_split_vcfs(records, chunk_size, output_folder, base_name)
        total_files_created += len(files_created)

    print(f"\nSelesai. Total {total_files_created} file VCF dibuat di folder '{output_folder}'.")


if __name__ == "__main__":
    main()
