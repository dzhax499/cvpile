#ifndef HEADER_H
#define HEADER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dirent.h>
#include <sys/types.h>

// Fungsi utama
void clean_phone_number(const char *phone_number, char *cleaned_number);
void save_vcf_file(const char *output_folder, const char *file_name, const char *vcf_content);
void process_group(const char *contacts[], int contact_count, const char *base_name, char *vcf_content);
void txt_to_vcf(const char *input_file);
void merge_txt_files(const char *input_folder, const char *output_file);

#endif
