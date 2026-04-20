# 👟 Hubb_Shoestreatment — Cloud ERP UMKM
Sistem ERP modern berbasis cloud untuk bisnis cuci sepatu/laundry, dilengkapi dengan sistem manajemen inventaris, keuangan, notifikasi lintas platform, dan dashboard real-time.

---

## 🚀 Fitur Utama
Aplikasi ini dirancang untuk kemudahan operasional UMKM melalui perangkat mobile maupun desktop:

*   **🔐 Keamanan Cloud**: Sistem autentikasi pengguna menggunakan Supabase Auth.
*   **🧹 Smart POS**: Pencatatan order cepat dengan upload foto sepatu dan pembuatan nota digital otomatis.
*   **🧴 Manajemen Inventory & BOM**: Pengurangan stok bahan baku secara otomatis per transaksi sesuai resep (Bill of Materials).
*   **💹 Modul Keuangan**: Laporan laba rugi real-time dengan grafik waterfall yang informatif.
*   **📢 Notifikasi Ganda**: Notifikasi order ke Telegram dan pengiriman struk (receipt) otomatis ke email pelanggan.
*   **📱 Mobile Responsive**: Antarmuka yang dioptimalkan untuk penggunaan di smartphone.

---

## 📁 Struktur Proyek
```text
erp_cuci_sepatu/
├── app.py              # Entry point utama & antarmuka Streamlit
├── database.py         # Logika interaksi database & autentikasi Supabase
├── email_service.py    # Service pengiriman struk via SMTP (Email)
├── telegram_notif.py   # Service notifikasi Telegram Bot
├── ui_components.py    # Komponen UI reusable & Nota Generator
├── schema.sql          # Inisialisasi skema database Supabase
├── requirements.txt    # Daftar dependensi Python
└── .env                # Konfigurasi kredensial (Rahasia)
```

---

## 🛠️ Panduan Instalasi (Langkah demi Langkah)

### 1. Persiapan Database (Supabase)
1.  Buat akun di [Supabase](https://supabase.com/).
2.  Buat project baru dan buka **SQL Editor**.
3.  Jalankan isi file `schema.sql` untuk membuat tabel dasar.
4.  Jalankan perintah SQL tambahan berikut untuk mendukung fitur terbaru:
    ```sql
    -- Tambah kolom email customer
    ALTER TABLE tabel_transaksi_sales ADD COLUMN customer_email VARCHAR(100);

    -- Pastikan Row Level Security (RLS) mengizinkan akses aplikasi
    CREATE POLICY "Akses Penuh" ON tabel_layanan FOR ALL USING (true);
    CREATE POLICY "Akses Penuh" ON tabel_bahan_baku FOR ALL USING (true);
    CREATE POLICY "Akses Penuh" ON tabel_transaksi_sales FOR ALL USING (true);
    CREATE POLICY "Akses Penuh" ON tabel_bom FOR ALL USING (true);
    CREATE POLICY "Akses Penuh" ON tabel_pengeluaran FOR ALL USING (true);
    ```

### 2. Setup Lingkungan Lokal
```bash
# Clone repository
git clone <url-repo-anda>
cd erp_cuci_sepatu

# Buat virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# atau
venv\Scripts\activate     # Windows

# Install dependensi
pip install -r requirements.txt
```

### 3. Konfigurasi Environment (`.env`)
Buat file baru bernama `.env` dan isi dengan kredensial Anda:
```env
# SUPABASE
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# TELEGRAM
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# EMAIL (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=email-anda@gmail.com
EMAIL_PASSWORD=app-password-gmail-anda
```

---

## 📖 Cara Penggunaan

### 1. Pendaftaran Admin
Saat pertama kali dijalankan, buka tab **"Daftar Owner"** di halaman login untuk membuat akun admin pertama Anda. Setelah itu, Login menggunakan email tersebut.

### 2. Input Order (POS)
1.  Pilih menu **➕ Order Baru**.
2.  Isi data customer dan pilih layanan.
3.  Masukkan email pelanggan jika ingin mengirim struk otomatis.
4.  Upload foto sepatu sebagai bukti kondisi awal.
5.  Klik **Simpan Order**.

### 3. Manajemen Status
Buka menu **📋 Order** untuk memperbarui status pengerjaan (Antre → Cuci → Jemur → Selesai → Diambil). Status "Cuci" akan otomatis memotong stok bahan baku.

### 4. Laporan Keuangan
Lihat ringkasan laba bersih bulanan di menu **💹 Keuangan**. Semua biaya operasional (Fixed/Variable) dapat dicatat di tab **Catat Pengeluaran**.

---

## 🛠️ Troubleshooting (Tanya Jawab)

> [!WARNING]
> **Error: AttributeError: module 'database' has no attribute 'login_user'**
> Ini terjadi karena Streamlit gagal memuat ulang modul `database.py` setelah pembaruan kode.
> **Solusi:** Hentikan aplikasi (Ctrl+C di terminal) lalu jalankan kembali `streamlit run app.py`.

> [!TIP]
> **Email Struk Tidak Terkirim**
> Pastikan Anda menggunakan **App Password** Gmail (16 digit), bukan password login biasa, dan pastikan akses SMTP diaktifkan di akun Gmail Anda.

---

## 📡 Deployment ke Hosting
Untuk menjalankan aplikasi secara 24/7, direkomendasikan menggunakan **Streamlit Community Cloud** (Gratis):
1.  Upload kode ke GitHub.
2.  Hubungkan repo ke Streamlit Cloud.
3.  Masukkan isi `.env` ke bagian **Secrets** di pengaturan aplikasi.

---
**Maintained by:** Hubb_Shoestreatment Team | &copy; 2026
