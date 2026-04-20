"""
telegram_notif.py — Modul notifikasi Telegram
Kirim notifikasi order baru & laporan harian jam 21.00
"""
import os
import requests
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _send(text: str, chat_id: Optional[str] = None) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        cid = chat_id or TELEGRAM_CHAT_ID
        r = requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": cid,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def notif_order_baru(customer: str, layanan: str, total: int, wa: str = "") -> bool:
    wa_info = f"\n📱 WA: {wa}" if wa else ""
    pesan = (
        f"🥿 *ORDER BARU MASUK!*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Customer: *{customer}*{wa_info}\n"
        f"🧹 Layanan: {layanan}\n"
        f"💰 Total: *Rp {total:,}*\n"
        f"🕐 Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"_Segera diproses ya!_ ✨"
    )
    return _send(pesan)


def notif_stok_menipis(bahan_list: list[dict]) -> bool:
    if not bahan_list:
        return False
    items = "\n".join(
        f"  ⚠️ {b['nama_bahan']}: {b['stok_saat_ini']} {b['satuan']} (min: {b['reorder_level']})"
        for b in bahan_list
    )
    pesan = (
        f"🚨 *PERINGATAN: STOK MENIPIS!*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{items}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"_Segera lakukan restok!_"
    )
    return _send(pesan)


def laporan_harian(stats: dict) -> bool:
    """Kirim laporan harian ringkasan keuangan"""
    tgl = datetime.now().strftime("%d/%m/%Y")
    laba = stats.get("laba_bersih", 0)
    status_laba = "✅ UNTUNG" if laba >= 0 else "❌ RUGI"
    pesan = (
        f"📊 *LAPORAN HARIAN — {tgl}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💵 Total Sales: Rp {stats.get('total_sales', 0):,}\n"
        f"🧴 Bahan Terpakai: Rp {stats.get('bahan_terpakai', 0):,}\n"
        f"🏢 Fixed Cost: Rp {stats.get('fixed_cost', 0):,}\n"
        f"📦 Variable Cost: Rp {stats.get('variable_cost', 0):,}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💹 *Laba Bersih: Rp {laba:,}* {status_laba}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 Order aktif: {stats.get('order_aktif', 0)} sepatu\n"
        f"🎉 Selesai hari ini: {stats.get('selesai_hari_ini', 0)} sepatu"
    )
    return _send(pesan)


def notif_status_berubah(customer: str, status_baru: str, layanan: str) -> bool:
    emoji_map = {
        "Cuci": "🫧", "Jemur": "☀️", "Selesai": "✅", "Diambil": "🎁"
    }
    emoji = emoji_map.get(status_baru, "📦")
    pesan = (
        f"{emoji} *Update Order: {customer}*\n"
        f"Layanan {layanan} → *{status_baru}*\n"
        f"_{datetime.now().strftime('%H:%M WIB')}_"
    )
    return _send(pesan)
