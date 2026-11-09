#include "header.h"

int main() {
    int pilihan;

    do {
        printf("\n=== MENU ===\n");
        printf("1. Konversi TXT ke VCF\n");
        printf("2. Batch Rename VCF Files\n");
        printf("3. Gabungkan File TXT\n");
        printf("4. Konversi VCF ke TXT\n");
        printf("5. Buat Grup VCF\n");
        printf("0. Keluar\n");
        printf("Pilih menu: ");
        scanf("%d", &pilihan);

        switch (pilihan) {
            case 1: {
                char input_file[256];
                printf("Masukkan nama file TXT (dengan path jika perlu): ");
                scanf("%s", input_file);
                txt_to_vcf(input_file);
                break;
            }
            case 2: {
                printf("Fitur Batch Rename VCF Files belum diimplementasi.\n");
                break;
            }
            case 3: {
                char input_folder[256], output_file[256];
                printf("Masukkan folder input: ");
                scanf("%s", input_folder);
                printf("Masukkan nama file output TXT: ");
                scanf("%s", output_file);
                merge_txt_files(input_folder, output_file);
                break;
            }
            case 4: {
                printf("Fitur Konversi VCF ke TXT belum diimplementasi.\n");
                break;
            }
            case 5: {
                printf("Fitur Buat Grup VCF belum diimplementasi.\n");
                break;
            }
            case 0:
                printf("Keluar dari program.\n");
                break;
            default:
                printf("Pilihan tidak valid. Silakan coba lagi.\n");
        }
    } while (pilihan != 0);

    return 0;
}
