import os
import re
import phonenumbers
from phonenumbers import geocoder

def is_valid_phone_number(phone_number):
    try:
        phone_obj = phonenumbers.parse(phone_number, None)
        return phonenumbers.is_valid_number(phone_obj)
    except phonenumbers.NumberParseException:
        return False

def detect_country(phone_number):
    try:
        phone_obj = phonenumbers.parse(phone_number, None)
        country = geocoder.description_for_number(phone_obj, "en")
        return country if country else "Unknown"
    except phonenumbers.NumberParseException:
        return "Unknown"

def format_phone_number(phone_number):
    try:
        phone_obj = phonenumbers.parse(phone_number, None)
        formatted_phone = phonenumbers.format_number(phone_obj, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        formatted_phone = re.sub(r'\+(\d{1,3}) (\d{3}) (\d{3})(\d{4})', r'+\1 (\2) \3-\4', formatted_phone)
        return formatted_phone
    except phonenumbers.NumberParseException:
        return phone_number  # Kembalikan nomor asli jika tidak bisa diformat

def txt_to_vcf(input_txt, contacts_per_file):
    output_folder = 'vcf_output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_txt, 'r') as txt_file:
        contacts = txt_file.readlines()

    total_contacts = len(contacts)
    contact_counter = 0  # Untuk menghitung jumlah kontak yang telah diproses
    invalid_count = 0  # Untuk menghitung jumlah nomor tidak valid
    base_name = input("Masukkan nama untuk kontak: ")  # Minta nama satu kali di awal

    file_index = 0  # Indeks file VCF
    while contact_counter < total_contacts:
        output_vcf = f"File_{file_index + 1}.vcf"
        output_vcf_path = os.path.join(output_folder, output_vcf)

        with open(output_vcf_path, 'w') as vcf_file:
            # Reset nomor urut untuk setiap file
            file_contact_counter = 1

            for _ in range(contacts_per_file):
                if contact_counter >= total_contacts:
                    break  # Keluar jika tidak ada lagi kontak

                phone_number = contacts[contact_counter].strip()  # Hanya ambil nomor telepon

                # Tambahkan '+' jika belum ada
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number

                # Validasi nomor telepon
                if is_valid_phone_number(phone_number):
                    # Format nomor telepon
                    formatted_phone_number = format_phone_number(phone_number)

                    # Deteksi negara secara otomatis
                    country = detect_country(phone_number)

                    # Buat nama dengan penomoran berurutan
                    name = f"{base_name}_{str(file_contact_counter).zfill(3)}"
                    file_contact_counter += 1  # Increment nomor urut untuk file ini

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
                    name = f"{base_name}_{str(file_contact_counter).zfill(3)}_INVALID"
                    vcf_content_invalid = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{phone_number}
NOTE:Invalid Number
END:VCARD
"""
                    vcf_file.write(vcf_content_invalid)

                contact_counter += 1  # Increment the main contact counter for total contacts

        print(f"File VCF '{output_vcf}' berhasil dibuat di folder '{output_folder}'.")
        file_index += 1  # Increment file index

    # Tampilkan jumlah nomor tidak valid
    print(f"Jumlah nomor tidak valid: {invalid_count}")

# Fungsi untuk mendeteksi file txt di direktori saat ini
def detect_txt_file():
    txt_files = [f for f in os.listdir() if f.endswith('.txt')]
    if len(txt_files) == 0:
        print("Tidak ada file .txt yang ditemukan di direktori saat ini.")
        return None
    elif len(txt_files) == 1:
        return txt_files[0]
    else:
        print("Beberapa file .txt terdeteksi:")
        for idx, file_name in enumerate(txt_files):
            print(f"{idx + 1}. {file_name}")
        selected_idx = int(input("Pilih nomor file yang akan digunakan: ")) - 1
        return txt_files[selected_idx]

# Jalankan program
if __name__ == "__main__":
    # Dapatkan file txt secara otomatis
    input_txt = detect_txt_file()
    
    if input_txt:
        contacts_per_file = int(input("Masukkan jumlah kontak per file VCF: "))
        txt_to_vcf(input_txt, contacts_per_file)
    else:
        print("Proses dihentikan karena tidak ada file .txt yang dipilih.")
