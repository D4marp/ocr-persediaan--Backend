package handler

import (
	"database/sql"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

func RegisterTransaksiRoutes(r *gin.RouterGroup, pool *sql.DB) {
	r.GET("/transaksi", listTransaksi(pool))
	r.POST("/transaksi", createTransaksi(pool))
	r.PUT("/transaksi/:id", updateTransaksi(pool))
	r.DELETE("/transaksi/:id", deleteTransaksi(pool))
}

func listTransaksi(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		umkmID := c.Query("umkm_id")
		jenis := c.Query("jenis")

		query := `SELECT id, dokumen_id, jenis, nama_produk, kode_barang,
			jumlah, satuan, harga_satuan, total, tanggal_transaksi,
			ml_confidence, is_verified, created_at
			FROM transaksi WHERE 1=1`
		args := []interface{}{}

		if umkmID != "" {
			query += ` AND umkm_id=?`
			args = append(args, umkmID)
		}
		if jenis != "" {
			query += ` AND jenis=?`
			args = append(args, jenis)
		}
		query += ` ORDER BY created_at DESC LIMIT 200`

		rows, err := pool.QueryContext(c, query, args...)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		defer rows.Close()

		type TxRow struct {
			ID               string     `json:"id"`
			DokumenID        *string    `json:"dokumen_id"`
			Jenis            string     `json:"jenis"`
			NamaProduk       string     `json:"nama_produk"`
			KodeBarang       *string    `json:"kode_barang"`
			Jumlah           *float64   `json:"jumlah"`
			Satuan           *string    `json:"satuan"`
			HargaSatuan      *float64   `json:"harga_satuan"`
			Total            *float64   `json:"total"`
			TanggalTransaksi *time.Time `json:"tanggal_transaksi"`
			MLConfidence     *float64   `json:"ml_confidence"`
			IsVerified       bool       `json:"is_verified"`
			CreatedAt        time.Time  `json:"created_at"`
		}
		var txs []TxRow
		for rows.Next() {
			var tx TxRow
			rows.Scan(&tx.ID, &tx.DokumenID, &tx.Jenis, &tx.NamaProduk, &tx.KodeBarang,
				&tx.Jumlah, &tx.Satuan, &tx.HargaSatuan, &tx.Total, &tx.TanggalTransaksi,
				&tx.MLConfidence, &tx.IsVerified, &tx.CreatedAt)
			txs = append(txs, tx)
		}
		if txs == nil {
			txs = []TxRow{}
		}
		c.JSON(200, gin.H{"data": txs, "total": len(txs)})
	}
}

func createTransaksi(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			Jenis       string  `json:"jenis" binding:"required"`
			NamaProduk  string  `json:"nama_produk" binding:"required"`
			KodeBarang  string  `json:"kode_barang"`
			Jumlah      float64 `json:"jumlah"`
			Satuan      string  `json:"satuan"`
			HargaSatuan float64 `json:"harga_satuan"`
			Total       float64 `json:"total"`
			Tanggal     string  `json:"tanggal"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}
		if req.Jenis != "barang_masuk" && req.Jenis != "barang_keluar" {
			c.JSON(400, gin.H{"error": "Jenis harus 'barang_masuk' atau 'barang_keluar'"})
			return
		}

		id := uuid.New().String()
		_, err := pool.ExecContext(c, `
			INSERT INTO transaksi (id, jenis, nama_produk, kode_barang, jumlah, satuan,
				harga_satuan, total, is_verified)
			VALUES (?,?,?,?,?,?,?,?,true)
		`, id, req.Jenis, req.NamaProduk, req.KodeBarang, req.Jumlah, req.Satuan,
			req.HargaSatuan, req.Total)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		c.JSON(201, gin.H{"id": id, "message": "Transaksi berhasil disimpan"})
	}
}

func updateTransaksi(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		var req struct {
			Jenis       string  `json:"jenis"`
			NamaProduk  string  `json:"nama_produk"`
			KodeBarang  string  `json:"kode_barang"`
			Jumlah      float64 `json:"jumlah"`
			Satuan      string  `json:"satuan"`
			HargaSatuan float64 `json:"harga_satuan"`
			Total       float64 `json:"total"`
			IsVerified  bool    `json:"is_verified"`
			Catatan     string  `json:"catatan"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}
		_, err := pool.ExecContext(c, `
			UPDATE transaksi
			SET jenis=?, nama_produk=?, kode_barang=?, jumlah=?, satuan=?,
				harga_satuan=?, total=?, is_verified=?, catatan=?
			WHERE id=?
		`, req.Jenis, req.NamaProduk, req.KodeBarang, req.Jumlah, req.Satuan,
			req.HargaSatuan, req.Total, req.IsVerified, req.Catatan, id)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		c.JSON(200, gin.H{"message": "Transaksi diperbarui"})
	}
}

func deleteTransaksi(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		pool.ExecContext(c, `DELETE FROM transaksi WHERE id=?`, id)
		c.JSON(200, gin.H{"message": "Transaksi dihapus"})
	}
}
