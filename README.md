# OCR Persediaan UMKM — Backend

Go (Gin) API server + Python worker (OCR/ML) untuk sistem FA-OCR. Database: MySQL 8.0.

## Menjalankan dengan Docker Compose (full stack)

`docker-compose.yml` di repo ini menjalankan 3 container: `mysql`, `backend` (repo ini), dan `frontend`
(dibangun dari repo [ocr-persediaan--Website](https://github.com/D4marp/ocr-persediaan--Website)).
Karena `frontend` dibangun dari path relatif `../frontend`, repo Website **harus** di-clone sebagai
folder saudara (sibling) bernama persis `frontend`, sejajar dengan repo ini:

```
some-folder/
├── ocr-persediaan--Backend/   <- repo ini (docker-compose.yml ada di sini)
└── frontend/                  <- clone repo Website ke SINI, nama foldernya harus "frontend"
```

```bash
git clone https://github.com/D4marp/ocr-persediaan--Backend.git
git clone https://github.com/D4marp/ocr-persediaan--Website.git ocr-persediaan--Backend/../frontend

cd ocr-persediaan--Backend
cp .env.example .env   # sesuaikan kredensial/port bila perlu
docker compose up -d --build
```

| Service | URL default |
|---|---|
| Backend API | http://localhost:8080 |
| Frontend | http://localhost:3000 |
| MySQL | localhost:3307 |

## Mengganti port (VPS/PaaS yang portnya sudah dipakai)

Isi di `.env` (lihat `.env.example`):

```
BACKEND_PORT=8081
FRONTEND_PORT=3001
MYSQL_HOST_PORT=3308
PUBLIC_API_URL=http://localhost:8081/api/v1
```

`PUBLIC_API_URL` penting: Next.js membakukan URL ini ke dalam bundle JavaScript **saat build**,
jadi harus diisi port publik yang benar (bukan hanya port internal) sebelum `docker compose up --build`.

## Development lokal (tanpa Docker penuh)

```bash
docker compose up -d mysql   # hanya database
go run ./cmd/server          # backend native, baca .env
```

## Skema Database

`pkg/db/schema.sql` dijalankan otomatis oleh container MySQL saat pertama kali dibuat
(`docker-entrypoint-initdb.d`). Tabel: `dokumen`, `transaksi`, `stok_produk`, `sus_response`,
plus view `v_mutasi_persediaan` untuk laporan mutasi.
