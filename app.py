"""
app.py — ERP Cloud UMKM Cuci Sepatu
Entry point utama Streamlit
Jalankan: streamlit run app.py
"""
import streamlit as st
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from io import BytesIO

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

# ── CSS MOBILE-FIRST ────────────────────────────────────────
st.markdown("""
<style>
    /* Mobile-first: padding lebih kecil */
    .block-container { padding: 1rem 1rem 2rem; max-width: 900px; }
    /* Tombol full-width di mobile */
    .stButton > button { width: 100%; border-radius: 8px; font-weight: 600; }
    .stButton > button[kind="primary"] { background: #1D9E75; border: none; }
    /* Input field lebih besar untuk jari */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        font-size: 16px !important; min-height: 44px;
    }
    /* Tabel responsif */
    .stDataFrame { font-size: 13px; }
    /* Tab styling */
    .stTabs [data-baseweb="tab"] { font-size: 14px; font-weight: 600; }
    /* Hide streamlit branding */
    #MainMenu, footer { visibility: hidden; }
    /* Alert box */
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ── SCHEDULER LAPORAN HARIAN ────────────────────────────────
def setup_scheduler():
    """Jalankan laporan harian jam 21.00 via APScheduler"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        import pytz

        def kirim_laporan():
            now = datetime.now()
            stats = db.hitung_keuangan_bulan(now.month, now.year)
            aktif = db.get_transaksi_aktif()
            stats["order_aktif"] = len(aktif)
            stats["selesai_hari_ini"] = sum(
                1 for t in aktif if t.get("status") == "Selesai"
            )
            tg.laporan_harian(stats)

            # Cek stok menipis
            menipis = db.get_bahan_hampir_habis()
            if menipis:
                tg.notif_stok_menipis(menipis)

        if "scheduler_started" not in st.session_state:
            scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Jakarta"))
            scheduler.add_job(kirim_laporan, "cron", hour=21, minute=0)
            scheduler.start()
            st.session_state.scheduler_started = True
    except Exception:
        pass  # Scheduler opsional, tidak menghentikan app


# ═══════════════════════════════════════════════════════════
# HALAMAN: DASHBOARD
# ═══════════════════════════════════════════════════════════
def halaman_dashboard(profil=None):
    nama_toko = profil.get("nama_toko", "ERP Toko") if profil else "ERP Toko"
    mobile_header(nama_toko, f"Dashboard · {datetime.now().strftime('%d %b %Y')}")

    now = datetime.now()
    stats = db.hitung_keuangan_bulan(now.month, now.year)
    transaksi_aktif = db.get_transaksi_aktif()
    bahan_menipis = db.get_bahan_hampir_habis()

    # ── ALERT STOK ──
    if bahan_menipis:
        nama_list = ", ".join(b["nama_bahan"] for b in bahan_menipis)
        st.warning(f"⚠️ Stok menipis: **{nama_list}** — segera restok!")

    # ── KPI CARDS ──
    col1, col2 = st.columns(2)
    with col1:
        metric_card("Pendapatan Bulan Ini",
                    fmt_rupiah(stats["total_sales"]), color="#1D9E75")
        metric_card("Order Aktif",
                    f"{len(transaksi_aktif)} sepatu", color="#3B82F6")
    with col2:
        laba = stats["laba_bersih"]
        metric_card("Laba Bersih",
                    fmt_rupiah(laba),
                    delta="Bulan ini",
                    color="#1D9E75" if laba >= 0 else "#EF4444")
        metric_card("Stok Menipis",
                    f"{len(bahan_menipis)} bahan", color="#F59E0B")

    st.markdown("---")

    # ── PIPELINE STATUS ──
    st.subheader("Order Sedang Diproses")
    status_list = ["Cuci", "Selesai"]
    cols = st.columns(2)
    for i, s in enumerate(status_list):
        cnt = sum(1 for t in transaksi_aktif if t["status"] == s)
        with cols[i]:
            warna = ["#3B82F6", "#10B981"][i]
            metric_card(s, str(cnt), color=warna)

    # ── TABEL ORDER AKTIF ──
    if transaksi_aktif:
        st.subheader("🔄 Order Sedang Diproses")
        rows = []
        for t in transaksi_aktif:
            tgl = db.parse_iso(t["created_at"])
            layanan = t.get("tabel_layanan", {})
            rows.append({
                "ID": f"#{t['id']:05d}",
                "Customer": t["customer_name"],
                "Layanan": layanan.get("nama_layanan", "-") if layanan else "-",
                "Status": t["status"],
                "Total": fmt_rupiah(t["total_bayar"]),
                "Bayar": "✅" if t["is_paid"] else "⏳",
                "Tgl Masuk": tgl.strftime("%d/%m %H:%M"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── GRAFIK MINI ──
    st.markdown("---")
    st.subheader("📊 Komposisi Biaya Bulan Ini")
    labels = ["Bahan Terpakai", "Fixed Cost", "Variable Cost", "Laba Bersih"]
    values = [
        max(stats["bahan_terpakai"], 0),
        max(stats["fixed_cost"], 0),
        max(stats["variable_cost"], 0),
        max(stats["laba_bersih"], 0),
    ]
    if sum(values) > 0:
        fig = px.pie(
            names=labels, values=values,
            color_discrete_sequence=["#F59E0B","#EF4444","#F97316","#10B981"],
            hole=0.5
        )
        fig.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=280,
            showlegend=True,
            legend=dict(orientation="h", y=-0.1)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Belum ada data transaksi bulan ini.")


# ═══════════════════════════════════════════════════════════
# HALAMAN: POS / ORDER BARU
# ═══════════════════════════════════════════════════════════
def halaman_pos(profil=None):
    mobile_header("Input Order Baru", "Form Point of Sales")

    layanan_list = db.get_all_layanan()
    if not layanan_list:
        st.error("Belum ada layanan. Tambahkan di menu Master Data.")
        return

    with st.form("form_order", clear_on_submit=True):
        st.markdown("##### 👤 Data Customer")
        nama = st.text_input("Nama Customer *", placeholder="Budi Santoso")
        wa   = st.text_input("No. WhatsApp", placeholder="08123456789")

        st.markdown("##### Layanan")
        layanan_options = {f"{l['nama_layanan']} — {fmt_rupiah(l['harga'])}": l for l in layanan_list}
        layanan_pilih = st.selectbox("Pilih Layanan *", options=list(layanan_options.keys()))
        layanan_obj = layanan_options[layanan_pilih]

        # Tampilkan BOM
        bom = db.get_bom_by_layanan(layanan_obj["id"])
        if bom:
            with st.expander("🧴 Bahan yang digunakan"):
                for b in bom:
                    bahan_info = b.get("tabel_bahan_baku", {})
                    st.write(f"• {bahan_info.get('nama_bahan','?')}: "
                             f"{b['jumlah_pemakaian']} {bahan_info.get('satuan','')}")

        st.markdown("##### Pembayaran")
        total = st.number_input("Total Bayar (Rp) *",
                                value=layanan_obj["harga"],
                                min_value=0, step=1000)
        is_paid = st.checkbox("Sudah bayar (lunas)")

        st.markdown("##### 📸 Foto Sepatu")
        foto = st.file_uploader("Upload foto (opsional) - Maks 1 MB", type=["jpg","jpeg","png"],
                                help="Foto kondisi sepatu sebelum dicuci (Maksimal 1 MB)")

        catatan = st.text_area("Catatan", placeholder="Catatan khusus pengerjaan...")

        st.markdown("---")
        st.markdown("📧 **Kirim Struk via Email (Opsional)**")
        email_cust = st.text_input("Email Customer", placeholder="customer@email.com")

        submitted = st.form_submit_button("✅ SIMPAN ORDER", type="primary", use_container_width=True)

    if submitted:
        if not nama:
            st.error("Nama customer wajib diisi!")
            return
        
        # --- VALIDASI UKURAN FOTO (1 MB) ---
        if foto and foto.size > 1 * 1024 * 1024:
            st.error("❌ Ukuran foto terlalu besar! Harap gunakan foto di bawah 1 MB.")
            return

        with st.spinner("Menyimpan order..."):
            foto_url = ""
            if foto:
                try:
                    foto_url = db.upload_foto_sepatu(foto.read(), foto.name)
                except Exception as e:
                    st.warning(f"Foto gagal diupload: {e}")

            trx = db.buat_transaksi(
                customer=nama.strip(),
                wa=wa.strip(),
                layanan_id=layanan_obj["id"],
                total=int(total),
                foto_url=foto_url,
                catatan=catatan,
                email=email_cust.strip()
            )

            if is_paid:
                db.update_bayar_transaksi(trx["id"], True)

            # Notifikasi Telegram
            tg.notif_order_baru(nama, layanan_obj["nama_layanan"], int(total), wa)
            
            # Kirim Struk via Email
            if email_cust.strip():
                tgl_str = db.parse_iso(trx["created_at"]).strftime("%d %B %Y, %H:%M")
                mail.kirim_struk(
                    email=email_cust.strip(),
                    trx_id=trx["id"],
                    customer=nama,
                    layanan=layanan_obj["nama_layanan"],
                    total=int(total),
                    tanggal_str=tgl_str,
                    catatan=catatan
                )

            # Cek stok menipis
            menipis = db.get_bahan_hampir_habis()
            if menipis:
                tg.notif_stok_menipis(menipis)

        st.success(f"✅ Order #{trx['id']:05d} berhasil disimpan!")
        st.markdown(generate_nota(trx, layanan_obj["nama_layanan"], shop_profile=profil))


# ═══════════════════════════════════════════════════════════
# HALAMAN: MANAJEMEN ORDER
# ═══════════════════════════════════════════════════════════
def halaman_order(profil=None):
    mobile_header("Manajemen Order", "Update status & tracking")

    status_options = ["Semua", "Cuci", "Selesai", "Sudah diambil"]
    col1, col2 = st.columns([2, 1])
    with col1:
        filter_status = st.selectbox("Filter Status", status_options)
    with col2:
        st.write("")
        st.write("")
        refresh = st.button("🔄 Refresh", use_container_width=True)

    transaksi = db.get_all_transaksi(limit=50, status_filter=filter_status)

    if not transaksi:
        st.info("Tidak ada order dengan filter ini.")
        return

    STATUS_NEXT = {
        "Cuci": "Selesai",
        "Selesai": "Sudah diambil"
    }

    for t in transaksi:
        layanan = t.get("tabel_layanan") or {}
        layanan_nama = layanan.get("nama_layanan", "-")
        tgl = db.parse_iso(t["created_at"])

        with st.container():
            st.markdown(f"""
            <div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin-bottom:10px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <strong>#{t['id']:05d} · {t['customer_name']}</strong>
                    {status_badge(t['status'])}
                </div>
                <div style="font-size:13px;color:#666;margin-top:6px">
                    {layanan_nama} · {fmt_rupiah(t['total_bayar'])} · {tgl.strftime('%d/%m %H:%M')}
                    {"&nbsp;✅ Lunas" if t['is_paid'] else "&nbsp;⏳ Belum bayar"}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if t.get("foto_url"):
                with st.expander("📸 Lihat foto"):
                    st.image(t["foto_url"], width=200)

            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                next_status = STATUS_NEXT.get(t["status"])
                if next_status:
                    if st.button(f"➡️ {next_status}", key=f"mv_{t['id']}"):
                        try:
                            db.update_status_transaksi(t["id"], next_status)
                            tg.notif_status_berubah(t["customer_name"], next_status, layanan_nama)
                            st.success(f"Status diubah ke {next_status}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal: {e}")
            with col2:
                if not t["is_paid"]:
                    if st.button("💰 Lunas", key=f"pay_{t['id']}"):
                        db.update_bayar_transaksi(t["id"], True)
                        st.success("✅ Ditandai lunas")
                        st.rerun()
            with col3:
                if st.button("🧾 Nota", key=f"nota_{t['id']}"):
                    st.markdown(generate_nota(t, layanan_nama, shop_profile=profil))
            with col4:
                # ── WHATSAPP BUTTON ──
                wa_no = t.get("whatsapp_no")
                if wa_no:
                    # Bersihkan karakter non-numeric jika ada
                    wa_clean = ''.join(filter(str.isdigit, wa_no))
                    if wa_clean.startswith("0"):
                        wa_clean = "62" + wa_clean[1:]
                    
                    msg = f"Halo {t['customer_name']}, sepatu Anda dengan order #{t['id']:05d} ({layanan_nama}) saat ini berstatus: *{t['status']}*."
                    wa_url = f"https://wa.me/{wa_clean}?text={msg.replace(' ', '%20')}"
                    st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="width:100%;height:38px;border-radius:8px;border:1px solid #25D366;background:white;color:#25D366;font-weight:600;cursor:pointer">💬 WA</button></a>''', unsafe_allow_html=True)
                else:
                    st.button("💬 WA", key=f"wa_none_{t['id']}", disabled=True)
                    email_dest = t.get("customer_email")
                    if not email_dest:
                        st.warning("⚠️ Email customer tidak terdata.")
                    else:
                        with st.spinner("Mengirim ulang email..."):
                            tgl_str = db.parse_iso(t["created_at"]).strftime("%d %B %Y, %H:%M")
                            mail.kirim_struk(
                                email=email_dest,
                                trx_id=t["id"],
                                customer=t["customer_name"],
                                layanan=layanan_nama,
                                total=t["total_bayar"],
                                tanggal_str=tgl_str,
                                catatan=t.get("catatan", "")
                            )
                            st.toast(f"✅ Struk dikirim ke {email_dest}")


# ═══════════════════════════════════════════════════════════
# HALAMAN: INVENTORY & BOM
# ═══════════════════════════════════════════════════════════
def halaman_inventory(profil=None):
    mobile_header("Inventory & BOM", "Stok bahan baku & resep layanan")

    tab1, tab2, tab3 = st.tabs(["Stok Bahan", "Kelola Bill Of Materials", "Tambah Bahan"])

    # ── TAB 1: Stok ──
    with tab1:
        bahan_list = db.get_all_bahan()
        if not bahan_list:
            st.info("Belum ada bahan baku.")
        else:
            rows = []
            for b in bahan_list:
                status_stok = "⚠️ MENIPIS" if b["stok_saat_ini"] <= b["reorder_level"] else "✅ Aman"
                rows.append({
                    "Nama Bahan": b["nama_bahan"],
                    "Stok": f"{b['stok_saat_ini']} {b['satuan']}",
                    "Reorder": f"{b['reorder_level']} {b['satuan']}",
                    "Harga/Satuan": fmt_rupiah(b["harga_per_satuan"]),
                    "Status": status_stok,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.subheader("Update Stok Manual")
            bahan_dict = {b["nama_bahan"]: b for b in bahan_list}
            pilih = st.selectbox("Pilih Bahan", list(bahan_dict.keys()), key="upd_bahan")
            bahan_sel = bahan_dict[pilih]
            stok_baru = st.number_input(
                f"Stok baru ({bahan_sel['satuan']})",
                value=float(bahan_sel["stok_saat_ini"]),
                min_value=0.0, step=1.0
            )
            if st.button("Update Stok", type="primary"):
                try:
                    db.update_stok_bahan(bahan_sel["id"], stok_baru)
                    st.success(f"✅ Stok {pilih} diperbarui menjadi {stok_baru}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # ── TAB 2: BOM ──
    with tab2:
        layanan_list = db.get_all_layanan()
        bahan_list = db.get_all_bahan()

        if not layanan_list or not bahan_list:
            st.warning("Tambahkan layanan dan bahan baku terlebih dahulu.")
        else:
            layanan_dict = {l["nama_layanan"]: l for l in layanan_list}
            pilih_layanan = st.selectbox("Pilih Layanan", list(layanan_dict.keys()), key="bom_lay")
            layanan_obj = layanan_dict[pilih_layanan]

            bom = db.get_bom_by_layanan(layanan_obj["id"])
            if bom:
                st.markdown("**Komposisi saat ini:**")
                for b in bom:
                    bi = b.get("tabel_bahan_baku", {})
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"🧴 {bi.get('nama_bahan','')} — {b['jumlah_pemakaian']} {bi.get('satuan','')}")
                    with col2:
                        if st.button("🗑️", key=f"delbom_{b['id']}"):
                            db.delete_bom(b["id"])
                            st.rerun()
            else:
                st.info("Layanan ini belum punya BOM.")

            st.markdown("**Tambah bahan ke BOM:**")
            bahan_dict = {b["nama_bahan"]: b for b in bahan_list}
            pilih_bahan = st.selectbox("Bahan", list(bahan_dict.keys()), key="bom_bahan")
            jumlah = st.number_input("Jumlah pemakaian per order", min_value=0.1, step=0.5)
            if st.button("➕ Tambah ke BOM", type="primary"):
                db.upsert_bom(layanan_obj["id"], bahan_dict[pilih_bahan]["id"], jumlah)
                st.success("✅ BOM diperbarui!")
                st.rerun()

    # ── TAB 3: Tambah Bahan ──
    with tab3:
        with st.form("form_bahan", clear_on_submit=True):
            nama_bahan = st.text_input("Nama Bahan *")
            col1, col2 = st.columns(2)
            with col1:
                satuan = st.selectbox("Satuan", ["ml", "gr", "pcs", "liter", "kg"])
                stok_awal = st.number_input("Stok Awal", min_value=0.0, step=1.0)
            with col2:
                harga_sat = st.number_input("Harga/Satuan (Rp)", min_value=0, step=100)
                reorder = st.number_input("Reorder Level", min_value=0.0, step=1.0)

            if st.form_submit_button("💾 Simpan Bahan", type="primary"):
                if nama_bahan:
                    db.upsert_bahan(nama_bahan, stok_awal, satuan, harga_sat, reorder)
                    st.success(f"✅ Bahan '{nama_bahan}' disimpan!")
                    st.rerun()
                else:
                    st.error("Nama bahan wajib diisi!")


# ═══════════════════════════════════════════════════════════
# HALAMAN: KEUANGAN
# ═══════════════════════════════════════════════════════════
def halaman_keuangan(profil=None):
    mobile_header("Modul Keuangan", "Laba bersih & pengeluaran")

    tab1, tab2 = st.tabs(["Laporan Laba Rugi", "Catat Pengeluaran"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            bulan = st.selectbox("Bulan", list(range(1, 13)),
                                 index=datetime.now().month - 1,
                                 format_func=lambda x: datetime(2024, x, 1).strftime("%B"))
        with col2:
            tahun = st.number_input("Tahun", value=datetime.now().year, min_value=2020)

        stats = db.hitung_keuangan_bulan(bulan, tahun)

        col1, col2 = st.columns(2)
        with col1:
            metric_card("💵 Total Sales", fmt_rupiah(stats["total_sales"]), color="#10B981")
            metric_card("🧴 Bahan Terpakai", fmt_rupiah(stats["bahan_terpakai"]), color="#F59E0B")
        with col2:
            metric_card("🏢 Fixed Cost", fmt_rupiah(stats["fixed_cost"]), color="#EF4444")
            metric_card("📦 Variable Cost", fmt_rupiah(stats["variable_cost"]), color="#F97316")

        laba = stats["laba_bersih"]
        warna = "#10B981" if laba >= 0 else "#EF4444"
        st.markdown(f"""
        <div style="background:{warna}20;border:2px solid {warna};border-radius:12px;
                    padding:20px;text-align:center;margin-top:16px">
            <div style="font-size:14px;color:{warna};font-weight:600">LABA BERSIH</div>
            <div style="font-size:32px;font-weight:800;color:{warna}">{fmt_rupiah(laba)}</div>
            <div style="font-size:12px;color:#666">Sales - Bahan - Fixed - Variable</div>
        </div>
        """, unsafe_allow_html=True)

        # Chart waterfall
        fig = go.Figure(go.Waterfall(
            name="Laba Rugi",
            orientation="v",
            measure=["relative","relative","relative","relative","total"],
            x=["Sales","Bahan","Fixed Cost","Variable Cost","Laba Bersih"],
            y=[stats["total_sales"], -stats["bahan_terpakai"],
               -stats["fixed_cost"], -stats["variable_cost"], 0],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "#10B981"}},
            decreasing={"marker": {"color": "#EF4444"}},
            totals={"marker": {"color": "#3B82F6"}},
        ))
        fig.update_layout(
            height=300, margin=dict(t=20, b=20, l=20, r=20),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabel pengeluaran
        pen_list = db.get_all_pengeluaran(bulan, tahun)
        if pen_list:
            st.subheader("📋 Rincian Pengeluaran")
            rows = [{
                "Tanggal": p["tanggal"],
                "Kategori": p["kategori"],
                "Nama": p["nama_biaya"],
                "Jumlah": fmt_rupiah(p["jumlah"]),
                "Ket": p.get("keterangan", ""),
            } for p in pen_list]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        with st.form("form_pengeluaran", clear_on_submit=True):
            kategori = st.radio("Kategori", ["Fixed Cost", "Variable Cost"], horizontal=True)
            nama_biaya = st.text_input("Nama Biaya *", placeholder="contoh: Sewa tempat")
            col1, col2 = st.columns(2)
            with col1:
                jumlah = st.number_input("Jumlah (Rp) *", min_value=0, step=1000)
            with col2:
                tgl = st.date_input("Tanggal", value=date.today())
            keterangan = st.text_input("Keterangan")

            if st.form_submit_button("💾 Catat Pengeluaran", type="primary"):
                if nama_biaya and jumlah > 0:
                    db.buat_pengeluaran(kategori, nama_biaya, jumlah, tgl, keterangan)
                    st.success(f"✅ Pengeluaran '{nama_biaya}' dicatat!")
                    st.rerun()
                else:
                    st.error("Nama biaya dan jumlah wajib diisi!")


# ═══════════════════════════════════════════════════════════
# HALAMAN: MASTER DATA
# ═══════════════════════════════════════════════════════════
def halaman_master(profil=None):
    mobile_header("Master Data", "Kelola layanan & pengaturan")

    tab1, tab2 = st.tabs(["Layanan", "Pengaturan Toko"])

    with tab1:
        layanan_list = db.get_all_layanan()
    if layanan_list:
        st.subheader("Daftar Layanan")
        rows = [{
            "ID": l["id"],
            "Layanan": l["nama_layanan"],
            "Harga": fmt_rupiah(l["harga"]),
            "Estimasi": f"{l['estimasi_hari']} hari",
        } for l in layanan_list]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("➕ Tambah / Edit Layanan")
    with st.form("form_layanan", clear_on_submit=True):
        nama_lay = st.text_input("Nama Layanan *")
        col1, col2 = st.columns(2)
        with col1:
            harga = st.number_input("Harga (Rp)", min_value=0, step=1000)
        with col2:
            estimasi = st.number_input("Estimasi Hari", min_value=1, value=2)

        if st.form_submit_button("💾 Simpan Layanan", type="primary"):
            if nama_lay:
                db.upsert_layanan(nama_lay, harga, estimasi)
                st.success(f"✅ Layanan '{nama_lay}' disimpan!")
                st.rerun()
            else:
                st.error("Nama layanan wajib diisi!")

    # ── TAB 2: PENGATURAN TOKO ──
    with tab2:
        st.subheader("Edit Profil Toko")
        st.caption("Identitas ini akan muncul di Header dan Nota Digital.")
        with st.form("form_profil"):
            new_nama = st.text_input("Nama Toko", value=profil.get("nama_toko", ""))
            new_wa   = st.text_input("No. WhatsApp Toko", value=profil.get("no_whatsapp", ""))
            new_mail = st.text_input("Email Toko", value=profil.get("email_toko", ""))
            new_addr = st.text_area("Alamat Toko", value=profil.get("alamat", ""))
            
            if st.form_submit_button("💾 Simpan Perubahan", type="primary"):
                db.update_profil_toko(new_nama, new_addr, new_wa, new_mail)
                st.success("✅ Profil toko berhasil diperbarui!")
                st.rerun()

    # ── LOG SISTEM & DIAGNOSTIK ──
    st.markdown("---")
    st.subheader("Log Sistem & Diagnostik")
    st.caption("Memantau status pengiriman email dan error teknis lainnya.")

    LOG_FILE = "system_logs.txt"
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                logs = f.readlines()
                # Ambil 50 baris terakhir
                recent_logs = "".join(logs[-50:])
                st.code(recent_logs or "Belum ada log tercatat.", language="text")
        except Exception as e:
            st.error(f"Gagal membaca log: {e}")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Bersihkan Log", use_container_width=True):
                with open(LOG_FILE, "w") as f:
                    f.write("")
                st.success("Log dibersihkan!")
                st.rerun()
    else:
        st.info("Belum ada file log sistem.")


# ═══════════════════════════════════════════════════════════
# HALAMAN: LOGIN
# ═══════════════════════════════════════════════════════════
def halaman_login(profil=None, cm=None):
    nama_toko = profil.get("nama_toko", "ERP Toko") if profil else "ERP Toko"
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="color: #1D9E75; margin-bottom: 0;">{nama_toko}</h1>
        <p style="color: #666; font-size: 1.1rem;">ERP System by haniffraihan</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["Login", "Daftar Owner"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="admin@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("MASUK KE DASHBOARD", type="primary")
                
                if submitted:
                    if not email or not password:
                        st.error("Email dan Password wajib diisi!")
                    else:
                        with st.spinner("Autentikasi..."):
                            try:
                                res = db.login_user(email, password)
                                st.session_state.authenticated = True
                                st.session_state.user = res.user
                                
                                # Simpan cookie untuk Remember Me (7 hari)
                                if cm:
                                    expiry = datetime.now() + timedelta(days=7)
                                    cm.set("sb_access_token", res.session.access_token, expires_at=expiry)
                                    cm.set("sb_refresh_token", res.session.refresh_token, expires_at=expiry)
                                
                                st.success("Login Berhasil!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal Login: {str(e)}")

        with tab2:
            st.info("ℹ️ Gunakan menu ini untuk membuat akun admin pertama Anda.")
            with st.form("signup_form"):
                new_email = st.text_input("Email Baru", placeholder="email@tokoanda.com")
                new_password = st.text_input("Password Baru", type="password")
                confirm = st.text_input("Konfirmasi Password", type="password")
                signup_btn = st.form_submit_button("BUAT AKUN")
                
                if signup_btn:
                    if new_password != confirm:
                        st.error("Konfirmasi password tidak cocok!")
                    elif len(new_password) < 6:
                        st.error("Password minimal 6 karakter!")
                    else:
                        try:
                            db.daftar_user(new_email, new_password)
                            st.success("✅ Pendaftaran berhasil! Silakan coba login.")
                        except Exception as e:
                            st.error(f"Gagal Daftar: {str(e)}")


# ═══════════════════════════════════════════════════════════
# ROUTING UTAMA
# ═══════════════════════════════════════════════════════════
def main():
    # Inisialisasi Profil Toko
    profil = db.get_profil_toko()

    # Inisialisasi Cookie Manager (harus dipanggil setiap run)
    cookie_manager = stx.CookieManager(key="cookie_manager_main")
    
    # Inisialisasi Auth State
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        
        # Coba pulihkan dari cookie
        access_token = cookie_manager.get("sb_access_token")
        refresh_token = cookie_manager.get("sb_refresh_token")
        
        if access_token and refresh_token:
            res = db.restore_session_user(access_token, refresh_token)
            if res and res.user:
                st.session_state.authenticated = True
                st.session_state.user = res.user

    # Sesi login aktif (Bypass debug dihapus untuk persiapan Demo)
    pass

    if not st.session_state.authenticated:
        halaman_login(profil, cookie_manager)
        return

    setup_scheduler()

    # Navigation bottom-bar style (mobile friendly)
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] > div { text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    menu = st.radio(
        "",
        ["Dashboard", "Order Baru", "Order", "Inventory", "Keuangan", "Master", "Keluar"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("---")

    if menu == "Dashboard":
        halaman_dashboard(profil)
    elif menu == "Order Baru":
        halaman_pos(profil)
    elif menu == "Order":
        halaman_order(profil)
    elif menu == "Inventory":
        halaman_inventory(profil)
    elif menu == "Keuangan":
        halaman_keuangan(profil)
    elif menu == "Master":
        halaman_master(profil)
    elif menu == "Keluar":
        db.logout_user()
        st.session_state.authenticated = False
        st.session_state.user = None
        # Hapus cookie
        cookie_manager.delete("sb_access_token")
        cookie_manager.delete("sb_refresh_token")
        st.rerun()


if __name__ == "__main__":
    main()
