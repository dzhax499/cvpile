# Fungsi untuk membaca file txt dan memeriksa duplikasi nomor telepon
def cek_duplikasi_nomor(file_path):
    try:
        with open(file_path, 'r') as file:
            # Membaca semua baris dalam file
            lines = file.readlines()

        # Membuat set untuk melacak nomor yang sudah ditemukan
        nomor_telepon = set()
        duplikat = set()

        # Memproses setiap baris (dan nomor) di file
        for line in lines:
            # Membersihkan whitespace dan newline, serta memeriksa jika bukan baris kosong
            nomor = line.strip()
            if nomor:
                # Jika nomor sudah ada di set, berarti duplikat
                if nomor in nomor_telepon:
                    duplikat.add(nomor)
                else:
                    nomor_telepon.add(nomor)

        if duplikat:
            print(f"Nomor telepon duplikat ditemukan: {', '.join(duplikat)}")
        else:
            print("Tidak ada nomor telepon yang duplikat.")

    except FileNotFoundError:
        print("File tidak ditemukan. Periksa kembali jalur file.")

# Panggil fungsi dengan nama file txt yang ada di folder yang sama
cek_duplikasi_nomor('nomor_telepon.txt')
