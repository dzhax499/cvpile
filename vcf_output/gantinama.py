import os
import re

def batch_rename_vcf_from_file(folder_path, name_file_path):
    # Cek apakah folder dan file nama baru ada
    if not os.path.isdir(folder_path):
        print("Folder tidak ditemukan.")
        return
    if not os.path.isfile(name_file_path):
        print("File nama baru tidak ditemukan.")
        return

    # Baca daftar nama baru dari file teks dengan encoding 'utf-8' tanpa membersihkan karakter
    with open(name_file_path, 'r', encoding='utf-8') as f:
        new_names = [line.rstrip('\n') for line in f if line.strip()]

    # Dapatkan daftar file .vcf yang ingin diubah namanya, dan urutkan berdasarkan angka dalam nama
    files = sorted(
        [file for file in os.listdir(folder_path) if file.endswith(".vcf")],
        key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
    )

    # Pastikan ada cukup nama baru untuk mengganti semua file .vcf di folder
    if len(new_names) < len(files):
        print("Jumlah nama baru di file teks tidak cukup untuk semua file .vcf di folder.")
        return

    # Ubah nama setiap file .vcf sesuai urutan dalam daftar nama baru
    for filename, new_name in zip(files, new_names):
        # Buat nama file baru dengan ekstensi .vcf
        new_filename = f"{new_name}.vcf"

        # Buat path lengkap untuk file lama dan file baru
        old_file = os.path.join(folder_path, filename)
        new_file = os.path.join(folder_path, new_filename)

        # Ubah nama file
        os.rename(old_file, new_file)
        print(f'Mengganti "{filename}" menjadi "{new_filename}"')

# Contoh penggunaan dengan path yang diinginkan
folder_path = "D:/cvvcf/vcf_output"  # Lokasi folder berisi file .vcf
name_file_path = "D:/cvvcf/nama_baru.txt"  # Lokasi file teks berisi nama baru
batch_rename_vcf_from_file(folder_path, name_file_path)
