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

    # Tambahkan input untuk menentukan angka awal urutan nama
    start_number = int(input("Masukkan angka awal urutan nama: "))

    file_index = 0  # Indeks file VCF
    while contact_counter < total_contacts:
        output_vcf = f"contacts_{file_index + 1}.vcf"
        output_vcf_path = os.path.join(output_folder, output_vcf)

        with open(output_vcf_path, 'w') as vcf_file:
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

                    # Increment kontak counter
                    contact_counter += 1

                    # Buat nama dengan penomoran berurutan, dimulai dari 'start_number'
                    name = f"{base_name}_{str(start_number).zfill(3)}"

                    # Buat format VCF untuk setiap kontak yang valid
                    vcf_content = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{formatted_phone_number}
NOTE:Country: {country}
END:VCARD
"""
                    vcf_file.write(vcf_content)
                    
                    # Tambah start_number setelah setiap kontak
                    start_number += 1
                else:
                    # Tambah hitung untuk nomor tidak valid
                    invalid_count += 1
                    contact_counter += 1  # Tetap lanjutkan ke kontak berikutnya

                    # Tulis entri untuk nomor tidak valid
                    name = f"{base_name}_{str(start_number).zfill(3)}_INVALID"
                    vcf_content_invalid = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL;TYPE=CELL:{phone_number}
NOTE:Invalid Number
END:VCARD
"""
                    vcf_file.write(vcf_content_invalid)
                    
                    # Tambah start_number untuk nomor tidak valid juga
                    start_number += 1

        print(f"File VCF '{output_vcf}' berhasil dibuat di folder '{output_folder}'.")
        file_index += 1  # Increment file index

    # Tampilkan jumlah nomor tidak valid
    print(f"Jumlah nomor tidak valid: {invalid_count}")
