import os
import random
from PIL import Image, ImageDraw, ImageFont

# Konfigurasi dasar
BASE_IMAGE_PATH = "ssedit.jpg"  # Gambar input
OUTPUT_FOLDER = "generated_screenshots"
FONT_PATH = "SFProText-Regular.ttf"  # Ganti sesuai lokasi font kamu
BASE_CODE = "RBN"
TOTAL_IMAGES = 300

# Buat folder output jika belum ada
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Fungsi membuat gambar baru
def generate_images(base_img_path, base_code, total, font_path):
    base_img = Image.open(base_img_path)
    font = ImageFont.truetype(font_path, 28)

    for i in range(1, total + 1):
        img = base_img.copy()
        draw = ImageDraw.Draw(img)

        # Random jam
        hour = random.randint(7, 22)
        minute = random.randint(0, 59)
        jam = f"{hour:02d}.{minute:02d}"
        draw.rectangle([60, 30, 150, 60], fill=(17, 17, 17))  # tutup jam lama
        draw.text((60, 30), jam, font=font, fill=(255, 255, 255))

        # Ganti nama grup
        code = f"{base_code}{i:03d}"
        draw.rectangle([150, 100, 360, 140], fill=(17, 17, 17))  # tutup kode lama
        draw.text((150, 100), code, font=font, fill=(255, 255, 255))

        # Angka notifikasi (acak 31–40)
        notif = str(random.randint(31, 40))
        draw.rectangle([490, 740, 530, 770], fill=(17, 17, 17))  # tutup angka lama
        draw.text((490, 740), notif, font=font, fill=(255, 255, 255))

        # Simpan gambar
        filename = f"{base_code}{i:03d}.jpg"
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        img.save(output_path)

    print(f"{total} gambar berhasil dibuat di folder: {OUTPUT_FOLDER}")

# Jalankan
generate_images(BASE_IMAGE_PATH, BASE_CODE, TOTAL_IMAGES, FONT_PATH)
