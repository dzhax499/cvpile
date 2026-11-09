#include "header.h"

int main() {
    int choice;

    do {
        printf("\n=== MENU ===\n");
        printf("1. Konversi TXT ke VCF\n");
        printf("2. Batch Rename VCF Files\n");
        printf("3. Gabungkan File TXT\n");
        printf("4. Konversi VCF ke TXT\n");
        printf("5. Buat Grup VCF\n");
        printf("0. Keluar\n");
        printf("Pilih menu: ");
        scanf("%d", &choice);

        switch (choice) {
            case 1:
                txt_to_vcf();
                break;
            case 2:
                batch_rename_vcf_from_file();
                break;
            case 3:
                merge_txt_files();
                break;
            case 4:
                vcf_to_txt_multiple();
                break;
            case 5:
                group_vcf_creator();
                break;
            case 0:
                printf("Keluar dari program.\n");
                break;
            default:
                printf("Pilihan tidak valid. Coba lagi.\n");
                break;
        }
    } while (choice != 0);

    return 0;
}
