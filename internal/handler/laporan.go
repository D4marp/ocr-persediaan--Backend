package handler

import (
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

func RegisterLaporanRoutes(r *gin.RouterGroup, pool *pgxpool.Pool) {
	r.GET("/laporan/mutasi", getMutasi(pool))
	r.GET("/laporan/ringkasan", getRingkasan(pool))
	r.GET("/laporan/kartu/:nama_produk", getKartuPersediaan(pool))
}

func getMutasi(pool *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		umkmID := c.Query("umkm_id")
		if umkmID == "" {
			umkmID = "default"
		}

		rows, err := pool.Query(c, `
			SELECT nama_produk, kode_barang, satuan,
				stok_awal, total_masuk, total_keluar, stok_akhir
			FROM v_mutasi_persediaan
			WHERE umkm_id=$1
			ORDER BY nama_produk
		`, umkmID)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		defer rows.Close()

		type MutasiRow struct {
			NamaProduk  string  `json:"nama_produk"`
			KodeBarang  string  `json:"kode_barang"`
			Satuan      string  `json:"satuan"`
			StokAwal    float64 `json:"stok_awal"`
			TotalMasuk  float64 `json:"total_masuk"`
			TotalKeluar float64 `json:"total_keluar"`
			StokAkhir   float64 `json:"stok_akhir"`
		}
		var result []MutasiRow
		for rows.Next() {
			var r MutasiRow
			rows.Scan(&r.NamaProduk, &r.KodeBarang, &r.Satuan,
				&r.StokAwal, &r.TotalMasuk, &r.TotalKeluar, &r.StokAkhir)
			result = append(result, r)
		}
		if result == nil {
			result = []MutasiRow{}
		}
		c.JSON(200, gin.H{"data": result, "total": len(result)})
	}
}

func getRingkasan(pool *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		umkmID := c.Query("umkm_id")
		if umkmID == "" {
			umkmID = "default"
		}

		var totalDokumen, totalTransaksi int
		var avgConf float64
		pool.QueryRow(c, `SELECT COUNT(*) FROM dokumen WHERE umkm_id=$1 AND status='done'`, umkmID).Scan(&totalDokumen)
		pool.QueryRow(c, `SELECT COUNT(*) FROM transaksi WHERE umkm_id=$1`, umkmID).Scan(&totalTransaksi)
		pool.QueryRow(c, `SELECT COALESCE(AVG(ocr_confidence),0) FROM dokumen WHERE umkm_id=$1 AND status='done'`, umkmID).Scan(&avgConf)

		var totalProduk int
		pool.QueryRow(c, `SELECT COUNT(DISTINCT nama_produk) FROM transaksi WHERE umkm_id=$1`, umkmID).Scan(&totalProduk)

		c.JSON(200, gin.H{
			"total_dokumen":      totalDokumen,
			"total_transaksi":    totalTransaksi,
			"total_produk":       totalProduk,
			"avg_ocr_confidence": avgConf,
		})
	}
}

func getKartuPersediaan(pool *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		namaProduk := c.Param("nama_produk")
		umkmID := c.Query("umkm_id")
		if umkmID == "" {
			umkmID = "default"
		}

		rows, err := pool.Query(c, `
			SELECT t.id, t.jenis, t.jumlah, t.satuan, t.harga_satuan, t.total,
				t.tanggal_transaksi, t.ml_confidence, t.is_verified, t.created_at
			FROM transaksi t
			WHERE t.nama_produk=$1 AND t.umkm_id=$2
			ORDER BY COALESCE(t.tanggal_transaksi, t.created_at::date) ASC
		`, namaProduk, umkmID)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		defer rows.Close()

		type KartuRow struct {
			ID               string   `json:"id"`
			Jenis            string   `json:"jenis"`
			Jumlah           *float64 `json:"jumlah"`
			Satuan           *string  `json:"satuan"`
			HargaSatuan      *float64 `json:"harga_satuan"`
			Total            *float64 `json:"total"`
			TanggalTransaksi *string  `json:"tanggal_transaksi"`
			MLConfidence     *float64 `json:"ml_confidence"`
			IsVerified       bool     `json:"is_verified"`
			CreatedAt        string   `json:"created_at"`
		}
		var kartu []KartuRow
		for rows.Next() {
			var r KartuRow
			rows.Scan(&r.ID, &r.Jenis, &r.Jumlah, &r.Satuan, &r.HargaSatuan, &r.Total,
				&r.TanggalTransaksi, &r.MLConfidence, &r.IsVerified, &r.CreatedAt)
			kartu = append(kartu, r)
		}
		if kartu == nil {
			kartu = []KartuRow{}
		}
		c.JSON(200, gin.H{"nama_produk": namaProduk, "data": kartu, "total": len(kartu)})
	}
}
