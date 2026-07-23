-- Schema OCR Persediaan UMKM
-- Jalankan otomatis via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Dokumen transaksi yang diupload
CREATE TABLE IF NOT EXISTS dokumen (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  umkm_id         TEXT NOT NULL DEFAULT 'default',
  filename        TEXT NOT NULL,
  file_path       TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','processing','done','error')),
  ocr_text        TEXT,
  ocr_confidence  FLOAT,
  processing_time_ms FLOAT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Transaksi hasil klasifikasi ML
CREATE TABLE IF NOT EXISTS transaksi (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dokumen_id        UUID REFERENCES dokumen(id) ON DELETE CASCADE,
  umkm_id           TEXT NOT NULL DEFAULT 'default',
  jenis             TEXT NOT NULL CHECK (jenis IN ('barang_masuk','barang_keluar')),
  nama_produk       TEXT NOT NULL,
  kode_barang       TEXT,
  jumlah            DECIMAL(12,2),
  satuan            TEXT,
  harga_satuan      DECIMAL(15,2),
  total             DECIMAL(15,2),
  tanggal_transaksi DATE,
  ml_confidence     FLOAT,
  model_used        TEXT,
  is_verified       BOOLEAN DEFAULT FALSE,
  catatan           TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Stok produk (dihitung dari transaksi)
CREATE TABLE IF NOT EXISTS stok_produk (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  umkm_id       TEXT NOT NULL DEFAULT 'default',
  kode_barang   TEXT,
  nama_produk   TEXT NOT NULL,
  satuan        TEXT,
  stok_awal     DECIMAL(12,2) DEFAULT 0,
  harga_pokok   DECIMAL(15,2),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(umkm_id, nama_produk)
);

-- Kuesioner SUS
CREATE TABLE IF NOT EXISTS sus_response (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  responden_id  TEXT NOT NULL,
  umkm_id       TEXT DEFAULT 'default',
  q1 SMALLINT NOT NULL CHECK (q1 BETWEEN 1 AND 5),
  q2 SMALLINT NOT NULL CHECK (q2 BETWEEN 1 AND 5),
  q3 SMALLINT NOT NULL CHECK (q3 BETWEEN 1 AND 5),
  q4 SMALLINT NOT NULL CHECK (q4 BETWEEN 1 AND 5),
  q5 SMALLINT NOT NULL CHECK (q5 BETWEEN 1 AND 5),
  q6 SMALLINT NOT NULL CHECK (q6 BETWEEN 1 AND 5),
  q7 SMALLINT NOT NULL CHECK (q7 BETWEEN 1 AND 5),
  q8 SMALLINT NOT NULL CHECK (q8 BETWEEN 1 AND 5),
  q9 SMALLINT NOT NULL CHECK (q9 BETWEEN 1 AND 5),
  q10 SMALLINT NOT NULL CHECK (q10 BETWEEN 1 AND 5),
  skor_sus      FLOAT NOT NULL,
  kategori      TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- View: laporan mutasi persediaan
CREATE OR REPLACE VIEW v_mutasi_persediaan AS
SELECT
  t.umkm_id,
  t.nama_produk,
  COALESCE(t.kode_barang, '') AS kode_barang,
  COALESCE(sp.satuan, t.satuan, '') AS satuan,
  COALESCE(sp.stok_awal, 0) AS stok_awal,
  COALESCE(SUM(CASE WHEN t.jenis='barang_masuk'  THEN t.jumlah ELSE 0 END), 0) AS total_masuk,
  COALESCE(SUM(CASE WHEN t.jenis='barang_keluar' THEN t.jumlah ELSE 0 END), 0) AS total_keluar,
  COALESCE(sp.stok_awal, 0)
    + COALESCE(SUM(CASE WHEN t.jenis='barang_masuk'  THEN t.jumlah ELSE 0 END), 0)
    - COALESCE(SUM(CASE WHEN t.jenis='barang_keluar' THEN t.jumlah ELSE 0 END), 0) AS stok_akhir
FROM transaksi t
LEFT JOIN stok_produk sp
  ON sp.nama_produk = t.nama_produk AND sp.umkm_id = t.umkm_id
GROUP BY t.umkm_id, t.nama_produk, t.kode_barang, sp.satuan, t.satuan, sp.stok_awal;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_dokumen_status    ON dokumen(status);
CREATE INDEX IF NOT EXISTS idx_dokumen_umkm      ON dokumen(umkm_id);
CREATE INDEX IF NOT EXISTS idx_transaksi_umkm    ON transaksi(umkm_id);
CREATE INDEX IF NOT EXISTS idx_transaksi_produk  ON transaksi(nama_produk);
CREATE INDEX IF NOT EXISTS idx_sus_responden     ON sus_response(responden_id);
