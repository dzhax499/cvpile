import random
import time

# Fungsi animasi umum untuk menampilkan animasi angka acak
def animasi_angka(teks, durasi=3):
    print(teks)
    
    angka_terpilih = random.randint(0, 36)  # Angka akhir yang akan muncul
    for _ in range(durasi * 10):
        angka_acak = random.randint(0, 36)
        print(f"Angka: {angka_acak}", end='\r')
        time.sleep(0.1)
    return angka_terpilih

# Fungsi animasi umum untuk menampilkan animasi warna acak
def animasi_warna(teks, durasi=3):
    print(teks)
    
    warna_terpilih = random.choice(['merah', 'hitam'])
    for _ in range(durasi * 10):
        warna_acak = random.choice(['merah', 'hitam'])
        print(f"Warna: {warna_acak}", end='\r')
        time.sleep(0.1)
    return warna_terpilih

# Fungsi animasi besar/kecil
def animasi_besar_kecil(teks, durasi=3):
    print(teks)
    
    angka_terpilih = random.randint(0, 36)  # Angka akhir yang akan muncul
    for _ in range(durasi * 10):
        angka_acak = random.randint(0, 36)
        kategori = 'kecil' if angka_acak <= 18 else 'besar'
        print(f"Angka: {angka_acak} | Kategori: {kategori}", end='\r')
        time.sleep(0.1)
    return angka_terpilih

# Fungsi pengecekan kategori besar/kecil
def cek_besar_kecil(angka):
    if 1 <= angka <= 18:
        return 'kecil'
    elif 19 <= angka <= 36:
        return 'besar'
    else:
        return 'nol'

# Fungsi utama permainan roulette
def roulette(saldo):
    print("Permainan Roulette")
    taruhan = int(input("Masukkan jumlah taruhan: "))

    if taruhan > saldo:
        print("Saldo tidak cukup.")
        return saldo

    print("Pilih jenis taruhan:")
    print("1. Tebak angka (0-36)")
    print("2. Tebak warna (merah/hitam)")
    print("3. Tebak besar/kecil (1-18: kecil, 19-36: besar)")
    pilihan = input("Masukkan pilihan taruhan (1/2/3): ").strip()

    # Proses berdasarkan pilihan taruhan
    if pilihan == "1":
        angka_tebakan = int(input("Masukkan angka tebakan (0-36): "))
        print("Memutar roda untuk angka...")
        angka_akhir = animasi_angka("Roda berputar untuk angka...", durasi=5)

        if angka_tebakan == angka_akhir:
            print(f"Selamat! Anda menang angka! Angka yang keluar adalah {angka_akhir}.")
            saldo += taruhan * 35  # Pembayaran untuk angka
        else:
            print(f"Anda kalah angka. Angka yang keluar adalah {angka_akhir}.")
            saldo -= taruhan

    elif pilihan == "2":
        warna_tebakan = input("Masukkan tebakan warna (merah/hitam): ").lower()
        print("Memutar roda untuk warna...")
        warna_akhir = animasi_warna("Roda berputar untuk warna...", durasi=5)

        if warna_tebakan == warna_akhir:
            print(f"Selamat! Anda menang warna! Warna yang keluar adalah {warna_akhir}.")
            saldo += taruhan  # Pembayaran untuk warna
        else:
            print(f"Anda kalah warna. Warna yang keluar adalah {warna_akhir}.")
            saldo -= taruhan

    elif pilihan == "3":
        besar_kecil_tebakan = input("Masukkan tebakan (besar/kecil): ").lower()
        print("Memutar roda untuk besar/kecil...")
        angka_akhir = animasi_besar_kecil("Roda berputar untuk besar/kecil...", durasi=5)
        hasil_besar_kecil = cek_besar_kecil(angka_akhir)

        if besar_kecil_tebakan == hasil_besar_kecil:
            print(f"Selamat! Anda menang tebakan besar/kecil ({hasil_besar_kecil})!")
            saldo += taruhan  # Pembayaran untuk besar/kecil
        else:
            print(f"Anda kalah tebakan besar/kecil. Angka yang keluar adalah {angka_akhir}, kategori {hasil_besar_kecil}.")
            saldo -= taruhan

    else:
        print("Pilihan tidak valid.")

    print(f"Saldo Anda sekarang: {saldo}")
    return saldo

# Fungsi utama untuk menjalankan permainan casino
def main():
    saldo = 1000  # Saldo awal pemain
    print("Selamat datang di Casino Python!")
    print(f"Saldo awal Anda: {saldo}")

    while True:
        print("\n--- Menu Casino ---")
        print("1. Roulette")
        print("2. Keluar")
        pilihan = input("Pilih permainan (1/2): ")

        if pilihan == "1":
            saldo = roulette(saldo)
        elif pilihan == "2":
            print(f"Terima kasih telah bermain di casino! Saldo akhir Anda: {saldo}")
            break
        else:
            print("Pilihan tidak valid.")

        # Jika saldo habis, permainan selesai
        if saldo <= 0:
            print("Saldo Anda habis! Permainan selesai.")
            break

# Menjalankan program utama
if __name__ == "__main__":
    main()
