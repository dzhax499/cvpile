# VCF Tools Desktop Suite

Aplikasi desktop GUI modern berbasis **CustomTkinter** untuk konversi, pengelolaan, penamaan otomatis, dan pembuatan file kontak **VCF (vCard 3.0)** secara cepat dan efisien.

---

## Fitur Utama

### 1. Bulk VCF Converter
- **Multi-TXT Batch Upload**: Mendukung upload dan pemrosesan banyak file TXT sekaligus secara otomatis.
- **Custom Split Chunk**: Membagi kontak per file dengan jumlah tetap (misal: `1000`) atau pembagian kustom dipisah koma (misal: `2000,2000,1000`).
- **Opsi Nama-Nomor**: Otomatis menggabungkan nama kontak input program dengan nomor telepon tanpa spasi di sekitar tanda `-` (contoh: `REY-081234567890`).
- **Mode Tanpa Nama**: Opsi kontak hanya berisi nomor telepon tanpa nama (`FN:08123...`).
- **Live Preview & Validasi Nomor**: Validasi nomor internasional langsung via library `phonenumbers`.

### 2. VCF ke TXT
- Konversi cepat file VCF menjadi daftar kontak TXT rapi.
- Ekstraksi nama dan nomor telepon secara otomatis.

### 3. TXT ke XLSX
- Konversi nomor kontak TXT ke format spreadsheet Excel (.xlsx).
- Sanitasi karakter dan proteksi formula injection (`=`, `+`, `-`, `@`).

### 4. Admin VCF Creator
- **Pemisah Grup Pintar**: Gunakan tanda titik `.` untuk memisahkan grup **ADMIN** dan tanda koma `,` untuk grup **NAVY** sekaligus penanda simpan file.
- **Auto-Fill Kode Naming**: Otomatis menghasilkan nama grup dan file sequential (misal: kode `A1` menghasilkan `ADMIN A1`, `NAVY A1`, dan file `ADMINNAVY A1.vcf`).
- **Regex & Pembersihan Nomor Otomatis**: Mendeteksi pola nomor lokal Indonesia `0821xxx` / `08xxx` dan merapikannya ke format standar internasional `628xxxx`, serta otomatis menghapus spasi (` `), tanda minus (`-`), titik, dan tanda kurung.
- **Selip Nomor Admin & Navy Tambahan**: Fitur opsional untuk menyelipkan nomor admin atau navy tambahan ke setiap file VCF yang dibuat, dengan penomoran urut otomatis.

### 5. Rename VCF Files
- Mengganti nama file-file VCF secara massal dengan prefix atau pola nama yang seragam.

### 6. Session Cache (30 Menit)
- Otomatis menyimpan status input, form, dan tab terakhir saat aplikasi ditutup.
- Jika dibuka kembali dalam kurun waktu 30 menit, seluruh data akan dipulihkan secara otomatis. Cache otomatis kedaluwarsa setelah 30 menit.

---

## Persyaratan Sistem

- Python 3.9+
- Windows / macOS / Linux

## Instalasi

1. Clone repositori ini:
   ```bash
   git clone https://github.com/dzhax499/vcf-tools-desktop.git
   cd vcf-tools-desktop
   ```

2. Buat virtual environment (opsional namun disarankan):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   ```

3. Pasang dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Menjalankan Aplikasi

```bash
python app_desktop.py
```

## Menjalankan Pengujian

Suite pengujian otomatis dapat dijalankan dengan:
```bash
python -m unittest test_app_desktop.py test_vcf_txt_tools.py test_xlsx_tools.py
```

---

## Lisensi
MIT License
