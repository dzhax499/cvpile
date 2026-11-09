#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "header.h"

// Fungsi untuk membersihkan nomor telepon
void clean_phone_number(const char *phone_number, char *cleaned_number) {
    int j = 0;
    for (int i = 0; phone_number[i] != '\0'; i++) {
        if (isdigit(phone_number[i]) || phone_number[i] == '+') {
            cleaned_number[j++] = phone_number[i];
        }
    }
    cleaned_number[j] = '\0'; // Null-terminate string
}

// Fungsi untuk membuat file VCF
void save_vcf_file(const char *output_folder, const char *file_name, const char *vcf_content) {
    char output_path[256];
    snprintf(output_path, sizeof(output_path), "%s/%s.vcf", output_folder, file_name);

    FILE *vcf_file = fopen(output_path, "w");
    if (vcf_file == NULL) {
        printf("Gagal membuat file VCF: %s\n", output_path);
        return;
    }

    fprintf(vcf_file, "%s", vcf_content);
    fclose(vcf_file);
    printf("File '%s' berhasil dibuat di folder '%s'.\n", file_name, output_folder);
}

// Fungsi untuk memproses grup kontak dan menghasilkan konten VCF
void process_group(const char *contacts[], int contact_count, const char *base_name, char *vcf_content) {
    for (int i = 0; i < contact_count; i++) {
        char cleaned_number[32];
        clean_phone_number(contacts[i], cleaned_number);

        char contact_name[50];
        snprintf(contact_name, sizeof(contact_name), "%s %03d", base_name, i + 1);

        // Tambahkan ke konten VCF
        char temp[512];
        snprintf(temp, sizeof(temp),
                 "BEGIN:VCARD\n"
                 "VERSION:3.0\n"
                 "FN:%s\n"
                 "TEL;TYPE=CELL:%s\n"
                 "END:VCARD\n",
                 contact_name, cleaned_number);
        strcat(vcf_content, temp);
    }
}

// Fungsi untuk membaca file TXT dan menghasilkan file VCF
void txt_to_vcf(const char *input_file) {
    FILE *txt_file = fopen(input_file, "r");
    if (txt_file == NULL) {
        printf("Gagal membuka file: %s\n", input_file);
        return;
    }

    char line[256];
    const char *contacts[100];
    int contact_count = 0;
    char vcf_content[8192] = "";
    char output_folder[] = "vcf_output";

    // Buat folder output jika belum ada
    char mkdir_cmd[256];
    snprintf(mkdir_cmd, sizeof(mkdir_cmd), "mkdir -p %s", output_folder);
    system(mkdir_cmd);

    while (fgets(line, sizeof(line), txt_file)) {
        // Hapus newline
        line[strcspn(line, "\n")] = '\0';

        if (strcmp(line, ".") == 0 || strcmp(line, ",") == 0) {
            // Proses grup kontak jika ada pemisah ('.' atau ',')
            if (contact_count > 0) {
                char base_name[50];
                printf("Masukkan nama dasar untuk grup ini (contoh: Group 1): ");
                scanf("%s", base_name);

                process_group(contacts, contact_count, base_name, vcf_content);
                contact_count = 0;
            }

            if (strcmp(line, ",") == 0) {
                char file_name[50];
                printf("Masukkan nama file VCF untuk grup ini (tanpa ekstensi): ");
                scanf("%s", file_name);

                save_vcf_file(output_folder, file_name, vcf_content);
                strcpy(vcf_content, ""); // Reset konten VCF
            }
        } else {
            contacts[contact_count++] = strdup(line);
        }
    }

    // Proses sisa kontak di akhir file
    if (contact_count > 0) {
        char base_name[50];
        printf("Masukkan nama dasar untuk grup ini (contoh: Group 1): ");
        scanf("%s", base_name);

        process_group(contacts, contact_count, base_name, vcf_content);
    }

    // Simpan file VCF terakhir jika ada konten
    if (strlen(vcf_content) > 0) {
        char file_name[50];
        printf("Masukkan nama file VCF untuk grup terakhir (tanpa ekstensi): ");
        scanf("%s", file_name);

        save_vcf_file(output_folder, file_name, vcf_content);
    }

    fclose(txt_file);
}

// Fungsi tambahan lain seperti penggabungan file TXT
void merge_txt_files(const char *input_folder, const char *output_file) {
    FILE *outfile = fopen(output_file, "w");
    if (outfile == NULL) {
        printf("Gagal membuat file output: %s\n", output_file);
        return;
    }

    DIR *dir = opendir(input_folder);
    if (dir == NULL) {
        printf("Folder tidak ditemukan: %s\n", input_folder);
        fclose(outfile);
        return;
    }

    char path[512]; // Pastikan buffer cukup besar
    char buffer[256];
    struct dirent *entry;

    while ((entry = readdir(dir)) != NULL) {
        // Abaikan "." dan ".."
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }

        // Periksa apakah file memiliki ekstensi .txt
        if (strstr(entry->d_name, ".txt") != NULL) {
            snprintf(path, sizeof(path), "%s/%s", input_folder, entry->d_name);
            FILE *infile = fopen(path, "r");
            if (infile != NULL) {
                while (fgets(buffer, sizeof(buffer), infile)) {
                    fputs(buffer, outfile);
                }
                fclose(infile);
            } else {
                printf("Gagal membuka file: %s\n", path);
            }
        }
    }

    closedir(dir);
    fclose(outfile);
    printf("Semua file TXT berhasil digabungkan ke: %s\n", output_file);
}