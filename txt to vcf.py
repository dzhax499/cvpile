import os
import re

def clean_phone_number(phone_number):
    """Membersihkan nomor telepon dari spasi, strip, atau karakter lain yang tidak perlu."""
    # Hanya ambil digit dan tanda + dari nomor telepon
    cleaned_number = re.sub(r'[^\d+]', '', phone_number)
    return cleaned_number

def vcf_to_txt_multiple(vcf_files, txt_files_count, use_name):
    output_folder = 'txt_output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    total_contacts = []

    # Loop melalui setiap file VCF yang diberikan
    for vcf_file in vcf_files:
        with open(vcf_file, 'r') as vcf:
            contact_name = None
            contact_phone = None

            for line in vcf:
                line = line.strip()

                # Cari baris yang mengandung nama kontak
                if line.startswith("FN:") and use_name:
                    contact_name = line[3:].strip()  # Ambil nama setelah "FN:"

                # Cari baris yang mengandung nomor telepon
                if line.startswith("TEL"):
                    raw_phone_number = re.findall(r'\+?\d[\d\s\-\(\)]*', line)
                    if raw_phone_number:
                        contact_phone = clean_phone_number(raw_phone_number[0])  # Bersihkan nomor telepon dari format

                # Jika sudah mendapat nama dan nomor, simpan ke dalam daftar
                if contact_phone:
                    if use_name and contact_name:
                        total_contacts.append(f"{contact_name}: {contact_phone}")
                    else:
                        total_contacts.append(contact_phone)

                    # Reset untuk kontak berikutnya
                    contact_name = None
                    contact_phone = None

    # Hitung berapa banyak kontak per file txt
    contacts_per_file = len(total_contacts) // txt_files_count
    remainder = len(total_contacts) % txt_files_count  # Jika ada sisa kontak

    contact_index = 0
    for i in range(txt_files_count):
        output_txt = os.path.join(output_folder, f'Fikri {i + 1}.txt')

        with open(output_txt, 'w') as txt_file:
            # Tentukan jumlah kontak yang akan dimasukkan ke file ini
            contacts_in_this_file = contacts_per_file + (1 if i < remainder else 0)

            for _ in range(contacts_in_this_file):
                txt_file.write(total_contacts[contact_index] + '\n')
                contact_index += 1

        print(f"File TXT '{output_txt}' berhasil dibuat di folder '{output_folder}'.")

# Jalankan program
if __name__ == "__main__":
    # Dapatkan direktori di mana skrip dijalankan
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Dapatkan semua file vcf yang ada di direktori yang sama dengan skrip ini
    vcf_files = [os.path.join(script_dir, f) for f in os.listdir(script_dir) if f.endswith('.vcf')]

    if not vcf_files:
        print("Tidak ada file VCF yang ditemukan.")
    else:
        # Minta pengguna untuk memasukkan jumlah file TXT yang ingin dibuat
        txt_files_count = int(input("Masukkan berapa banyak file TXT yang ingin dibuat: "))

        # Tanyakan apakah pengguna ingin menggunakan nama dalam output txt
        use_name = input("Apakah Anda ingin menggunakan nama dalam output (yes/no)? ").strip().lower() == 'yes'

        # Jalankan konversi dari banyak file vcf ke beberapa file txt
        vcf_to_txt_multiple(vcf_files, txt_files_count, use_name)
