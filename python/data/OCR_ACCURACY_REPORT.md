# Laporan Evaluasi Akurasi OCR — Nota UMKM

**Tanggal evaluasi:** 2026-07-16
**Engine:** Tesseract 5.5.2 (`--oem 3`, kandidat PSM 3/4/6/11 dipilih otomatis per gambar berdasar skor confidence — lihat `ocr_engine.py`)
**Bahasa:** `ind+eng`

## 1. Dataset

Dataset dibangun dari dua rekap transaksi nyata milik UMKM (bukan data sintetis):

| Sumber | Isi | Nota unik | Baris item |
|---|---|---|---|
| `Nota pembelian.xlsx` | Pembelian bahan/kemasan | 16 | 24 |
| `Nota produksi.xlsx` | Pembelian bahan baku produksi | 31 | 70 |
| **Gabungan (unik)** | | **47** | **94** |

Setiap baris di kedua spreadsheet ditranskrip manual oleh pemilik usaha dari foto nota asli (struk kasir, faktur dot-matrix, dan nota tulisan tangan) yang disimpan di Google Drive/Gmail pribadi. 41 dari foto tsb berhasil diunduh (via sesi Chrome yang sudah login) dan dipakai sebagai **input uji OCR**; nilai pada spreadsheet menjadi **ground truth**.

Pencocokan foto → baris ground truth dilakukan **secara visual (manual)**, bukan lewat OCR itu sendiri, untuk menghindari bias sirkular pada evaluasi. 40 dari 41 foto berhasil dicocokkan; 1 foto (`link10`, nota tulisan tangan "Telor" tanpa nama toko) tidak punya padanan di kedua spreadsheet dan dikeluarkan dari perhitungan.

## 2. Metodologi Pengukuran

Karena ground truth hanya berisi field terstruktur (No. Nota, Toko/Supplier, Nama Barang, Qty, Harga, Total) — bukan transkrip lengkap nota (kop surat, alamat, dst) — akurasi dihitung per-field, gaya evaluasi umum untuk dataset nota/faktur (mis. SROIE, CORD):

1. **Field Detection Rate** — apakah nilai suatu field (dinormalisasi: huruf besar, tanpa tanda baca) berhasil ditemukan di teks hasil OCR, memakai pencocokan token + fuzzy match (`difflib`, ambang 0.8) per kata kunci pada field tsb. Field yang diuji per nota: No. Nota/ID, Toko/Supplier, Nama Barang tiap item, dan Total Harga tiap item (dicocokkan sebagai deret digit rupiah).
2. **Field-level Character Accuracy (1-CER)** — untuk field yang polanya ditemukan, dihitung jarak Levenshtein karakter-demi-karakter antara nilai ground truth dan potongan teks OCR di lokasi kemunculan terbaiknya (bukan CER global atas seluruh dokumen, karena itu akan bias oleh kop surat/boilerplate yang tak tercatat di ground truth).

Preprocessing yang dipakai: grayscale → upscale bila <1200px → autocontrast (PIL). Pipeline produksi proyek ini (`preprocessor.py`) memakai OpenCV (deskew + adaptive threshold) tapi library OpenCV pada environment evaluasi ini korup (linking error Homebrew/protobuf, di luar kendali proyek), sehingga hasil di bawah ini kemungkinan **sedikit lebih rendah** dari performa pipeline produksi yang sebenarnya.

## 3. Hasil

### Akurasi keseluruhan (40 nota, 91 baris item)

| Metrik | Nilai |
|---|---|
| Field Detection Rate (rata-rata) | **46.7%** |
| Field-level Character Accuracy | **53.4%** |

### Breakdown per jenis format nota

| Jenis nota | n | Field Detection | Character Accuracy |
|---|---|---|---|
| Cetak standar (kasir/faktur laser: Bahankoe, Depo Lestari, Indomaret, Titi Disk Stationery, dll) | 16 | **83.9%** | **82.0%** |
| Tulisan tangan (Toko Berkah Mandiri, Toko Sembako, UMRRA) | 6 | 31.9% | 43.6% |
| Dot-matrix POS (Yellow Shop) | 18 | 18.5% | 31.3% |

**Temuan utama:** akurasi Tesseract sangat bergantung pada jenis font nota, bukan sekadar "OCR akurat X%" secara umum:
- Pada nota **cetak standar** (font umum, kontras tinggi), Tesseract mencapai **~84% field detection / ~82% character accuracy** — sebanding dengan literatur OCR nota berbahasa Indonesia yang memakai preprocessing dasar.
- Pada nota **dot-matrix** (mis. toko "Yellow Shop", printer kasir titik/dot-matrix), akurasi anjlok ke **~18%** meski gambar tajam dan terbaca jelas oleh mata manusia — dikonfirmasi lewat pengujian tambahan (beberapa kombinasi threshold, PSM, OEM legacy/LSTM) yang semuanya gagal, menunjukkan ini keterbatasan riil Tesseract pada pola font titik, bukan masalah preprocessing.
- Pada nota **tulisan tangan**, akurasi ~32% — sesuai ekspektasi karena Tesseract memang tidak dirancang untuk teks tulisan tangan.

### Catatan kualitas data

- 1 dari 41 foto tidak berpadanan ground truth (dikeluarkan dari skor, bukan dihitung sebagai 0%).
- 1 nota ("Nota Sembako", Toko Sembako) memiliki indikasi transkripsi manual yang bergeser satu baris pada spreadsheet sumber (tanggal tertulis 11/04 vs tercatat 01/04; nilai per-item tidak berjumlah sama dengan total di foto) — diikutkan apa adanya dalam skor karena ambiguitas kecil, dicatat sebagai batasan data.

## 4. Implikasi untuk Paper

Angka yang relevan disebutkan sesuai kebutuhan narasi:
- **"Akurasi OCR keseluruhan: 46.7% (field detection) / 53.4% (character accuracy) pada 40 nota UMKM nyata dari 3 jenis format berbeda."**
- **"Pada subset nota bercetak standar, akurasi mencapai 83.9%/82.0%, namun turun signifikan pada nota dot-matrix (18.5%/31.3%) dan tulisan tangan (31.9%/43.6%) — menunjukkan kebutuhan preprocessing khusus per jenis nota untuk deployment UMKM riil."**

File detail per-nota (skor tiap field): `data/accuracy_report.json`.
File teks OCR mentah: `data/ocr_results.json`.
Ground truth terstruktur: `data/nota_ground_truth.json`.
