"""
database.py — Modul database terpusat
Semua interaksi dengan Supabase ada di sini (tidak ada query di UI)
"""
import os
from datetime import date, datetime
import calendar
from typing import Optional
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def parse_iso(dt_str: str) -> datetime:
    """Helper untuk parsing ISO format dari Supabase yang variatif (milidetik)."""
    if not dt_str:
        return None
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        # Fallback jika milidetik tidak standar (misal 5 digit: .25202)
        if "." in dt_str:
            prefix, remainder = dt_str.split(".", 1)
            if "+" in remainder:
                mics, tz = remainder.split("+", 1)
                sign = "+"
            elif "-" in remainder:
                mics, tz = remainder.split("-", 1)
                sign = "-"
            else:
                mics, tz, sign = remainder, "", ""
            mics = mics.ljust(6, "0")[:6]
            dt_str = f"{prefix}.{mics}{sign}{tz}"
            return datetime.fromisoformat(dt_str)
        raise


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        st.error("❌ SUPABASE_URL dan SUPABASE_ANON_KEY belum diset di .env")
        st.stop()
    return create_client(url, key)


# ─── AUTENTIKASI ────────────────────────────────────────────

def login_user(email: str, password: str):
    """Login ke Supabase Auth (Mengembalian session untuk cookie)"""
    sb = get_supabase()
    res = sb.auth.sign_in_with_password({"email": email, "password": password})
    return res


def restore_session_user(access_token: str, refresh_token: str):
    """Pulihkan sesi dari token (untuk persistent login)"""
    sb = get_supabase()
    try:
        # Panggil set_session, SDK akan mencoba me-refresh jika expired
        res = sb.auth.set_session(access_token, refresh_token)
        return res
    except Exception as e:
        print(f"DEBUG: Gagal pulihkan sesi: {e}")
        return None


def recover_session(refresh_token: str):
    """Pulihkan sesi hanya menggunakan refresh_token"""
    sb = get_supabase()
    try:
        # refresh_session akan menukarkan refresh_token lama dengan session baru
        res = sb.auth.refresh_session(refresh_token)
        return res
    except Exception as e:
        print(f"DEBUG: Gagal recover sesi: {e}")
        return None


def validate_user_email(email: str):
    """
    Validasi email user (Mockup untuk persistent login).
    Di produksi, sebaiknya cek ke tabel 'profiles' atau 'users' khusus.
    """
    if not email or "@" not in email:
        return None
    # Kembalikan objek yang menyerupai res.user dari Supabase
    class MockUser:
        def __init__(self, email):
            self.email = email
            self.id = "mock_id" # Bisa disesuaikan jika ada ID real
            
    return MockUser(email)


def daftar_user(email: str, password: str):
    """Daftar user baru (untuk registrasi awal/admin)"""
    sb = get_supabase()
    return sb.auth.sign_up({"email": email, "password": password})


def logout_user():
    """Sign out dari Supabase"""
    sb = get_supabase()
    sb.auth.sign_out()


# ─── LAYANAN ────────────────────────────────────────────────

def get_all_layanan() -> list[dict]:
    sb = get_supabase()
    res = sb.table("tabel_layanan").select("*").eq("is_active", True).order("nama_layanan").execute()
    return res.data or []


def upsert_layanan(nama: str, harga: int, estimasi: int, id: Optional[int] = None) -> dict:
    sb = get_supabase()
    data = {"nama_layanan": nama, "harga": harga, "estimasi_hari": estimasi}
    if id:
        data["id"] = id
    res = sb.table("tabel_layanan").upsert(data).execute()
    return res.data[0] if res.data else {}


# ─── BAHAN BAKU ─────────────────────────────────────────────

def get_all_bahan() -> list[dict]:
    sb = get_supabase()
    res = sb.table("tabel_bahan_baku").select("*").order("nama_bahan").execute()
    return res.data or []


def get_bahan_hampir_habis() -> list[dict]:
    """Ambil bahan dengan stok <= reorder_level"""
    bahan = get_all_bahan()
    return [b for b in bahan if b["stok_saat_ini"] <= b["reorder_level"]]


def update_stok_bahan(bahan_id: int, stok_baru: float) -> bool:
    if stok_baru < 0:
        raise ValueError("Stok tidak boleh minus")
    sb = get_supabase()
    sb.table("tabel_bahan_baku").update({"stok_saat_ini": stok_baru}).eq("id", bahan_id).execute()
    return True


def upsert_bahan(nama: str, stok: float, satuan: str, harga: int,
                 reorder: float, id: Optional[int] = None) -> dict:
    sb = get_supabase()
    data = {
        "nama_bahan": nama, "stok_saat_ini": stok, "satuan": satuan,
        "harga_per_satuan": harga, "reorder_level": reorder
    }
    if id:
        data["id"] = id
    res = sb.table("tabel_bahan_baku").upsert(data).execute()
    return res.data[0] if res.data else {}


# ─── BOM ────────────────────────────────────────────────────

def get_bom_by_layanan(layanan_id: int) -> list[dict]:
    sb = get_supabase()
    res = (sb.table("tabel_bom")
           .select("*, tabel_bahan_baku(nama_bahan, satuan, stok_saat_ini)")
           .eq("layanan_id", layanan_id)
           .execute())
    return res.data or []


def get_all_bom() -> list[dict]:
    sb = get_supabase()
    res = (sb.table("tabel_bom")
           .select("*, tabel_layanan(nama_layanan), tabel_bahan_baku(nama_bahan, satuan)")
           .execute())
    return res.data or []


def upsert_bom(layanan_id: int, bahan_id: int, jumlah: float) -> dict:
    sb = get_supabase()
    res = sb.table("tabel_bom").upsert({
        "layanan_id": layanan_id,
        "bahan_id": bahan_id,
        "jumlah_pemakaian": jumlah
    }, on_conflict="layanan_id,bahan_id").execute()
    return res.data[0] if res.data else {}


def delete_bom(bom_id: int) -> bool:
    sb = get_supabase()
    sb.table("tabel_bom").delete().eq("id", bom_id).execute()
    return True


# ─── TRANSAKSI SALES ────────────────────────────────────────

def get_all_transaksi(limit: int = 100, offset: int = 0, status_filter: Optional[str] = None) -> list[dict]:
    sb = get_supabase()
    q = (sb.table("tabel_transaksi_sales")
         .select("*, tabel_layanan(nama_layanan, estimasi_hari)")
         .order("created_at", desc=True)
         .range(offset, offset + limit - 1))
    if status_filter and status_filter != "Semua":
        q = q.eq("status", status_filter)
    return q.execute().data or []


def get_total_transaksi_count(status_filter: Optional[str] = None) -> int:
    sb = get_supabase()
    q = sb.table("tabel_transaksi_sales").select("*", count="exact")
    if status_filter and status_filter != "Semua":
        q = q.eq("status", status_filter)
    res = q.execute()
    return res.count if res.count is not None else 0


def get_transaksi_aktif() -> list[dict]:
    """Order yang belum diambil"""
    sb = get_supabase()
    res = (sb.table("tabel_transaksi_sales")
           .select("*, tabel_layanan(nama_layanan)")
           .not_.eq("status", "Diambil")
           .order("created_at", desc=True)
           .execute())
    return res.data or []


def buat_transaksi(customer: str, wa: str, layanan_id: int,
                    total: int, foto_url: str = "", catatan: str = "",
                    email: str = "") -> dict:
    """
    Buat transaksi baru. 
    NOTE: Trigger 'trigger_potong_stok' di DB otomatis memotong stock bahan baku 
    jika status awal adalah 'Cuci'.
    """
    sb = get_supabase()
    res = sb.table("tabel_transaksi_sales").insert({
        "customer_name": customer,
        "whatsapp_no": wa,
        "customer_email": email,
        "layanan_id": layanan_id,
        "total_bayar": total,
        "foto_url": foto_url,
        "catatan": catatan,
        "status": "Cuci",
        "is_paid": False,
    }).execute()
    return res.data[0] if res.data else {}


def update_status_transaksi(trx_id: int, status_baru: str) -> dict:
    """
    Update status pengerjaan.
    NOTE: Trigger 'trigger_potong_stok' di DB otomatis memotong stock bahan baku 
    jika status berubah menjadi 'Cuci'.
    """
    sb = get_supabase()
    res = (sb.table("tabel_transaksi_sales")
           .update({"status": status_baru})
           .eq("id", trx_id)
           .execute())
    return res.data[0] if res.data else {}


def update_bayar_transaksi(trx_id: int, is_paid: bool) -> dict:
    sb = get_supabase()
    res = (sb.table("tabel_transaksi_sales")
           .update({"is_paid": is_paid})
           .eq("id", trx_id)
           .execute())
    return res.data[0] if res.data else {}


# ─── PENGELUARAN ────────────────────────────────────────────

def get_all_pengeluaran(bulan: Optional[int] = None, tahun: Optional[int] = None) -> list[dict]:
    sb = get_supabase()
    q = sb.table("tabel_pengeluaran").select("*").order("tanggal", desc=True)
    if bulan and tahun:
        awal = f"{tahun}-{bulan:02d}-01"
        last_day = calendar.monthrange(tahun, bulan)[1]
        akhir = f"{tahun}-{bulan:02d}-{last_day}"
        q = q.gte("tanggal", awal).lte("tanggal", akhir)
    return q.execute().data or []


def buat_pengeluaran(kategori: str, nama: str, jumlah: int,
                     tanggal: date, ket: str = "") -> dict:
    sb = get_supabase()
    res = sb.table("tabel_pengeluaran").insert({
        "kategori": kategori,
        "nama_biaya": nama,
        "jumlah": jumlah,
        "tanggal": str(tanggal),
        "keterangan": ket,
    }).execute()
    return res.data[0] if res.data else {}


def delete_pengeluaran(pen_id: int) -> bool:
    sb = get_supabase()
    sb.table("tabel_pengeluaran").delete().eq("id", pen_id).execute()
    return True


# ─── KALKULASI KEUANGAN ─────────────────────────────────────

def hitung_keuangan_bulan(bulan: int, tahun: int) -> dict:
    """Hitung laba bersih bulan tertentu"""
    trx = get_all_transaksi(limit=9999)
    pengeluaran = get_all_pengeluaran(bulan, tahun)
    bahan = get_all_bahan()

    total_sales = sum(
        t["total_bayar"] for t in trx
        if t["is_paid"] and
        parse_iso(t["created_at"]).month == bulan and
        parse_iso(t["created_at"]).year == tahun
    )

    total_fixed = sum(p["jumlah"] for p in pengeluaran if p["kategori"] == "Fixed Cost")
    total_variable = sum(p["jumlah"] for p in pengeluaran if p["kategori"] == "Variable Cost")
    total_pengeluaran = total_fixed + total_variable

    # Estimasi nilai bahan terpakai (dari semua BOM yang diproses bulan ini)
    bahan_terpakai = 0
    for t in trx:
        tgl = parse_iso(t["created_at"])
        if tgl.month == bulan and tgl.year == tahun and t["status"] in ["Cuci", "Selesai", "Diambil"]:
            if t.get("layanan_id"):
                bom = get_bom_by_layanan(t["layanan_id"])
                for b in bom:
                    bahan_info = next((x for x in bahan if x["id"] == b["bahan_id"]), None)
                    if bahan_info:
                        bahan_terpakai += b["jumlah_pemakaian"] * bahan_info["harga_per_satuan"]

    laba_bersih = total_sales - bahan_terpakai - total_pengeluaran

    return {
        "total_sales": total_sales,
        "bahan_terpakai": bahan_terpakai,
        "fixed_cost": total_fixed,
        "variable_cost": total_variable,
        "total_pengeluaran": total_pengeluaran,
        "laba_bersih": laba_bersih,
    }


# ─── PROFIL TOKO ────────────────────────────────────────────

def get_profil_toko() -> dict:
    """Ambil data profil toko (hanya 1 baris id=1)"""
    sb = get_supabase()
    res = sb.table("tabel_profil_toko").select("*").eq("id", 1).execute()
    if res.data:
        return res.data[0]
    # Fallback jika kosong (minimalis)
    return {"nama_toko": "Hubb_Shoestreatment", "alamat": "", "no_whatsapp": ""}


def update_profil_toko(nama: str, alamat: str, wa: str, email: str) -> dict:
    sb = get_supabase()
    res = sb.table("tabel_profil_toko").upsert({
        "id": 1,
        "nama_toko": nama,
        "alamat": alamat,
        "no_whatsapp": wa,
        "email_toko": email,
        "updated_at": "now()"
    }).execute()
    return res.data[0] if res.data else {}


# ─── UPLOAD FOTO ────────────────────────────────────────────

def upload_foto_sepatu(file_bytes: bytes, filename: str) -> str:
    """Upload ke Supabase Storage, return public URL"""
    sb = get_supabase()
    path = f"orders/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    sb.storage.from_("foto-sepatu").upload(path, file_bytes, {"content-type": "image/jpeg"})
    url_res = sb.storage.from_("foto-sepatu").get_public_url(path)
    return url_res
