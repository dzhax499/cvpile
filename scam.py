def buat_file_berurutan():
    jumlah_file = int(input("Masukkan jumlah file yang ingin dibuat: "))
    teks_dasar = input("Masukkan teks dasar yang ingin disimpan: ")
    jumlah_baris = int(input("Masukkan jumlah baris untuk setiap file: "))
    nama_file_dasar = input("Masukkan nama dasar file (tanpa ekstensi): ")
    
    for nomor_file in range(1, jumlah_file + 1):
        nama_file_lengkap = f"{nama_file_dasar}_{nomor_file}.txt"
        
        try:
            with open(nama_file_lengkap, 'w') as file:
                for i in range(1, jumlah_baris + 1):
                    file.write(f"{i}. {teks_dasar} - File {nomor_file}, Baris {i}\n")
            print(f"File {nama_file_lengkap} berhasil dibuat dengan {jumlah_baris} baris.")
        except Exception as e:
            print(f"Terjadi kesalahan saat membuat file ke-{nomor_file}: {e}")

if __name__ == "__main__":
    buat_file_berurutan()