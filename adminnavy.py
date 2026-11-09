import os
import re
import phonenumbers
from phonenumbers import geocoder

def is_valid_phone_number(phone_number):
    try:
        phone_number = re.sub(r'\s+|\-|\(|\)', '', phone_number)  # Hapus spasi dan simbol
        phone_obj = phonenumbers.parse(phone_number, None)
        return phonenumbers.is_valid_number(phone_obj)
    except phonenumbers.NumberParseException:
        return False

def detect_country(phone_number):
    try:
        phone_number = re.sub(r'\s+|\-|\(|\)', '', phone_number)  # Hapus spasi dan simbol
        phone_obj = phonenumbers.parse(phone_number, None)
        country = geocoder.description_for_number(phone_obj, "en")
        return country if country else "Unknown"
    except phonenumbers.NumberParseException:
        return "Unknown"

def format_phone_number(phone_number):
    try:
        phone_number = re.sub(r'\s+|\-|\(|\)', '', phone_number)  # Hapus spasi dan simbol
        phone_obj = phonenumbers.parse(phone_number, None)
        formatted_phone = phonenumbers.format_number(phone_obj, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        formatted_phone = re.sub(r'\+(\d{1,3}) (\d{3}) (\d{3})(\d{4})', r'+\1 (\2) \3-\4', formatted_phone)
        return formatted_phone
    except phonenumbers.NumberParseException:
        return phone_number  # Kembalikan nomor asli jika tidak bisa diformat

def txt_to_vcf(input_txt, contacts_per_file, base_vcf_name):
    output_folder = 'vcf_output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_txt, 'r') as txt_file:
        contacts = txt_file.readlines()

    total_contacts = len(contacts)
    contact_counter = 0  # Untuk menghitung jumlah kontak yang telah diproses
    invalid_count = 0  # Untuk menghitung jumlah nomor tidak valid

    file_index = 0  # Indeks file VCF
    while contact_counter < total_contacts:
        # Nama file VCF berdasarkan input pengguna, dengan urutan numerik
        output_vcf = f"{base_vcf_name}_{file_index + 1}.vcf"
        output_vcf_path = os.path.join(output_folder, output_vcf)

        with open(output_vcf_path, 'w') as vcf_file:
            for _ in range(contacts_per_file):
                if contact_counter >= total_contacts:
                    break  # Keluar jika tidak ada lagi kontak

                # Ambil nomor dan nama kontak dari file .txt
                contact_info = contacts[contact_counter].strip().split(maxsplit=1)  # Ambil nomor dan nama
                phone_number = contact_info[0].strip()  # Bersihkan spasi di nomor telepon
                name = contact_info[1].strip() if len(contact_info) > 1 else f"Unknown_{contact_counter}"  # Ambil nama atau beri nama default

                # Tambahkan '+' jika belum ada
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number

                # Validasi nomor telepon
                if is_valid_phone_number(phone_number):
                    # Format nomor telepon
                    formatted_phone_number = format_phone_number(phone_number)

                    # Deteksi negara secara otomatis
                    country = detect_country(phone_number)

                    # Increment kontak counter
                    contact_counter += 1

                    # Buat format VCF untuk setiap kontak yang valid
                    vcf_content = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{formatted_phone_number}
NOTE:Country: {country}
END:VCARD
"""
                    vcf_file.write(vcf_content)
                else:
                    # Tambah hitung untuk nomor tidak valid
                    invalid_count += 1
                    contact_counter += 1  # Tetap lanjutkan ke kontak berikutnya

                    # Tulis entri untuk nomor tidak valid
                    name = f"{name}_INVALID"
                    vcf_content_invalid = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{phone_number}
NOTE:Invalid Number
END:VCARD
"""
                    vcf_file.write(vcf_content_invalid)

        print(f"File VCF '{output_vcf}' berhasil dibuat di folder '{output_folder}'.")
        file_index += 1  # Increment file index

    # Tampilkan jumlah nomor tidak valid
    print(f"Jumlah nomor tidak valid: {invalid_count}")

# Jalankan program
if __name__ == "__main__":
    # Dapatkan direktori di mana skrip dijalankan
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Nama file txt input (harus ada di direktori yang sama dengan kode)
    input_txt = os.path.join(script_dir, 'contacts.txt')

    # Minta pengguna memasukkan jumlah kontak per file VCF yang ingin dibuat
    contacts_per_file = int(input("Masukkan jumlah kontak yang ingin dimasukkan ke setiap file VCF: "))

    # Minta pengguna untuk memasukkan nama file VCF (tanpa ekstensi .vcf)
    base_vcf_name = input("Masukkan nama dasar untuk file VCF (tanpa ekstensi .vcf): ")

    # Jalankan konversi dari txt ke vcf
    txt_to_vcf(input_txt, contacts_per_file, base_vcf_name)