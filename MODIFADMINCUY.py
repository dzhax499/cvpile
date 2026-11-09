import os
import re
import phonenumbers
from phonenumbers import geocoder

def is_valid_phone_number(phone_number):
    try:
        phone_number = re.sub(r'\s+|\-|\(|\)', '', phone_number)
        phone_obj = phonenumbers.parse(phone_number, None)
        return phonenumbers.is_valid_number(phone_obj)
    except phonenumbers.NumberParseException:
        return False

def detect_country(phone_number):
    try:
        phone_number = re.sub(r'\s+|\-|\(|\)', '', phone_number)
        phone_obj = phonenumbers.parse(phone_number, None)
        return geocoder.description_for_number(phone_obj, "en") or "Unknown"
    except phonenumbers.NumberParseException:
        return "Unknown"

def format_phone_number(phone_number):
    try:
        phone_number = re.sub(r'\s+|\-|\(|\)', '', phone_number)
        phone_obj = phonenumbers.parse(phone_number, None)
        formatted_phone = phonenumbers.format_number(phone_obj, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        formatted_phone = re.sub(r'\+(\d{1,3}) (\d{3}) (\d{3})(\d{4})', r'+\1 (\2) \3-\4', formatted_phone)
        return formatted_phone
    except phonenumbers.NumberParseException:
        return phone_number

def save_vcf_file(output_folder, file_name, vcf_content):
    counter = 1
    # Clean filename from invalid characters
    file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
    output_path = os.path.join(output_folder, f"{file_name}.vcf")
    
    while os.path.exists(output_path):
        output_path = os.path.join(output_folder, f"{file_name}_{counter}.vcf")
        counter += 1
    
    with open(output_path, 'w', encoding='utf-8') as vcf_file:
        vcf_file.write(vcf_content)
    print(f"File '{os.path.basename(output_path)}' berhasil dibuat di '{output_folder}'.")

def process_group(contacts, contact_name_base, use_numbering=True):
    vcf_content = ""
    for idx, contact in enumerate(contacts):
        phone_number = contact.strip()
        
        if use_numbering:
            contact_name = f"{contact_name_base} {idx + 1:03d}"
        else:
            contact_name = f"{contact_name_base} {idx + 1}"

        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number

        if is_valid_phone_number(phone_number):
            formatted_phone_number = format_phone_number(phone_number)
            country = detect_country(phone_number)
            vcf_content += f"""BEGIN:VCARD
VERSION:3.0
FN:{contact_name}
TEL;TYPE=CELL:{formatted_phone_number}
NOTE:Country: {country}
END:VCARD
"""
        else:
            vcf_content += f"""BEGIN:VCARD
VERSION:3.0
FN:{contact_name}
TEL;TYPE=CELL:{phone_number}
NOTE:Invalid Number
END:VCARD
"""
    return vcf_content

def read_name_file(name_file_path):
    """
    Membaca file nama untuk grup dan file VCF
    Format: satu baris = satu nama grup/file
    """
    try:
        with open(name_file_path, 'r', encoding='utf-8') as file:
            names = [line.strip() for line in file.readlines() if line.strip()]
        return names
    except FileNotFoundError:
        print(f"File nama '{name_file_path}' tidak ditemukan.")
        return []
    except Exception as e:
        print(f"Error membaca file nama: {e}")
        return []

def parse_contacts_file(contacts_file_path):
    """
    Parse file contacts.txt dengan format lama (menggunakan delimiter . dan ,)
    Mengembalikan list grup dengan nomor telepon
    """
    try:
        with open(contacts_file_path, 'r', encoding='utf-8') as file:
            lines = [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"File kontak '{contacts_file_path}' tidak ditemukan.")
        return []
    except Exception as e:
        print(f"Error membaca file kontak: {e}")
        return []

    groups = []
    current_contacts = []
    group_type = "NAVY"  # Default tipe grup
    
    for line in lines:
        if line == '.':
            # ADMIN group
            if current_contacts:
                groups.append({
                    'type': 'ADMIN',
                    'contacts': current_contacts[:]
                })
                current_contacts = []
                
        elif line == ',':
            # NAVY group - simpan grup
            if current_contacts:
                groups.append({
                    'type': 'NAVY',
                    'contacts': current_contacts[:]
                })
                current_contacts = []
        else:
            # Nomor telepon
            if line:
                current_contacts.append(line)
    
    # Handle contacts terakhir jika ada
    if current_contacts:
        groups.append({
            'type': 'NAVY',
            'contacts': current_contacts
        })
    
    return groups

def process_dual_file_vcf(contacts_file, names_file, config):
    """
    Proses VCF dengan dua file: contacts.txt dan namectc.txt
    """
    # Baca file kontak
    contact_groups = parse_contacts_file(contacts_file)
    if not contact_groups:
        print("Tidak ada grup kontak yang ditemukan!")
        return
    
    # Baca file nama
    group_names = read_name_file(names_file)
    if not group_names:
        print("Tidak ada nama grup yang ditemukan!")
        return
    
    # Setup output folder
    output_folder = config['output_folder']
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Tampilkan informasi
    print(f"\nDitemukan {len(contact_groups)} grup kontak")
    print(f"Ditemukan {len(group_names)} nama grup")
    
    # Pisahkan grup ADMIN dan NAVY
    admin_groups = [g for g in contact_groups if g['type'] == 'ADMIN']
    navy_groups = [g for g in contact_groups if g['type'] == 'NAVY']
    
    print(f"Grup ADMIN: {len(admin_groups)}")
    print(f"Grup NAVY: {len(navy_groups)}")
    
    # Proses grup ADMIN (jika ada)
    admin_name_index = 0
    for i, group in enumerate(admin_groups):
        if admin_name_index < len(group_names):
            group_name = group_names[admin_name_index]
            file_name = group_name  # Nama file sama dengan nama grup
        else:
            group_name = f"ADMIN_{i+1}"
            file_name = group_name
        
        print(f"Memproses ADMIN grup: {group_name}")
        vcf_content = process_group(group['contacts'], group_name, config['use_numbering'])
        save_vcf_file(output_folder, file_name, vcf_content)
        admin_name_index += 1
    
    # Proses grup NAVY
    navy_name_index = admin_name_index  # Lanjutkan dari index setelah ADMIN
    for i, group in enumerate(navy_groups):
        if navy_name_index < len(group_names):
            group_name = group_names[navy_name_index]
            file_name = group_name  # Nama file sama dengan nama grup
        else:
            group_name = f"NAVY_{i+1}"
            file_name = group_name
        
        print(f"Memproses NAVY grup: {group_name}")
        vcf_content = process_group(group['contacts'], group_name, config['use_numbering'])
        save_vcf_file(output_folder, file_name, vcf_content)
        navy_name_index += 1
    
    print(f"\nPemrosesan selesai! Semua file disimpan di folder '{output_folder}'.")

def get_user_preferences():
    """Dapatkan preferensi pengguna"""
    print("=== Konfigurasi VCF Converter ===")
    
    # Folder output
    output_folder = input("Masukkan nama folder output (default: vcf_output): ").strip() or "vcf_output"
    
    # Opsi penomoran kontak
    print("\nFormat penomoran kontak dalam grup:")
    print("1. Gunakan penomoran 3 digit (001, 002, 003)")
    print("2. Gunakan penomoran biasa (1, 2, 3)")
    
    while True:
        numbering_choice = input("Pilih format penomoran (1-2): ").strip()
        if numbering_choice in ['1', '2']:
            break
        print("Pilihan tidak valid. Masukkan 1 atau 2.")
    
    config = {
        'output_folder': output_folder,
        'use_numbering': numbering_choice == '1'
    }
    
    return config

def main():
    print("=== Dual File VCF Converter ===")
    print("Menggunakan 2 file:")
    print("1. contacts.txt - berisi nomor telepon dengan delimiter . dan ,")
    print("2. namectc.txt - berisi nama grup dan file VCF")
    
    # Dapatkan file input
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # File contacts.txt
    default_contacts = os.path.join(script_dir, 'contacts.txt')
    contacts_file = input(f"Masukkan path file kontak (default: {default_contacts}): ").strip()
    if not contacts_file:
        contacts_file = default_contacts
    
    if not os.path.exists(contacts_file):
        print(f"File kontak '{contacts_file}' tidak ditemukan.")
        input("Tekan Enter untuk keluar...")
        return
    
    # File namectc.txt
    default_names = os.path.join(script_dir, 'namectc.txt')
    names_file = input(f"Masukkan path file nama (default: {default_names}): ").strip()
    if not names_file:
        names_file = default_names
    
    if not os.path.exists(names_file):
        print(f"File nama '{names_file}' tidak ditemukan.")
        input("Tekan Enter untuk keluar...")
        return
    
    # Dapatkan preferensi pengguna
    config = get_user_preferences()
    
    # Tampilkan ringkasan konfigurasi
    print("\n=== Ringkasan Konfigurasi ===")
    print(f"File kontak: {contacts_file}")
    print(f"File nama: {names_file}")
    print(f"Folder output: {config['output_folder']}")
    print(f"Format penomoran: {'3 digit' if config['use_numbering'] else 'biasa'}")
    
    confirm = input("\nLanjutkan dengan konfigurasi ini? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Operasi dibatalkan.")
        return
    
    # Proses file
    process_dual_file_vcf(contacts_file, names_file, config)

if __name__ == "__main__":
    main()