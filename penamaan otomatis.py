import os
import re

def clean_phone_number(phone_number):
    """Membersihkan nomor telepon dari spasi, strip, atau karakter lain yang tidak perlu."""
    cleaned_number = re.sub(r'[^\d+]', '', phone_number)
    return cleaned_number

def txt_to_vcf_multiple(txt_file, vcf_files_count, base_name):
    output_folder = 'vcf_output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    contacts = []

    # Membaca kontak dari file .txt
    with open(txt_file, 'r') as f:
        for line in f:
            # Menghilangkan spasi atau karakter kosong di awal dan akhir
            line = line.strip()
            if line:
                contact = line.split(maxsplit=1)  # Split nomor dan nama
                if len(contact) == 2:
                    phone_number, name = contact
                else:
                    phone_number = contact[0]
                    name = None

                phone_number = clean_phone_number(phone_number)
                contacts.append((phone_number, name))

    # Hitung berapa banyak kontak per file .vcf
    contacts_per_file = len(contacts) // vcf_files_count
    remainder = len(contacts) % vcf_files_count  # Untuk sisa kontak jika tidak merata

    contact_index = 0
    for i in range(vcf_files_count):
        # Buat nama file dengan format "(1) DOW", "(2) DOW", dst.
        output_vcf = os.path.join(output_folder, f'({i + 1}) {base_name}.vcf')

        with open(output_vcf, 'w') as vcf_file:
            vcf_file.write("BEGIN:VCARD\nVERSION:3.0\n")

            # Tentukan jumlah kontak yang akan dimasukkan ke file ini
            contacts_in_this_file = contacts_per_file + (1 if i < remainder else 0)

            for _ in range(contacts_in_this_file):
                phone_number, name = contacts[contact_index]
                
                if not name:
                    name = f"{base_name}_{i+1}_{contact_index+1}"  # Buat nama jika tidak ada
                
                vcf_file.write(f"FN:{name}\n")
                vcf_file.write(f"TEL;TYPE=CELL:+{phone_number}\n")
                vcf_file.write("END:VCARD\n")
                
                contact_index += 1

        print(f"File VCF '{output_vcf}' berhasil dibuat di folder '{output_folder}'.")

# Jalankan program
if __name__ == "__main__":
    # Dapatkan file TXT di direktori yang sama dengan kode ini secara otomatis
    txt_file = None
    for file in os.listdir():
        if file.endswith('.txt'):
            txt_file = file
            break

    if not txt_file:
        print("File TXT tidak ditemukan di direktori yang sama.")
    else:
        print(f"File TXT '{txt_file}' ditemukan.")

        # Minta pengguna untuk memasukkan jumlah file VCF yang ingin dibuat
        vcf_files_count = int(input("Masukkan berapa banyak file VCF yang ingin dibuat: "))

        # Minta pengguna untuk memasukkan nama dasar untuk file VCF
        base_name = input("Masukkan nama dasar file VCF (contoh: DOW): ").strip()

        # Jalankan konversi dari txt ke beberapa file vcf
        txt_to_vcf_multiple(txt_file, vcf_files_count, base_name)
