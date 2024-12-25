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
        return formatted_phone
    except phonenumbers.NumberParseException:
        return phone_number  # Kembalikan nomor asli jika tidak bisa diformat

def txt_to_vcf(input_txt, contacts_per_file, base_name):
    output_folder = 'vcf_output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_txt, 'r') as txt_file:
        contacts = [line.strip() for line in txt_file if line.strip()]  # Abaikan baris kosong

    total_contacts = len(contacts)
    contact_counter = 0  # Untuk menghitung jumlah kontak yang telah diproses
    invalid_count = 0  # Untuk menghitung jumlah nomor tidak valid

    file_index = 0  # Indeks file VCF
    name_counter = 1  # Untuk menghitung urutan nama kontak
    while contact_counter < total_contacts:
        # Nama file VCF otomatis dengan prefix "contact_"
        output_vcf = f"XXX {file_index + 1}.vcf"
        output_vcf_path = os.path.join(output_folder, output_vcf)

        with open(output_vcf_path, 'w') as vcf_file:
            for _ in range(contacts_per_file):
                if contact_counter >= total_contacts:
                    break  # Keluar jika tidak ada lagi kontak

                # Ambil nomor dan nama kontak dari file .txt
                contact_info = contacts[contact_counter].split(maxsplit=1)  # Ambil nomor dan nama

                # Periksa jika contact_info kosong atau tidak memiliki data yang cukup
                if not contact_info or len(contact_info) < 1:
                    contact_counter += 1  # Lanjutkan ke baris berikutnya
                    continue  # Lewati baris kosong atau tidak valid

                phone_number = contact_info[0].strip()  # Bersihkan spasi di nomor telepon
                name = f"{base_name} {name_counter:03}"  # Format nama kontak dengan urutan, misal "REY 001"
                name_counter += 1

                # Tambahkan '+' jika belum ada
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number

                # Validasi nomor telepon
                if is_valid_phone_number(phone_number):
                    # Format nomor telepon
                    formatted_phone_number = format_phone_number(phone_number)

                    # Deteksi negara secara otomatis
                    country = detect_country(phone_number)

                    # Buat format VCF untuk setiap kontak yang valid
                    vcf_content = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{formatted_phone_number}
NOTE:Country: {country}
END:VCARD
"""
                else:
                    # Tambah hitung untuk nomor tidak valid
                    invalid_count += 1

                    # Buat entri untuk nomor tidak valid
                    vcf_content = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{phone_number}
NOTE:Invalid Number
END:VCARD
"""
                
                # Tulis vcf_content ke file
                vcf_file.write(vcf_content)
                contact_counter += 1  # Increment kontak counter untuk setiap kontak

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

    # Minta pengguna memasukkan nama dasar untuk kontak
    base_name = input("Masukkan nama dasar untuk kontak (misal 'REY'): ")

    # Jalankan konversi dari txt ke vcf
    txt_to_vcf(input_txt, contacts_per_file, base_name)
