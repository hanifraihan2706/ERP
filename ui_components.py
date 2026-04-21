"""
ui_components.py — Komponen UI reusable
Format rupiah, nota digital, metric cards, dll
"""
import streamlit as st
from datetime import datetime


def parse_iso(dt_str: str) -> datetime:
    """Helper untuk parsing ISO format dari Supabase yang variatif (milidetik)."""
    if not dt_str:
        return None
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
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


def fmt_rupiah(angka: int) -> str:
    return f"Rp {int(angka):,}".replace(",", ".")


def metric_card(label: str, value: str, delta: str = "", color: str = "#1D9E75"):
    """KPI card dengan warna custom dan efek hover"""
    st.markdown(f"""
    <div class="kpi-card" style="
        background: {color}15;
        border-left: 4px solid {color};
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 12px;
        transition: all 0.3s ease;
    ">
        <div style="font-size:13px;color:#666;margin-bottom:6px">{label}</div>
        <div style="font-size:26px;font-weight:800;color:{color}">{value}</div>
        {"<div style='font-size:12px;color:#999;margin-top:4px'>" + delta + "</div>" if delta else ""}
    </div>
    """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    color_map = {
        "Cuci":    ("#3B82F6", "#DBEAFE"), # Blue
        "Selesai": ("#10B981", "#D1FAE5"), # Green
        "Diambil": ("#6B7280", "#F3F4F6"),
    }
    fg, bg = color_map.get(status, ("#000", "#eee"))
    return (f'<span style="background:{bg};color:{fg};padding:3px 10px;'
            f'border-radius:12px;font-size:12px;font-weight:600">{status}</span>')


def generate_nota(trx: dict, layanan_nama: str, shop_profile: dict = None) -> str:
    """Generate nota digital sebagai string markdown"""
    tgl = parse_iso(trx["created_at"])
    paid = "LUNAS" if trx["is_paid"] else "BELUM BAYAR"
    
    shop_name = shop_profile.get("nama_toko", "ERP Cuci Sepatu") if shop_profile else "ERP Cuci Sepatu"
    shop_addr = shop_profile.get("alamat", "") if shop_profile else ""
    
    return f"""
---
### {shop_name.upper()}
**No. Order:** `#{trx['id']:05d}`
**Tanggal:** {tgl.strftime('%d %B %Y, %H:%M')}

| | |
|---|---|
| Customer | {trx['customer_name']} |
| WA | {trx.get('whatsapp_no','-')} |
| Layanan | {layanan_nama} |
| Status | {trx['status']} |
| Pembayaran | {paid} |

**Total: {fmt_rupiah(trx['total_bayar'])}**

_{trx.get('catatan', '')}_

{f'* {shop_addr}*' if shop_addr else ""}
*Terima kasih telah mempercayakan sepatu Anda kepada kami!*
---
"""


def mobile_header(title: str, subtitle: str = ""):
    """Header mobile-friendly"""
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1D9E75, #0F6E56);
        color: white;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 20px;
    ">
        <div style="font-size:20px;font-weight:700">{title}</div>
        {"<div style='font-size:13px;opacity:0.85;margin-top:4px'>" + subtitle + "</div>" if subtitle else ""}
    </div>
    """, unsafe_allow_html=True)


def confirm_dialog(key: str, label: str) -> bool:
    """Simple confirm button dengan double-click pattern"""
    if f"confirm_{key}" not in st.session_state:
        st.session_state[f"confirm_{key}"] = False

    if not st.session_state[f"confirm_{key}"]:
        if st.button(label, key=f"btn1_{key}"):
            st.session_state[f"confirm_{key}"] = True
            st.rerun()
        return False
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Ya, lanjutkan", key=f"btn_yes_{key}", type="primary"):
                st.session_state[f"confirm_{key}"] = False
                return True
        with col2:
            if st.button("Batal", key=f"btn_no_{key}"):
                st.session_state[f"confirm_{key}"] = False
                st.rerun()
        return False
