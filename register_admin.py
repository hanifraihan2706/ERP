import database as db
from dotenv import load_dotenv
import os

def main():
    load_dotenv()
    
    print("=== REGISTRASI ADMIN BARU ===")
    email = input("Masukkan Email: ").strip()
    password = input("Masukkan Password (min 6 karakter): ").strip()
    
    if len(password) < 6:
        print("❌ Gagal: Password terlalu pendek!")
        return

    try:
        res = db.daftar_user(email, password)
        print(f"✅ Berhasil mendaftarkan: {email}")
        print("Silakan cek email tersebut untuk konfirmasi (jika fitur email confirmation aktif di Supabase).")
    except Exception as e:
        print(f"❌ Gagal mendaftar: {str(e)}")

if __name__ == "__main__":
    main()
