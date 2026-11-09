import os

def merge_txt_files(input_folder, output_file):
    try:
        # Mengambil daftar file .txt dan mengurutkannya secara ascending
        txt_files = sorted([f for f in os.listdir(input_folder) if f.endswith('.txt')])

        with open(output_file, 'w', encoding='utf-8') as outfile:
            for filename in txt_files:
                file_path = os.path.join(input_folder, filename)
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())

        print(f"Semua file .txt berhasil digabungkan ke {output_file}")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

# Masukkan path folder yang berisi file .txt dan nama file output
folder_path = "D:/cvvcf/gabung"  # Ganti dengan path ke folder Anda
output_file_name = "gabungan.txt"

merge_txt_files(folder_path, output_file_name)