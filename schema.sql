-- ============================================================
-- ERP CUCI SEPATU - SUPABASE SCHEMA
-- Jalankan di Supabase SQL Editor
-- ============================================================

-- 1. TABEL LAYANAN
CREATE TABLE IF NOT EXISTS tabel_layanan (
    id          BIGSERIAL PRIMARY KEY,
    nama_layanan VARCHAR(100) NOT NULL,
    harga        INTEGER NOT NULL CHECK (harga >= 0),
    estimasi_hari INTEGER NOT NULL DEFAULT 1,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 2. TABEL BAHAN BAKU
CREATE TABLE IF NOT EXISTS tabel_bahan_baku (
    id              BIGSERIAL PRIMARY KEY,
    nama_bahan      VARCHAR(100) NOT NULL,
    stok_saat_ini   DECIMAL(10,2) NOT NULL DEFAULT 0,
    satuan          VARCHAR(10) NOT NULL CHECK (satuan IN ('ml', 'gr', 'pcs', 'liter', 'kg')),
    harga_per_satuan INTEGER NOT NULL DEFAULT 0,
    reorder_level   DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. TABEL TRANSAKSI SALES
CREATE TABLE IF NOT EXISTS tabel_transaksi_sales (
    id            BIGSERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    whatsapp_no   VARCHAR(20),
    layanan_id    BIGINT REFERENCES tabel_layanan(id),
    status        VARCHAR(20) NOT NULL DEFAULT 'Cuci'
                  CHECK (status IN ('Cuci', 'Selesai', 'Sudah diambil')),
    total_bayar   INTEGER NOT NULL DEFAULT 0,
    is_paid       BOOLEAN DEFAULT FALSE,
    foto_url      TEXT,
    catatan       TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 4. TABEL BOM (Bill of Materials)
CREATE TABLE IF NOT EXISTS tabel_bom (
    id               BIGSERIAL PRIMARY KEY,
    layanan_id       BIGINT NOT NULL REFERENCES tabel_layanan(id) ON DELETE CASCADE,
    bahan_id         BIGINT NOT NULL REFERENCES tabel_bahan_baku(id) ON DELETE CASCADE,
    jumlah_pemakaian DECIMAL(10,2) NOT NULL CHECK (jumlah_pemakaian > 0),
    UNIQUE (layanan_id, bahan_id)
);

-- 5. TABEL PENGELUARAN
CREATE TABLE IF NOT EXISTS tabel_pengeluaran (
    id         BIGSERIAL PRIMARY KEY,
    kategori   VARCHAR(20) NOT NULL CHECK (kategori IN ('Fixed Cost', 'Variable Cost')),
    nama_biaya VARCHAR(100) NOT NULL,
    jumlah     INTEGER NOT NULL CHECK (jumlah >= 0),
    tanggal    DATE NOT NULL DEFAULT CURRENT_DATE,
    keterangan TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. TABEL PROFIL TOKO (SaaS Branding)
CREATE TABLE IF NOT EXISTS tabel_profil_toko (
    id          INTEGER PRIMARY KEY DEFAULT 1,
    nama_toko   VARCHAR(100) NOT NULL DEFAULT 'Nama Toko Anda',
    alamat      TEXT,
    no_whatsapp VARCHAR(20),
    email_toko  VARCHAR(100),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT profile_only_one CHECK (id = 1)
);

-- Masukkan data awal profil jika belum ada
INSERT INTO tabel_profil_toko (id, nama_toko)
VALUES (1, 'Hubb_Shoestreatment')
ON CONFLICT (id) DO NOTHING;

-- ── STORAGE BUCKET untuk foto sepatu ──
INSERT INTO storage.buckets (id, name, public)
VALUES ('foto-sepatu', 'foto-sepatu', TRUE)
ON CONFLICT DO NOTHING;

-- ── STORAGE POLICY: siapa saja bisa upload & lihat ──
DROP POLICY IF EXISTS "Public foto read" ON storage.objects;
CREATE POLICY "Public foto read" ON storage.objects
    FOR SELECT USING (bucket_id = 'foto-sepatu');

DROP POLICY IF EXISTS "Public foto upload" ON storage.objects;
CREATE POLICY "Public foto upload" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'foto-sepatu');

-- ── FUNCTION: potong stok otomatis saat status → Cuci ──
CREATE OR REPLACE FUNCTION potong_stok_bom()
RETURNS TRIGGER AS $$
DECLARE
    bom_row RECORD;
    stok_cukup BOOLEAN := TRUE;
    stok_kurang TEXT := '';
BEGIN
    -- Hanya jalankan jika status berubah MENJADI 'Cuci'
    IF NEW.status = 'Cuci' AND (OLD.status IS DISTINCT FROM 'Cuci') THEN
        -- Cek dulu apakah semua stok cukup
        FOR bom_row IN
            SELECT bb.nama_bahan, bb.stok_saat_ini, b.jumlah_pemakaian
            FROM tabel_bom b
            JOIN tabel_bahan_baku bb ON bb.id = b.bahan_id
            WHERE b.layanan_id = NEW.layanan_id
        LOOP
            IF bom_row.stok_saat_ini < bom_row.jumlah_pemakaian THEN
                stok_cukup := FALSE;
                stok_kurang := stok_kurang || bom_row.nama_bahan || ' ';
            END IF;
        END LOOP;

        IF NOT stok_cukup THEN
            RAISE EXCEPTION 'Stok tidak mencukupi untuk: %', stok_kurang;
        END IF;

        -- Potong stok semua bahan sesuai BOM
        FOR bom_row IN
            SELECT b.bahan_id, b.jumlah_pemakaian
            FROM tabel_bom b
            WHERE b.layanan_id = NEW.layanan_id
        LOOP
            UPDATE tabel_bahan_baku
            SET stok_saat_ini = stok_saat_ini - bom_row.jumlah_pemakaian
            WHERE id = bom_row.bahan_id;
        END LOOP;
    END IF;

    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Pasang trigger ke tabel transaksi
DROP TRIGGER IF EXISTS trigger_potong_stok ON tabel_transaksi_sales;
CREATE TRIGGER trigger_potong_stok
    BEFORE UPDATE ON tabel_transaksi_sales
    FOR EACH ROW EXECUTE FUNCTION potong_stok_bom();

-- ── DATA AWAL ──
INSERT INTO tabel_layanan (nama_layanan, harga, estimasi_hari) VALUES
    ('Cuci Biasa', 25000, 2),
    ('Cuci Premium', 45000, 3),
    ('Cuci + Repaint', 120000, 5),
    ('Deep Cleaning', 75000, 3),
    ('Unyellowing Sol', 50000, 2)
ON CONFLICT DO NOTHING;

INSERT INTO tabel_bahan_baku (nama_bahan, stok_saat_ini, satuan, harga_per_satuan, reorder_level) VALUES
    ('Sabun Sneaker Cleaner', 2000, 'ml', 50, 500),
    ('Cairan Repaint', 1500, 'ml', 120, 300),
    ('Kuas Pembersih', 50, 'pcs', 5000, 10),
    ('Sikat Halus', 30, 'pcs', 8000, 5),
    ('Cairan Unyellowing', 800, 'ml', 200, 200)
ON CONFLICT DO NOTHING;
