import os
import re
import csv
import json
import phonenumbers
from phonenumbers import geocoder, carrier
import tkinter as tk
from tkinter import (
    filedialog, messagebox, ttk, 
    scrolledtext, StringVar, IntVar, BooleanVar
)


class ContactConverter:
    def __init__(self, master):
        self.master = master
        master.title("Contact Converter Tool")
        master.geometry("800x850")
        master.configure(bg='#f0f0f0')

        # Style configuration
        self.style = ttk.Style()
        self.style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        self.style.configure('TButton', font=('Arial', 10))

        # Input file path
        self.input_file_path = tk.StringVar()
        self.create_input_file_section()

        # Conversion options
        self.create_conversion_options()

        # Advanced conversion options
        self.create_advanced_conversion_options()

        # Output filename options
        self.create_output_filename_section()

        # Conversion type radio buttons
        self.create_conversion_type_section()

        # Buttons
        self.create_action_buttons()

        # Log area
        self.create_log_area()

    def create_input_file_section(self):
        """Create section for selecting input file."""
        input_frame = ttk.Frame(self.master, style='TFrame')
        input_frame.pack(pady=10, padx=20, fill='x')

        ttk.Label(input_frame, text="Input File(s):").pack(side='left')
        
        input_entry = ttk.Entry(input_frame, textvariable=self.input_file_path, width=50)
        input_entry.pack(side='left', padx=10, expand=True, fill='x')

        browse_btn = ttk.Button(input_frame, text="Browse", command=self.browse_input_file)
        browse_btn.pack(side='left', padx=5)

    def create_output_filename_section(self):
        """Create section for specifying output filename."""
        filename_frame = ttk.Frame(self.master, style='TFrame')
        filename_frame.pack(pady=10, padx=20, fill='x')

        # Output Filename
        ttk.Label(filename_frame, text="Output Filename (optional):").grid(row=0, column=0, sticky='w', padx=5)
        self.output_filename_var = StringVar()
        output_filename_entry = ttk.Entry(filename_frame, textvariable=self.output_filename_var, width=40)
        output_filename_entry.grid(row=0, column=1, padx=5, sticky='we')

        # Filename hint
        ttk.Label(filename_frame, text="Leave blank for default naming", font=('Arial', 8, 'italic')).grid(row=1, column=1, sticky='w', padx=5)


    def create_conversion_options(self):
        """Create basic conversion options section."""
        options_frame = ttk.Frame(self.master, style='TFrame')
        options_frame.pack(pady=10, padx=20, fill='x')

        # Base Name
        ttk.Label(options_frame, text="Base Name:").grid(row=0, column=0, sticky='w', padx=5)
        self.base_name_var = StringVar(value="Contact")
        ttk.Entry(options_frame, textvariable=self.base_name_var, width=20).grid(row=0, column=1, padx=5)

        # File Prefix
        ttk.Label(options_frame, text="File Prefix:").grid(row=0, column=2, sticky='w', padx=5)
        self.file_prefix_var = StringVar(value="CONTACTS")
        ttk.Entry(options_frame, textvariable=self.file_prefix_var, width=20).grid(row=0, column=3, padx=5)

        # Contacts per File
        ttk.Label(options_frame, text="Contacts per File:").grid(row=1, column=0, sticky='w', padx=5)
        self.contacts_per_file_var = IntVar(value=50)
        ttk.Spinbox(options_frame, from_=1, to=1000, textvariable=self.contacts_per_file_var, width=10).grid(row=1, column=1, padx=5)

        # Letter Prefix Options
        self.use_letter_prefix_var = BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame, 
            text="Use Letter Prefix", 
            variable=self.use_letter_prefix_var, 
            command=self.toggle_letter_prefix
        ).grid(row=1, column=2, sticky='w', padx=5)

        # Letter Prefix Entry (initially disabled)
        self.letter_prefix_var = StringVar(value="")
        self.letter_prefix_entry = ttk.Entry(
            options_frame, 
            textvariable=self.letter_prefix_var, 
            width=10, 
            state='disabled'
        )
        self.letter_prefix_entry.grid(row=1, column=3, padx=5)

    def create_advanced_conversion_options(self):
        """Create advanced conversion options section."""
        advanced_frame = ttk.Frame(self.master, style='TFrame')
        advanced_frame.pack(pady=10, padx=20, fill='x')

        # TXT to VCF Start Index
        ttk.Label(advanced_frame, text="TXT to VCF Start Index:", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w')

        # Start Index for TXT to VCF
        ttk.Label(advanced_frame, text="Start Index:").grid(row=1, column=0, sticky='w', padx=5)
        self.txt_to_vcf_start_index_var = IntVar(value=1)
        ttk.Spinbox(advanced_frame, from_=1, to=10000, textvariable=self.txt_to_vcf_start_index_var, width=10).grid(row=1, column=1, padx=5)

        # VCF to TXT Conversion Options
        ttk.Label(advanced_frame, text="VCF to TXT Options:", font=('Arial', 10, 'bold')).grid(row=2, column=0, columnspan=4, sticky='w', pady=(10,0))

        # Number of contacts per TXT file
        ttk.Label(advanced_frame, text="Contacts per TXT:").grid(row=3, column=0, sticky='w', padx=5)
        self.vcf_to_txt_contacts_var = IntVar(value=50)
        ttk.Spinbox(advanced_frame, from_=1, to=10000, textvariable=self.vcf_to_txt_contacts_var, width=10).grid(row=3, column=1, padx=5)

        # Include contact names option
        self.include_names_var = BooleanVar(value=False)
        ttk.Checkbutton(
            advanced_frame, 
            text="Include Contact Names", 
            variable=self.include_names_var
        ).grid(row=3, column=2, sticky='w', padx=5)

        # Merge VCF/TXT Options
        ttk.Label(advanced_frame, text="Merge Options:", font=('Arial', 10, 'bold')).grid(row=4, column=0, columnspan=4, sticky='w', pady=(10,0))

        # Maximum contacts in merged file
        ttk.Label(advanced_frame, text="Max Contacts in Merged File:").grid(row=5, column=0, sticky='w', padx=5)
        self.merge_max_contacts_var = IntVar(value=1000)
        ttk.Spinbox(advanced_frame, from_=1, to=100000, textvariable=self.merge_max_contacts_var, width=10).grid(row=5, column=1, padx=5)

        # Remove Duplicates
        self.remove_duplicates_var = BooleanVar(value=True)
        ttk.Checkbutton(
            advanced_frame, 
            text="Remove Duplicates", 
            variable=self.remove_duplicates_var
        ).grid(row=5, column=2, sticky='w', padx=5)

    def convert_txt_to_vcf(self, input_file):
        """Convert TXT file to multiple VCF files with continuous global numbering."""
        # Read input numbers
        with open(input_file, 'r', encoding='utf-8') as f:
            contacts = [line.strip() for line in f if line.strip()]

        # Prepare conversion parameters
        base_name = self.base_name_var.get()
        file_prefix = self.file_prefix_var.get()
        contacts_per_file = self.contacts_per_file_var.get()
        letter_prefix = self.letter_prefix_var.get() if self.use_letter_prefix_var.get() else ""
        
        # Output directory
        output_dir = os.path.dirname(input_file)
        os.makedirs(output_dir, exist_ok=True)

        # Global tracking of current index across all files
        global_start_index = 1
        file_count = 0

        # Find existing VCF files in the directory to determine the starting index
        existing_vcf_files = [f for f in os.listdir(output_dir) if f.endswith('.vcf') and file_prefix in f]
        if existing_vcf_files:
            # Find the highest existing index
            def extract_index(filename):
                try:
                    # Extract number from filename, handling cases with and without letter prefix
                    match = re.search(r'(\d+)\.vcf$', filename)
                    return int(match.group(1)) if match else 0
                except:
                    return 0
            
            max_existing_index = max(extract_index(f) for f in existing_vcf_files)
            global_start_index = max_existing_index + 1

        # Process contacts in batches
        current_global_index = global_start_index

        for i in range(0, len(contacts), contacts_per_file):
            batch = contacts[i:i+contacts_per_file]
            file_count += 1

            # Create VCF filename
            if letter_prefix:
                vcf_filename = f"{file_prefix} {letter_prefix}{current_global_index}.vcf"
            else:
                vcf_filename = f"{file_prefix} {current_global_index}.vcf"
            
            vcf_path = os.path.join(output_dir, vcf_filename)

            with open(vcf_path, 'w', encoding='utf-8') as vcf_file:
                for local_idx, contact in enumerate(batch, 1):
                    # Split contact if it contains a name
                    parts = contact.split(" - ", 1)
                    if len(parts) > 1:
                        contact_name, phone_number = parts
                    else:
                        phone_number = contact
                        contact_name = f"{base_name}"

                    # Clean and validate number
                    clean_number = self.clean_number(phone_number)
                    
                    # Get country and carrier info
                    try:
                        phone_obj = phonenumbers.parse(clean_number)
                        country = (
                            geocoder.description_for_number(phone_obj, "en")
                            if phonenumbers.is_valid_number(phone_obj)
                            else "Unknown"
                        )
                        carrier_info = (
                            carrier.name_for_number(phone_obj, "en")
                            if phonenumbers.is_valid_number(phone_obj)
                            else "Unknown"
                        )
                    except:
                        country = "Unknown"
                        carrier_info = "Unknown"

                    # Construct contact name with continuous global numbering
                    if letter_prefix:
                        full_contact_name = f"{contact_name} {letter_prefix}{current_global_index:03}"
                    else:
                        full_contact_name = f"{contact_name} {current_global_index:03}"

                    # Write VCF entry
                    vcf_file.write(
                        f"BEGIN:VCARD\n"
                        f"VERSION:3.0\n"
                        f"FN:{full_contact_name}\n"
                        f"TEL;TYPE=CELL:{clean_number}\n"
                        f"NOTE:Country: {country}, Carrier: {carrier_info}\n"
                        f"END:VCARD\n"
                    )

                    # Increment global index
                    current_global_index += 1

            # Log the created file
            self.log_message(f"Created VCF file: {vcf_filename}")

        # Final summary
        self.log_message(f"Conversion complete. Total VCF files created: {file_count}")
        self.log_message(f"Contact numbering starts from: {global_start_index}")
        self.log_message(f"Final contact number: {current_global_index - 1}")

    def create_conversion_type_section(self):
        """Create conversion type radio buttons."""
        type_frame = ttk.Frame(self.master, style='TFrame')
        type_frame.pack(pady=10, padx=20, fill='x')

        self.conversion_type = StringVar(value="txt_to_vcf")
        
        conversion_types = [
            ("TXT to VCF", "txt_to_vcf"),
            ("VCF to TXT", "vcf_to_txt"),
            ("Merge Files", "merge_files")
        ]

        for text, value in conversion_types:
            ttk.Radiobutton(
                type_frame, 
                text=text, 
                variable=self.conversion_type, 
                value=value
            ).pack(side='left', padx=10)

    def toggle_letter_prefix(self):
        """Enable/disable letter prefix entry based on checkbox."""
        if self.use_letter_prefix_var.get():
            self.letter_prefix_entry.config(state='normal')
        else:
            self.letter_prefix_entry.config(state='disabled')
            self.letter_prefix_var.set("")

    def browse_input_file(self):
        """Open file dialog to browse input file(s)."""
        filetypes = [
            ("Text Files", "*.txt"),
            ("VCF Files", "*.vcf"),
            ("All Files", "*.*")
        ]
        
        # Multifile selection for merge and VCF to TXT
        if self.conversion_type.get() in ["vcf_to_txt", "merge_files"]:
            filenames = filedialog.askopenfilenames(filetypes=filetypes)
            if filenames:
                self.input_file_path.set("; ".join(filenames))
        else:
            # Single file selection for other conversions
            filename = filedialog.askopenfilename(filetypes=filetypes)
            if filename:
                self.input_file_path.set(filename)

    def convert_txt_to_vcf(self, input_file):
        """Convert TXT file to multiple VCF files with continuous contact numbering."""
        # Read input numbers
        with open(input_file, 'r', encoding='utf-8') as f:
            contacts = [line.strip() for line in f if line.strip()]

        # Prepare conversion parameters
        base_name = self.base_name_var.get()
        file_prefix = self.file_prefix_var.get()
        contacts_per_file = self.contacts_per_file_var.get()
        letter_prefix = self.letter_prefix_var.get() if self.use_letter_prefix_var.get() else ""
        
        # Get start index from UI
        start_index = self.txt_to_vcf_start_index_var.get()
        
        # Output directory
        output_dir = os.path.dirname(input_file)
        os.makedirs(output_dir, exist_ok=True)

        # Process contacts in batches
        file_count = 0
        global_contact_index = 1

        for i in range(0, len(contacts), contacts_per_file):
            batch = contacts[i:i+contacts_per_file]
            current_file_index = start_index + file_count

            # Create VCF filename with letter prefix
            if letter_prefix:
                vcf_filename = f"{file_prefix} {letter_prefix}{current_file_index}.vcf"
            else:
                vcf_filename = f"{file_prefix} {current_file_index}.vcf"
            
            vcf_path = os.path.join(output_dir, vcf_filename)

            with open(vcf_path, 'w', encoding='utf-8') as vcf_file:
                for contact in batch:
                    # Split contact if it contains a name
                    parts = contact.split(" - ", 1)
                    if len(parts) > 1:
                        contact_name, phone_number = parts
                    else:
                        phone_number = contact
                        contact_name = base_name

                    # Clean and validate number
                    clean_number = self.clean_number(phone_number)
                    
                    # Get country and carrier info
                    try:
                        phone_obj = phonenumbers.parse(clean_number)
                        country = (
                            geocoder.description_for_number(phone_obj, "en")
                            if phonenumbers.is_valid_number(phone_obj)
                            else "Unknown"
                        )
                        carrier_info = (
                            carrier.name_for_number(phone_obj, "en")
                            if phonenumbers.is_valid_number(phone_obj)
                            else "Unknown"
                        )
                    except:
                        country = "Unknown"
                        carrier_info = "Unknown"

                    # Construct contact name with continuous global numbering
                    full_contact_name = f"{contact_name} {global_contact_index:03}"

                    # Write VCF entry
                    vcf_file.write(
                        f"BEGIN:VCARD\n"
                        f"VERSION:3.0\n"
                        f"FN:{full_contact_name}\n"
                        f"TEL;TYPE=CELL:{clean_number}\n"
                        f"NOTE:Country: {country}, Carrier: {carrier_info}\n"
                        f"END:VCARD\n"
                    )

                    # Increment global contact index
                    global_contact_index += 1

            # Increment file count
            file_count += 1

            # Log the created file
            self.log_message(f"Created VCF file: {vcf_filename}")

        # Final summary
        last_contact_index = global_contact_index - 1
        first_contact_index = 1
        
        self.log_message(f"Conversion complete. Total VCF files created: {file_count}")
        self.log_message(f"First file index: {start_index}")
        self.log_message(f"Last file index: {start_index + file_count - 1}")
        self.log_message(f"Contact range: {first_contact_index} - {last_contact_index}")


    def merge_files(self):
        """Advanced file merging with support for TXT and VCF files and unique contact numbering."""
        # Get input files
        input_files = self.input_file_path.get().split("; ")
        
        # Validate input files
        if not input_files:
            messagebox.showerror("Error", "Please select files to merge")
            return
        
        # Determine file type based on first file
        first_file_ext = os.path.splitext(input_files[0])[1].lower()
        supported_extensions = {'.txt', '.vcf'}
        
        if first_file_ext not in supported_extensions:
            messagebox.showerror("Error", "Unsupported file type. Please select .txt or .vcf files.")
            return
        
        # Validate all files have the same extension
        if not all(os.path.splitext(f)[1].lower() == first_file_ext for f in input_files):
            messagebox.showerror("Error", "All files must be of the same type (.txt or .vcf)")
            return
        
        # Output directory
        output_dir = os.path.dirname(input_files[0]) if input_files else os.getcwd()
        
        # Maximum contacts per merged file
        max_contacts = self.merge_max_contacts_var.get()
        
        # Remove duplicates option
        remove_duplicates = self.remove_duplicates_var.get()
        
        # Get custom filename (or use default)
        custom_filename = self.output_filename_var.get().strip()
        
        # Ensure correct file extension for custom filename
        if custom_filename:
            # If no extension provided, add the appropriate extension
            if not os.path.splitext(custom_filename)[1]:
                custom_filename += first_file_ext
        
        # Collect all phone numbers or VCF contacts
        all_contacts = []
        
        # Process files based on extension
        if first_file_ext == '.txt':
            # TXT file merging
            for input_file in input_files:
                with open(input_file, 'r', encoding='utf-8') as f:
                    all_contacts.extend(line.strip() for line in f if line.strip())
            
            # Remove duplicates if option is selected
            if remove_duplicates:
                all_contacts = list(dict.fromkeys(all_contacts))
            
            # Split into multiple files if needed
            file_count = 0
            for i in range(0, len(all_contacts), max_contacts):
                file_count += 1
                batch = all_contacts[i:i+max_contacts]
                
                # Create output filename
                if custom_filename:
                    # If custom filename is provided, use it with numbering for multiple files
                    if len(all_contacts) > max_contacts:
                        base, ext = os.path.splitext(custom_filename)
                        output_filename = os.path.join(
                            output_dir, 
                            f"{base}_{file_count}{ext}"
                        )
                    else:
                        output_filename = os.path.join(output_dir, custom_filename)
                else:
                    # Default naming
                    output_filename = os.path.join(
                        output_dir, 
                        f"merged_{file_count}.txt" if len(all_contacts) > max_contacts else "merged.txt"
                    )
                
                # Write batch to file
                with open(output_filename, 'w', encoding='utf-8') as txt:
                    txt.write("\n".join(batch))
                
                self.log_message(f"Created merged TXT file: {output_filename}")

            # Final summary
            self.log_message(f"Total TXT numbers merged: {len(all_contacts)}")
            self.log_message(f"Total TXT files created: {file_count}")
        
        elif first_file_ext == '.vcf':
            # VCF merging with unique contact numbering
            for input_file in input_files:
                current_contact = {}
                with open(input_file, 'r', encoding='utf-8') as vcf:
                    for line in vcf:
                        line = line.strip()
                        if line == "BEGIN:VCARD":
                            current_contact = {}
                        elif line.startswith("FN:"):
                            current_contact['name'] = line.split(":", 1)[1].strip()
                        elif line.startswith("TEL;"):
                            current_contact['number'] = line.split(":", 1)[1].strip()
                        elif line == "END:VCARD":
                            if 'name' in current_contact and 'number' in current_contact:
                                all_contacts.append(
                                    f"{current_contact['name']} - {current_contact['number']}"
                                )
            
            # Remove duplicates if option is selected
            if remove_duplicates:
                all_contacts = list(dict.fromkeys(all_contacts))
            
            # Split into multiple files if needed
            file_count = 0
            for i in range(0, len(all_contacts), max_contacts):
                file_count += 1
                batch = all_contacts[i:i+max_contacts]
                
                # Create output filename
                if custom_filename:
                    # If custom filename is provided, use it with numbering for multiple files
                    if len(all_contacts) > max_contacts:
                        base, ext = os.path.splitext(custom_filename)
                        output_filename = os.path.join(
                            output_dir, 
                            f"{base}_{file_count}{ext}"
                        )
                    else:
                        output_filename = os.path.join(output_dir, custom_filename)
                else:
                    # Default naming
                    output_filename = os.path.join(
                        output_dir, 
                        f"merged_{file_count}.vcf" if len(all_contacts) > max_contacts else "merged.vcf"
                    )
                
                # Write batch to VCF file with reset numbering
                with open(output_filename, 'w', encoding='utf-8') as vcf:
                    for local_index, contact in enumerate(batch, 1):
                        name, number = contact.split(" - ", 1)
                        
                        # Clean and validate number
                        clean_number = self.clean_number(number)
                        
                        # Get country and carrier info
                        try:
                            phone_obj = phonenumbers.parse(clean_number)
                            country = (
                                geocoder.description_for_number(phone_obj, "en")
                                if phonenumbers.is_valid_number(phone_obj)
                                else "Unknown"
                            )
                            carrier_info = (
                                carrier.name_for_number(phone_obj, "en")
                                if phonenumbers.is_valid_number(phone_obj)
                                else "Unknown"
                            )
                        except:
                            country = "Unknown"
                            carrier_info = "Unknown"
                        
                        # Write VCF entry with reset numbering
                        vcf.write(
                            "BEGIN:VCARD\n"
                            "VERSION:3.0\n"
                            f"FN:{name} {local_index:03}\n"
                            f"TEL;TYPE=CELL:{clean_number}\n"
                            f"NOTE:Country: {country}, Carrier: {carrier_info}\n"
                            "END:VCARD\n"
                        )
                
                self.log_message(f"Created merged VCF file: {output_filename}")

            # Final summary
            self.log_message(f"Total VCF contacts merged: {len(all_contacts)}")
            self.log_message(f"Total VCF files created: {file_count}")


    def convert_contacts(self):
        """Main conversion method based on selected type."""
        try:
            input_files = self.input_file_path.get()
            if not input_files:
                messagebox.showerror("Error", "Please select input file(s).")
                return

            conversion_type = self.conversion_type.get()
            
            if conversion_type == "txt_to_vcf":
                self.convert_txt_to_vcf(self.input_file_path.get())
            elif conversion_type == "vcf_to_txt":
                self.convert_vcf_to_txt()
            elif conversion_type == "merge_files":
                self.merge_files()

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.log_message(f"Error: {str(e)}")

    def create_action_buttons(self):
        """Create action buttons."""
        button_frame = ttk.Frame(self.master, style='TFrame')
        button_frame.pack(pady=10, padx=20, fill='x')

        convert_btn = ttk.Button(button_frame, text="Convert", command=self.convert_contacts)
        convert_btn.pack(side='left', padx=10)

        clear_btn = ttk.Button(button_frame, text="Clear Log", command=self.clear_log)
        clear_btn.pack(side='left', padx=10)

    def create_log_area(self):
        """Create log area for displaying conversion results."""
        log_frame = ttk.Frame(self.master, style='TFrame')
        log_frame.pack(pady=10, padx=20, expand=True, fill='both')

        ttk.Label(log_frame, text="Conversion Log:").pack(anchor='w')

        self.log_area = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            width=80, 
            height=10
        )
        self.log_area.pack(expand=True, fill='both')

    def log_message(self, message):
        """Log messages to the log area."""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def clear_log(self):
        """Clear the log area."""
        self.log_area.delete(1.0, tk.END)

    def convert_txt_to_vcf(self, input_file):
        """Convert TXT file to multiple VCF files with advanced options."""
        # Read input numbers
        with open(input_file, 'r', encoding='utf-8') as f:
            contacts = [line.strip() for line in f if line.strip()]

        # Prepare conversion parameters
        base_name = self.base_name_var.get()
        file_prefix = self.file_prefix_var.get()
        contacts_per_file = self.contacts_per_file_var.get()
        letter_prefix = self.letter_prefix_var.get() if self.use_letter_prefix_var.get() else ""
        start_index = 1  # Always start from 1 for consistent numbering

        # Output directory
        output_dir = os.path.dirname(input_file)
        os.makedirs(output_dir, exist_ok=True)

        # Process contacts in batches
        current_index = start_index
        file_count = 0

        for i in range(0, len(contacts), contacts_per_file):
            batch = contacts[i:i+contacts_per_file]
            file_count += 1

            # Create VCF filename
            if letter_prefix:
                vcf_filename = f"{file_prefix} {letter_prefix}{current_index}.vcf"
            else:
                vcf_filename = f"{file_prefix} {current_index}.vcf"
            
            vcf_path = os.path.join(output_dir, vcf_filename)

            with open(vcf_path, 'w', encoding='utf-8') as vcf_file:
                for local_idx, contact in enumerate(batch, 1):
                    # Split contact if it contains a name
                    parts = contact.split(" - ", 1)
                    if len(parts) > 1:
                        contact_name, phone_number = parts
                    else:
                        phone_number = contact
                        contact_name = f"{base_name}"

                    # Clean and validate number
                    clean_number = self.clean_number(phone_number)
                    
                    # Get country and carrier info
                    try:
                        phone_obj = phonenumbers.parse(clean_number)
                        country = (
                            geocoder.description_for_number(phone_obj, "en")
                            if phonenumbers.is_valid_number(phone_obj)
                            else "Unknown"
                        )
                        carrier_info = (
                            carrier.name_for_number(phone_obj, "en")
                            if phonenumbers.is_valid_number(phone_obj)
                            else "Unknown"
                        )
                    except:
                        country = "Unknown"
                        carrier_info = "Unknown"

                    # Construct contact name with or without letter prefix
                    if letter_prefix:
                        full_contact_name = f"{contact_name} {letter_prefix}{current_index:03}"
                    else:
                        full_contact_name = f"{contact_name} {current_index:03}"

                    # Write VCF entry
                    vcf_file.write(
                        f"BEGIN:VCARD\n"
                        f"VERSION:3.0\n"
                        f"FN:{full_contact_name}\n"
                        f"TEL;TYPE=CELL:{clean_number}\n"
                        f"NOTE:Country: {country}, Carrier: {carrier_info}\n"
                        f"END:VCARD\n"
                    )

            # Log the created file
            self.log_message(f"Created VCF file: {vcf_filename}")
            
            # Increment index for next batch
            current_index += 1

        # Final summary
        self.log_message(f"Conversion complete. Total VCF files created: {file_count}")

    def clean_number(self, phone_number: str) -> str:
        """Clean and format phone number."""
        # Remove non-digit characters
        cleaned = re.sub(r'[^\d]', '', phone_number.strip())
        return f"+{cleaned}" if cleaned and cleaned[0].isdigit() else cleaned

def main():
    root = tk.Tk()
    app = ContactConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main()