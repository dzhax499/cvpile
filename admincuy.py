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
    output_path = os.path.join(output_folder, f"{file_name}.vcf")
    while os.path.exists(output_path):  # Periksa jika file sudah ada
        output_path = os.path.join(output_folder, f"{file_name}_{counter}.vcf")
        counter += 1
    with open(output_path, 'w') as vcf_file:
        vcf_file.write(vcf_content)
    print(f"File '{os.path.basename(output_path)}' successfully created in '{output_folder}'.")

def process_group(contacts, base_name):
    vcf_content = ""
    for idx, contact in enumerate(contacts):
        phone_number = contact.strip()
        contact_name = f"{base_name} {idx + 1:03d}"

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

def txt_to_vcf(input_txt):
    with open(input_txt, 'r') as txt_file:
        lines = txt_file.readlines()

    group_contacts = []
    all_vcf_content = ""
    output_folder = 'vcf_output_renamed'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    while lines:
        line = lines.pop(0).strip()
        if line == '.':
            if group_contacts:
                base_name = input("NAMA ADMIN : ")
                all_vcf_content += process_group(group_contacts, base_name)
                group_contacts = []
        elif line == ',':
            if group_contacts:
                base_name = input("NAMA NAVY : ")
                all_vcf_content += process_group(group_contacts, base_name)
                group_contacts = []
            file_name = input("NAMA FILE : ")
            save_vcf_file(output_folder, file_name, all_vcf_content)
            all_vcf_content = ""
        else:
            group_contacts.append(line)

    if group_contacts:
        base_name = input("Enter contact name for this group (e.g., Group 1): ")
        all_vcf_content += process_group(group_contacts, base_name)

    if all_vcf_content:
        file_name = input("Enter the name for this VCF file (without extension): ")
        save_vcf_file(output_folder, file_name, all_vcf_content)

# Run the program
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_txt = os.path.join(script_dir, 'contacts.txt')
    txt_to_vcf(input_txt)
