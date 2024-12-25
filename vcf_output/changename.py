import os
import shutil
import re

def batch_rename_vcf_from_file(src_folder, dest_folder, name_file_path):
    # Cek apakah folder asal, tujuan, dan file nama baru ada
    if not os.path.isdir(src_folder):
        print("Folder asal tidak ditemukan.")
        return
    if not os.path.isdir(dest_folder):
        os.makedirs(dest_folder)
        print(f"Folder tujuan '{dest_folder}' dibuat.")
    if not os.path.isfile(name_file_path):
        print("File nama baru tidak ditemukan.")
        return

    # Baca daftar nama baru dari file teks dengan encoding 'utf-8' tanpa membersihkan karakter
    with open(name_file_path, 'r', encoding='utf-8') as f:
        new_names = [line.rstrip('\n') for line in f if line.strip()]

    # Dapatkan daftar file .vcf yang ingin diubah namanya, dan urutkan berdasarkan angka dalam nama
    files = sorted(
        [file for file in os.listdir(src_folder) if file.endswith(".vcf")],
        key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
    )

    # Pastikan ada cukup nama baru untuk mengganti semua file .vcf di folder
    if len(new_names) < len(files):
        print("Jumlah nama baru di file teks tidak cukup untuk semua file .vcf di folder.")
        return

    # Ubah nama setiap file .vcf sesuai urutan dalam daftar nama baru dan pindahkan ke folder tujuan
    for filename, new_name in zip(files, new_names):
        # Buat nama file baru dengan ekstensi .vcf
        new_filename = f"{new_name}.vcf"

        # Buat path lengkap untuk file lama dan file baru
        old_file = os.path.join(src_folder, filename)
        new_file = os.path.join(dest_folder, new_filename)

        # Pindahkan file ke folder tujuan dengan nama baru
        shutil.move(old_file, new_file)
        print(f'Mengganti nama dan memindahkan "{filename}" menjadi "{new_filename}" ke folder tujuan.')

# Contoh penggunaan dengan path yang diinginkan
src_folder = "D:/cvvcf/vcf_output"  # Lokasi folder asal berisi file .vcf
dest_folder = "D:/cvvcf/vcf_output_renamed"  # Lokasi folder tujuan untuk file yang diubah namanya
name_file_path = "D:/cvvcf/nama_baru.txt"  # Lokasi file teks berisi nama baru
batch_rename_vcf_from_file(src_folder, dest_folder, name_file_path)
