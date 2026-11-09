import os
import re

def parse_vcf(file_path):
    contacts = []
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Split by VCARD entries
    vcards = re.split(r'BEGIN:VCARD', content)[1:]  # Skip the first empty part
    
    for vcard in vcards:
        lines = vcard.split('\n')
        name = ""
        phone = ""
        for line in lines:
            if line.startswith('FN:'):
                name = line[3:].strip()
            elif line.startswith('TEL;'):
                phone = line.split(':')[1].strip() if ':' in line else ""
        if name and phone:
            contacts.append((phone, name))
    return contacts

def vcf_to_txt(vcf_folder, output_folder, last_n_contacts, combine_all, include_name):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    vcf_files = [f for f in os.listdir(vcf_folder) if f.endswith('.vcf')]
    
    if combine_all:
        combined_contacts = []
        for vcf_file in vcf_files:
            vcf_path = os.path.join(vcf_folder, vcf_file)
            contacts = parse_vcf(vcf_path)
            # Take last N contacts
            selected_contacts = contacts[-last_n_contacts:] if len(contacts) >= last_n_contacts else contacts
            combined_contacts.extend(selected_contacts)
        
        output_txt = os.path.join(output_folder, 'combined_contacts.txt')
        with open(output_txt, 'w', encoding='utf-8') as txt_file:
            for phone, name in combined_contacts:
                if include_name:
                    txt_file.write(f"{phone} {name}\n")
                else:
                    txt_file.write(phone + '\n')
        print(f"Combined TXT file created: {output_txt}")
    else:
        for vcf_file in vcf_files:
            vcf_path = os.path.join(vcf_folder, vcf_file)
            contacts = parse_vcf(vcf_path)
            # Take last N contacts
            selected_contacts = contacts[-last_n_contacts:] if len(contacts) >= last_n_contacts else contacts
            
            txt_filename = os.path.splitext(vcf_file)[0] + '.txt'
            output_txt = os.path.join(output_folder, txt_filename)
            with open(output_txt, 'w', encoding='utf-8') as txt_file:
                for phone, name in selected_contacts:
                    if include_name:
                        txt_file.write(f"{phone} {name}\n")
                    else:
                        txt_file.write(phone + '\n')
            print(f"TXT file created for {vcf_file}: {output_txt}")

# Main execution
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Folder untuk file VCF input (dapat custom, tapi default di folder 'vcf_input')
    vcf_folder = os.path.join(script_dir, 'vcf_input')
    if not os.path.exists(vcf_folder):
        os.makedirs(vcf_folder)
        print(f"Folder 'vcf_input' dibuat di {vcf_folder}. Silakan letakkan file VCF di sana.")
    
    # Folder output untuk TXT
    output_folder = os.path.join(script_dir, 'txt_output_from_vcf')
    
    # Input jumlah kontak terakhir yang ingin diambil
    last_n_contacts = int(input("Masukkan jumlah kontak terakhir yang ingin diambil dari setiap VCF (misal 35): "))
    
    # Pilih opsi: gabung semua atau terpisah
    combine_choice = input("Apakah ingin menggabungkan semua kontak ke satu TXT? (y/n): ").lower()
    combine_all = combine_choice == 'y'
    
    # Pilih opsi: sertakan nama atau hanya nomor
    name_choice = input("Apakah ingin menyertakan nama kontak? (y/n): ").lower()
    include_name = name_choice == 'y'
    
    # Jalankan konversi
    vcf_to_txt(vcf_folder, output_folder, last_n_contacts, combine_all, include_name)