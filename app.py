"""
app.py — ERP Cloud UMKM Cuci Sepatu (REFACTORED FOR PERFORMANCE)
Optimized with Caching, Fragments, and Lazy Initialization.
"""
import streamlit as st
import os
import atexit
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from io import BytesIO

# [PERF] Lazy import handling in specific sections
import database as db
import telegram_notif as tg
import email_service as mail
import extra_streamlit_components as stx
from ui_components import (
    fmt_rupiah, metric_card, status_badge,
    generate_nota, mobile_header, confirm_dialog
)

# ── KONFIGURASI HALAMAN ─────────────────────────────────────
st.set_page_config(
    page_title="ERP Cuci Sepatu",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# [PERF] FIX 3: Cache CSS with @st.cache_resource
@st.cache_resource
def _get_css() -> str:
    return """
    <style>
        /* [PERF] CSS di-cache agar tidak di-parse ulang setiap rerun */
        .block-container { padding: 1rem 1rem 2rem; max-width: 1000px; }
        .kpi-card { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); cursor: default; }
        .kpi-card:hover { transform: translateY(-5px); box-shadow: 0 12px 24px rgba(0,0,0,0.12); filter: brightness(1.02); }

        div.st-key-nav_owner > div[role="radiogroup"],
        div.st-key-main_nav_radio > div[role="radiogroup"] {
            background-color: #f8f9fa; padding: 6px; border-radius: 16px; gap: 6px; border: 1px solid #edf2f7;
            width: 100% !important; display: flex !important; justify-content: space-between;
        }
        div.st-key-nav_owner [data-baseweb="radio"],
        div.st-key-main_nav_radio [data-baseweb="radio"] {
            flex: 1 1 0% !important; white-space: nowrap !important; display: flex !important;
            justify-content: center !important; align-items: center !important; padding: 12px 4px !important;
            border-radius: 12px !important; background-color: transparent !important; color: #4A5568 !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important; cursor: pointer; margin: 0 !important;
        }
        div.st-key-nav_owner [role="radiogroup"] label > div:first-child,
        div.st-key-main_nav_radio [role="radiogroup"] label > div:first-child { display: none !important; }
        
        div.st-key-nav_owner label[data-baseweb="radio"]:has(input:checked),
        div.st-key-main_nav_radio label[data-baseweb="radio"]:has(input:checked) {
            background-color: #1D9E75 !important; box-shadow: 0 8px 20px rgba(29, 158, 117, 0.3) !important; transform: translateY(-2px);
        }
        div.st-key-nav_owner label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p,
        div.st-key-main_nav_radio label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p {
            color: white !important; font-weight: 700 !important;
        }

        .stButton > button { width: 100%; border-radius: 10px; font-weight: 600; height: 48px; font-size: 16px !important; }
        .stButton > button[kind="primary"] { background: linear-gradient(135deg, #1D9E75, #158060); border: none; box-shadow: 0 4px 6px rgba(29, 158, 117, 0.2); }
        
        @media (max-width: 768px) {
            .block-container { padding-bottom: 120px !important; }
            div.st-key-nav_owner, div.st-key-main_nav_radio {
                position: fixed; bottom: 0; left: 0; right: 0; z-index: 999999; background: white;
                padding: 12px 10px 24px; box-shadow: 0 -8px 24px rgba(0,0,0,0.08); border-top: 1px solid #f0f0f0;
            }
            div.st-key-nav_owner > div[role="radiogroup"],
            div.st-key-main_nav_radio > div[role="radiogroup"] { overflow-x: auto !important; flex-wrap: nowrap !important; justify-content: flex-start !important; padding-bottom: 12px; }
            div.st-key-nav_owner [data-baseweb="radio"],
            div.st-key-main_nav_radio [data-baseweb="radio"] { min-width: 110px !important; font-size: 13px !important; padding: 10px 8px !important; }
        }
        #MainMenu, footer { visibility: hidden; }
    </style>
    """

# ── [PERF] FIX 1: Database Caching Wrappers ─────────────────
@st.cache_data(ttl=30)
def cached_transaksi_aktif():
    return db.get_transaksi_aktif()

@st.cache_data(ttl=300)
def cached_profil_toko():
    return db.get_profil_toko()

@st.cache_data(ttl=60)
def cached_bahan_hampir_habis():
    return db.get_bahan_hampir_habis()

@st.cache_data(ttl=120)
def cached_all_layanan():
    return db.get_all_layanan()

@st.cache_data(ttl=60)
def cached_all_bahan():
    return db.get_all_bahan()

@st.cache_data(ttl=15, show_spinner=False)
def cached_transaksi_page(limit, offset, status_filter):
    """Composite key cache: (limit, offset, status_filter)"""
    return db.get_all_transaksi(limit=limit, offset=offset, status_filter=status_filter)

@st.cache_data(ttl=15, show_spinner=False)
def cached_total_transaksi_count(status_filter):
    """Cache for total record count"""
    return db.get_total_transaksi_count(status_filter=status_filter)

@st.cache_data(ttl=120, max_entries=24)
def cached_keuangan_bulan(bulan, tahun):
    return db.hitung_keuangan_bulan(bulan, tahun)

def clear_db_caches():
    """Memberihkan cache saat ada perubahan data di DB"""
    cached_transaksi_aktif.clear()
    cached_all_bahan.clear()
    cached_bahan_hampir_habis.clear()
    cached_all_layanan.clear()
    cached_keuangan_bulan.clear()
    cached_transaksi_page.clear()
    cached_total_transaksi_count.clear()

# ── [PERF] FIX 5: Optimized Scheduler ───────────────────────
def setup_scheduler():
    # [PERF] Early return sebelum import untuk zero-cost rerun
    if "scheduler_started" in st.session_state:
        return 
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        import pytz

        def kirim_laporan():
            now = datetime.now()
            stats = db.hitung_keuangan_bulan(now.month, now.year)
            aktif = db.get_transaksi_aktif()
            stats["order_aktif"] = len(aktif)
            stats["selesai_hari_ini"] = sum(1 for t in aktif if t.get("status") == "Selesai")
            tg.laporan_harian(stats)

            menipis = db.get_bahan_hampir_habis()
            if menipis:
                tg.notif_stok_menipis(menipis)

        scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Jakarta"))
        scheduler.add_job(kirim_laporan, "cron", hour=21, minute=0)
        scheduler.start()
        atexit.register(scheduler.shutdown)
        st.session_state.scheduler_started = True
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# HALAMAN: DASHBOARD
# ═══════════════════════════════════════════════════════════
def halaman_dashboard(profil=None):
    is_owner = st.session_state.get("authenticated", False)
    nama_toko = profil.get("nama_toko", "ERP Toko") if profil else "ERP Toko"
    
    if not is_owner:
        # ── LAYER 1: CUSTOMER PORTAL (LANDING) ──
        st.markdown(f"""
        <div style="text-align: center; padding: 2.5rem 0 1rem 0;">
            <h1 style="color: #1D9E75; margin-bottom: 0.5rem; font-size: 2.5rem;">{nama_toko}</h1>
            <p style="color: #666; font-size: 1.2rem;">Solusi Cuci Sepatu Profesional & Cepat</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            <div style="background:#1D9E75; padding:25px; border-radius:20px; color:white; text-align:center; min-height:180px">
                <div style="font-size:40px">👟</div>
                <h3 style="color:white; margin:10px 0">Order Baru</h3>
                <p style="font-size:14px; opacity:0.9">Input pesanan cuci sepatu Anda di sini</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("MULAI ORDER SEKARANG", type="primary", use_container_width=True):
                # [PERF] FIX 6: Simplified Routing
                st.session_state.current_page = "order_baru"
                st.rerun()

        with col2:
            st.markdown("""
            <div style="background:#3B82F6; padding:25px; border-radius:20px; color:white; text-align:center; min-height:180px">
                <div style="font-size:40px">🔍</div>
                <h3 style="color:white; margin:10px 0">Cek Status</h3>
                <p style="font-size:14px; opacity:0.9">Pantau proses pengerjaan sepatu Anda</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("PANTAU STATUS PENGERJAAN", type="secondary", use_container_width=True):
                st.session_state.current_page = "order_status"
                st.rerun()

        st.markdown("---")
        # [PERF] FIX 1: Use Cached Data
        transaksi_aktif = cached_transaksi_aktif()
        st.subheader("Update Sales Hari Ini")
        col_st1, col_st2 = st.columns(2)
        with col_st1:
            metric_card("Sepatu Sedang Proses", f"{len(transaksi_aktif)} pasang", color="#3B82F6")
        with col_st2:
            cnt_selesai = sum(1 for t in transaksi_aktif if t["status"] == "Selesai")
            metric_card("Siap Diambil", f"{cnt_selesai} pasang", color="#10B981")

    else:
        # ── LAYER 2: OWNER ADMIN PANEL ──
        mobile_header(nama_toko, f"Admin Dashboard · {datetime.now().strftime('%d %b %Y')}")
        
        now = datetime.now()
        stats = cached_keuangan_bulan(now.month, now.year)
        transaksi_aktif = cached_transaksi_aktif()
        bahan_menipis = cached_bahan_hampir_habis()

        if bahan_menipis:
            st.warning(f"⚠️ Stok menipis: **{', '.join(b['nama_bahan'] for b in bahan_menipis)}**")

        col1, col2 = st.columns(2)
        with col1:
            metric_card("Pendapatan Bulan Ini", fmt_rupiah(stats["total_sales"]), color="#1D9E75")
            metric_card("Order Aktif", f"{len(transaksi_aktif)} sepatu", color="#3B82F6")
        with col2:
            laba = stats["laba_bersih"]
            metric_card("Laba Bersih", fmt_rupiah(laba), delta="Bulan ini", color="#1D9E75" if laba >= 0 else "#EF4444")
            metric_card("Stok Menipis", f"{len(bahan_menipis)} bahan", color="#F59E0B")

        st.markdown("---")
        st.subheader("Biaya Operasional")
        
        labels = ["Bahan Terpakai", "Fixed Cost", "Variable Cost"]
        values = [max(stats["bahan_terpakai"], 0), max(stats["fixed_cost"], 0), max(stats["variable_cost"], 0)]
        if sum(values) > 0:
            fig = px.pie(names=labels, values=values, color_discrete_sequence=["#F59E0B","#EF4444","#F97316"], hole=0.5)
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=280, showlegend=True, legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig, use_container_width=True)
        
        if transaksi_aktif:
            st.subheader("📋 Daftar Order Berjalan (Manajemen Cepat)")
            fragment_order_list(is_owner=True, profil=profil)


# ═══════════════════════════════════════════════════════════
# HALAMAN: POS / ORDER BARU
# ═══════════════════════════════════════════════════════════
# [PERF] FIX 2: Implementation of @st.fragment for POS Form
@st.fragment
def fragment_form_pos(profil, layanan_list):
    with st.form("form_order", clear_on_submit=True):
        st.markdown("##### 👤 Data Customer")
        nama = st.text_input("Nama Customer *", placeholder="Budi Santoso")
        wa   = st.text_input("No. WhatsApp", placeholder="08123456789")

        st.markdown("##### Layanan")
        layanan_options = {f"{l['nama_layanan']} — {fmt_rupiah(l['harga'])}": l for l in layanan_list}
        layanan_pilih = st.selectbox("Pilih Layanan *", options=list(layanan_options.keys()))
        layanan_obj = layanan_options[layanan_pilih]

        bom = db.get_bom_by_layanan(layanan_obj["id"])
        if bom:
            with st.expander("🧴 Bahan yang digunakan"):
                for b in bom:
                    bahan_info = b.get("tabel_bahan_baku", {})
                    st.write(f"• {bahan_info.get('nama_bahan','?')}: {b['jumlah_pemakaian']} {bahan_info.get('satuan','')}")

        st.markdown("##### Pembayaran")
        total = st.number_input("Total Bayar (Rp) *", value=layanan_obj["harga"], min_value=1000, step=1000)
        is_paid = st.checkbox("Sudah bayar (lunas)")

        st.markdown("##### 📸 Foto Sepatu")
        foto = st.file_uploader("Upload foto (opsional) - Maks 1 MB", type=["jpg","jpeg","png"])
        catatan = st.text_area("Catatan")
        
        st.markdown("---")
        email_cust = st.text_input("Email Customer")

        submitted = st.form_submit_button("✅ SIMPAN ORDER", type="primary", use_container_width=True)

    if submitted:
        if not nama:
            st.error("Nama customer wajib diisi!")
            return
        if total < 1000:
            st.error("Total bayar minimal Rp1.000!")
            return
        if foto and foto.size > 1 * 1024 * 1024:
            st.error("❌ Ukuran foto terlalu besar!")
            return

        with st.spinner("Menyimpan order..."):
            foto_url = ""
            if foto:
                try:
                    foto_url = db.upload_foto_sepatu(foto.read(), foto.name)
                except Exception: pass

            trx = db.buat_transaksi(
                customer=nama.strip(), wa=wa.strip(), layanan_id=layanan_obj["id"],
                total=int(total), foto_url=foto_url, catatan=catatan, email=email_cust.strip()
            )
            if is_paid: db.update_bayar_transaksi(trx["id"], True)
            
            # [PERF] Cache clearance after write
            clear_db_caches()
            
            tg.notif_order_baru(nama, layanan_obj["nama_layanan"], int(total), wa)
            if email_cust.strip():
                tgl_str = db.parse_iso(trx["created_at"]).strftime("%d %B %Y, %H:%M")
                mail.kirim_struk(email=email_cust.strip(), trx_id=trx["id"], customer=nama, 
                                 layanan=layanan_obj["nama_layanan"], total=int(total), 
                                 tanggal_str=tgl_str, catatan=catatan)

        st.success(f"✅ Order #{trx['id']:05d} disimpan!")
        st.markdown(generate_nota(trx, layanan_obj["nama_layanan"], shop_profile=profil))

def halaman_pos(profil=None):
    mobile_header("Input Order Baru", "Form Point of Sales")
    layanan_list = cached_all_layanan()
    if not layanan_list:
        st.error("Belum ada layanan.")
        return
    fragment_form_pos(profil, layanan_list)


# ═══════════════════════════════════════════════════════════
# HALAMAN: ORDER LIST (MONITOR)
# ═══════════════════════════════════════════════════════════
@st.fragment
def fragment_order_list(is_owner, profil):
    status_options = ["Semua", "Cuci", "Selesai", "Diambil"]
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        filter_status = st.selectbox("Filter Status", status_options, key="filter_status_frag")
    with col_f2:
        st.write(""); st.write("")
        if st.button("🔄 Refresh", use_container_width=True, key="refresh_frag"):
            st.rerun()

    PAGE_SIZE = 10
    total_count = cached_total_transaksi_count(status_filter=filter_status)
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    
    col_p1, col_p2 = st.columns([3, 1])
    with col_p2:
        page = st.number_input("Halaman", min_value=1, max_value=total_pages, step=1, key="page_nav")
    with col_p1:
        st.caption(f"Menampilkan total {total_count} order (Hal. {page}/{total_pages})")

    offset = (page - 1) * PAGE_SIZE
    transaksi = cached_transaksi_page(limit=PAGE_SIZE, offset=offset, status_filter=filter_status)

    if not transaksi:
        st.info("Tidak ada order pada kriteria ini.")
        return

    # [PERF] FIX: Optimized View for Owner (Single Dataframe for bulk info)
    if is_owner:
        df_rows = []
        for t in transaksi:
            layanan = t.get("tabel_layanan") or {}
            df_rows.append({
                "ID": f"#{t['id']:05d}",
                "Customer": t['customer_name'],
                "Layanan": layanan.get("nama_layanan", "-"),
                "Total": fmt_rupiah(t['total_bayar']),
                "Status": t['status'],
                "Paid": "✅" if t['is_paid'] else "⏳"
            })
        st.dataframe(pd.DataFrame(df_rows), use_container_width=True, hide_index=True)
        st.caption("Gunakan ekspander di bawah untuk aksi cepat per item:")

    STATUS_NEXT = {"Cuci": "Selesai", "Selesai": "Diambil"}

    for t in transaksi:
        layanan = t.get("tabel_layanan") or {}
        layanan_nama = layanan.get("nama_layanan", "-")
        tgl = db.parse_iso(t["created_at"])
        
        # [PERF] Use expander for actions, labeling with emoji because HTML span is not supported in expander title
        st_emoji = {"Cuci": "🧼", "Selesai": "✅", "Diambil": "📦"}.get(t['status'], "🏷️")
        with st.expander(f"{st_emoji} #{t['id']:05d} · {t['customer_name']} ({t['status']})", expanded=not is_owner):
            # Show the stylized badge inside the expander where HTML is allowed
            st.markdown(f"{status_badge(t['status'])} | **Layanan:** {layanan_nama} | **Waktu:** {tgl.strftime('%d/%m %H:%M')}", unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                next_status = STATUS_NEXT.get(t["status"])
                if next_status == "Selesai":
                    if st.button(f"➡️ Ke {next_status}", key=f"mv_{t['id']}"):
                        db.update_status_transaksi(t["id"], next_status)
                        clear_db_caches()
                        tg.notif_status_berubah(t["customer_name"], next_status, layanan_nama)
                        st.rerun()
                elif next_status == "Diambil":
                    st.warning(f"Konfirmasi pengambilan?")
                    if st.button("✅ Konfirmasi", key=f"conf_{t['id']}", use_container_width=True):
                        db.update_status_transaksi(t["id"], next_status)    
                        clear_db_caches()
                        tg.notif_status_berubah(t["customer_name"], next_status, layanan_nama)
                        st.rerun()
            with col2:
                if not t["is_paid"] and st.button("💰 Lunas", key=f"pay_{t['id']}"):
                    db.update_bayar_transaksi(t["id"], True)
                    clear_db_caches()
                    st.rerun()
            with col3:
                if st.button("🧾 Nota", key=f"nota_{t['id']}"):
                    st.markdown(generate_nota(t, layanan_nama, shop_profile=profil))
            with col4:
                wa_no = t.get("whatsapp_no")
                if wa_no:
                    wa_clean = ''.join(filter(str.isdigit, wa_no))
                    wa_clean = wa_clean.lstrip("0")   # Hapus semua awalan 0
                    if not wa_clean.startswith("62"):
                        wa_clean = "62" + wa_clean
                    msg = f"Halo {t['customer_name']}, order #{t['id']:05d} status: *{t['status']}*."
                    wa_url = f"https://wa.me/{wa_clean}?text={msg.replace(' ', '%20')}"
                    st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="width:100%;height:38px;border-radius:8px;border:1px solid #25D366;background:white;color:#25D366;font-weight:600;cursor:pointer;font-size:12px">💬 WA</button></a>''', unsafe_allow_html=True)
            st.markdown("<p style='margin-bottom:20px'></p>", unsafe_allow_html=True)

def halaman_order(profil=None):
    is_owner = st.session_state.get("authenticated", False)
    mobile_header("Status Order", "Monitoring operasional")
    fragment_order_list(is_owner, profil)


# ═══════════════════════════════════════════════════════════
# HALAMAN: INVENTORY
# ═══════════════════════════════════════════════════════════
# [PERF] FIX 2: @st.fragment for Stock Management
@st.fragment
def fragment_stok_bahan():
    bahan_list = cached_all_bahan()
    if not bahan_list:
        st.info("Belum ada bahan baku.")
        return
    
    rows = []
    for b in bahan_list:
        status_stok = "⚠️ MENIPIS" if b["stok_saat_ini"] <= b["reorder_level"] else "✅ Aman"
        rows.append({"Nama Bahan": b["nama_bahan"], "Stok": f"{b['stok_saat_ini']} {b['satuan']}", 
                    "Reorder": f"{b['reorder_level']} {b['satuan']}", "Harga/Satuan": fmt_rupiah(b["harga_per_satuan"]), "Status": status_stok})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Update Stok Manual")
    bahan_dict = {b["nama_bahan"]: b for b in bahan_list}
    pilih = st.selectbox("Pilih Bahan", list(bahan_dict.keys()), key="upd_bahan")
    bahan_sel = bahan_dict[pilih]
    stok_baru = st.number_input(f"Stok baru ({bahan_sel['satuan']})", value=float(bahan_sel["stok_saat_ini"]), min_value=0.0, step=1.0)
    if st.button("Update Stok", type="primary"):
        db.update_stok_bahan(bahan_sel["id"], stok_baru)
        clear_db_caches()
        st.success("✅ Stok diperbarui!")
        st.rerun()

def halaman_inventory(profil=None):
    mobile_header("Inventory & BOM", "Stok bahan baku & resep")
    tab1, tab2, tab3 = st.tabs(["Stok Bahan", "Kelola BOM", "Tambah Bahan"])
    with tab1: fragment_stok_bahan()
    with tab2:
        layanan_list = cached_all_layanan()
        bahan_list = cached_all_bahan()
        if not layanan_list or not bahan_list:
            st.warning("Tambahkan data Master terlebih dahulu.")
        else:
            layanan_dict = {l["nama_layanan"]: l for l in layanan_list}
            pilih_layanan = st.selectbox("Pilih Layanan", list(layanan_dict.keys()), key="bom_lay")
            lay_obj = layanan_dict[pilih_layanan]
            bom = db.get_bom_by_layanan(lay_obj["id"])
            if bom:
                for b in bom:
                    bi = b.get("tabel_bahan_baku", {})
                    col1, col2 = st.columns([3, 1])
                    col1.write(f"🧴 {bi.get('nama_bahan','')} — {b['jumlah_pemakaian']} {bi.get('satuan','')}")
                    if col2.button("🗑️", key=f"delbom_{b['id']}"):
                        db.delete_bom(b["id"]); clear_db_caches(); st.rerun()
            
            st.markdown("**Tambah ke BOM:**")
            bahan_dict = {b["nama_bahan"]: b for b in bahan_list}
            pilih_bahan = st.selectbox("Bahan", list(bahan_dict.keys()))
            jumlah = st.number_input("Jumlah pemakaian", min_value=0.1, step=0.5)
            if st.button("➕ Tambah", type="primary"):
                db.upsert_bom(lay_obj["id"], bahan_dict[pilih_bahan]["id"], jumlah)
                clear_db_caches(); st.rerun()

    with tab3:
        with st.form("form_bahan", clear_on_submit=True):
            nama_b = st.text_input("Nama Bahan *")
            satuan = st.selectbox("Satuan", ["ml", "gr", "pcs", "liter", "kg"])
            stok_awal = st.number_input("Stok Awal", min_value=0.0)
            harga = st.number_input("Harga/Satuan", min_value=0)
            reorder = st.number_input("Reorder Level", min_value=0.0)
            if st.form_submit_button("💾 Simpan", type="primary"):
                if nama_b:
                    db.upsert_bahan(nama_b, stok_awal, satuan, harga, reorder)
                    clear_db_caches(); st.success("Bahan disimpan!"); st.rerun()


# ═══════════════════════════════════════════════════════════
# HALAMAN: KEUANGAN
# ═══════════════════════════════════════════════════════════
# [PERF] FIX 2: @st.fragment for Financial Report
@st.fragment
def fragment_laporan(bulan, tahun):
    stats = cached_keuangan_bulan(bulan, tahun)
    col1, col2 = st.columns(2)
    col1.metric("Total Sales", fmt_rupiah(stats["total_sales"]))
    col1.metric("Bahan Terpakai", fmt_rupiah(stats["bahan_terpakai"]))
    col2.metric("Fixed Cost", fmt_rupiah(stats["fixed_cost"]))
    col2.metric("Variable Cost", fmt_rupiah(stats["variable_cost"]))
    
    laba = stats["laba_bersih"]
    warna = "#10B981" if laba >= 0 else "#EF4444"
    st.markdown(f'<div style="background:{warna}10;border:2px solid {warna};border-radius:12px;padding:20px;text-align:center;">'
                f'<div style="color:{warna};font-weight:600">LABA BERSIH</div>'
                f'<div style="font-size:32px;font-weight:800;color:{warna}">{fmt_rupiah(laba)}</div></div>', unsafe_allow_html=True)

    fig = go.Figure(go.Waterfall(measure=["relative"]*4 + ["total"], x=["Sales","Bahan","Fixed","Var","Laba"], 
                                 y=[stats["total_sales"], -stats["bahan_terpakai"], -stats["fixed_cost"], -stats["variable_cost"], 0],
                                 decreasing={"marker":{"color":"#EF4444"}}, increasing={"marker":{"color":"#10B981"}}, totals={"marker":{"color":"#3B82F6"}}))
    fig.update_layout(height=250, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)

def halaman_keuangan(profil=None):
    mobile_header("Keuangan", "Laporan laba rugi")
    t1, t2 = st.tabs(["Laporan", "Catat Pengeluaran"])
    with t1:
        c1, c2 = st.columns(2)
        bulan = c1.selectbox("Bulan", list(range(1, 13)), index=datetime.now().month-1, format_func=lambda x: date(2024,x,1).strftime("%B"))
        tahun = c2.number_input("Tahun", value=datetime.now().year)
        fragment_laporan(bulan, tahun)
    with t2:
        with st.form("f_pengeluaran", clear_on_submit=True):
            kat = st.radio("Kategori", ["Fixed Cost", "Variable Cost"], horizontal=True)
            nama_b = st.text_input("Nama Biaya *")
            jumlah = st.number_input("Jumlah (Rp)", min_value=0)
            if st.form_submit_button("💾 Simpan", type="primary"):
                if not nama_b:
                    st.error("Nama biaya wajib diisi!")
                elif jumlah <= 0:
                    st.error("Jumlah pengeluaran harus lebih dari Rp0!")
                else:
                    db.buat_pengeluaran(kat, nama_b, jumlah, date.today(), "")
                    clear_db_caches(); st.success("Dicatat!"); st.rerun()


# ═══════════════════════════════════════════════════════════
# HALAMAN: MASTER & LOGIN
# ═══════════════════════════════════════════════════════════
def halaman_master(profil=None):
    mobile_header("Master", "Layanan & Toko")
    t1, t2 = st.tabs(["Layanan", "Profil Toko"])
    with t1:
        lays = cached_all_layanan()
        if lays: st.dataframe(pd.DataFrame(lays), use_container_width=True, hide_index=True)
        with st.form("f_lay"):
            n = st.text_input("Nama Layanan")
            h = st.number_input("Harga", min_value=0)
            e = st.number_input("Estimasi (Hari)", min_value=1)
            if st.form_submit_button("Simpan"):
                db.upsert_layanan(n, h, e); clear_db_caches(); st.rerun()
    with t2:
        with st.form("f_profil"):
            n = st.text_input("Nama Toko", profil.get("nama_toko",""))
            if st.form_submit_button("Simpan Profil"):
                db.update_profil_toko(n, "", "", ""); clear_db_caches(); st.rerun()

def halaman_login(profil=None, cm=None):
    st.markdown(f'<h1 style="text-align:center;color:#1D9E75">{profil.get("nama_toko","ERP")}</h1>', unsafe_allow_html=True)
    with st.form("login_form"):
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("MASUK", type="primary"):
            try:
                res = db.login_user(e, p)
                st.session_state.authenticated = True
                st.session_state.current_page = "dashboard"
                if cm: cm.set("washub_refresh_token", res.session.refresh_token, max_age=7200)
                st.rerun()
            except Exception as ex: st.error(f"Gagal: {ex}")


# ═══════════════════════════════════════════════════════════
# ROUTING UTAMA
# ═══════════════════════════════════════════════════════════
def main():
    # [PERF] FIX 3: Inject Cached CSS
    st.markdown(_get_css(), unsafe_allow_html=True)
    
    # [PERF] FIX 4: Lazy CookieManager initialization
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="cm_v2")
    cm = st.session_state.cookie_manager

    profil = cached_profil_toko()
    
    # [PERF] FIX 6: Simplified Routing State
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"
    
    # Initial Auto-Login check
    if not st.session_state.get("authenticated"):
        tkn = cm.get("washub_refresh_token")
        if tkn:
            res = db.recover_session(tkn)
            if res and res.user:
                st.session_state.authenticated = True
                st.session_state.current_page = "dashboard"
    
    setup_scheduler()
    is_owner = st.session_state.get("authenticated", False)

    if is_owner:
        st.markdown('<div style="background:#1D9E75;padding:8px;border-radius:8px;color:white;text-align:center;font-weight:700;">🔓 LOGIN OWNER AKTIF</div>', unsafe_allow_html=True)
        # 🟢 Menu Owner Lengkap (Hybrid)
        owner_nav = {
            "Dashboard": "dashboard", 
            "Monitor Order": "order_status", 
            "POS Admin": "pos", 
            "Inventory": "inventory", 
            "Keuangan": "keuangan", 
            "Master": "master", 
            "Keluar": "logout"
        }
        labels = list(owner_nav.keys())
        inv_owner_nav = {v: k for k, v in owner_nav.items()}
        
        # [FIX] Radio Sync Logic
        curr_page = st.session_state.current_page
        if curr_page == "home": curr_page = "dashboard" # Normalize home to dashboard for owner
        if curr_page == "order_baru": curr_page = "pos"
        
        curr_label = inv_owner_nav.get(curr_page, "Dashboard")
        def_idx = labels.index(curr_label) if curr_label in labels else 0
        
        sel = st.radio("", labels, index=def_idx, horizontal=True, label_visibility="collapsed", key="nav_owner")
        
        # Update current_page only if radio is clicked (interaction)
        if owner_nav[sel] != st.session_state.current_page:
            # Special case: don't overwrite if we are in a sub-state unless manual click
            if st.session_state.current_page in owner_nav.values() or sel != curr_label:
                st.session_state.current_page = owner_nav[sel]
    else:
        # Layer 1: Public
        if st.session_state.current_page != "home":
            if st.button("⬅️ Kembali ke Beranda"):
                st.session_state.current_page = "home"; st.rerun()

        st.markdown("<div style='text-align:right'>", unsafe_allow_html=True)
        pub_nav = {"Beranda": "home", "Monitor Order": "order_status", "Owner Login": "login"}
        labels = list(pub_nav.keys())
        inv_pub_nav = {v: k for k, v in pub_nav.items()}
        
        curr_page = st.session_state.current_page
        curr_p_label = inv_pub_nav.get(curr_page, "Beranda")
        def_p_idx = labels.index(curr_p_label) if curr_p_label in labels else 0
        
        sel_p = st.radio("", labels, index=def_p_idx, horizontal=True, label_visibility="collapsed", key="nav_public")
        
        # Update current_page only if interaction happened
        if pub_nav[sel_p] != st.session_state.current_page:
            if st.session_state.current_page in pub_nav.values() or sel_p != curr_p_label:
                st.session_state.current_page = pub_nav[sel_p]

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Routing Final
    cp = st.session_state.current_page
    if cp in ["home", "dashboard"]: halaman_dashboard(profil)
    elif cp in ["pos", "order_baru"]: halaman_pos(profil)
    elif cp == "order_status": halaman_order(profil)
    elif cp == "inventory": halaman_inventory(profil)
    elif cp == "keuangan": halaman_keuangan(profil)
    elif cp == "master": halaman_master(profil)
    elif cp == "login": halaman_login(profil, cm)
    elif cp == "logout":
        db.logout_user()
        st.session_state.authenticated = False
        st.session_state.current_page = "home"
        cm.delete("washub_refresh_token")
        st.rerun()

if __name__ == "__main__":
    main()