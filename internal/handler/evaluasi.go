package handler

import (
	"encoding/json"
	"io"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/ocr-persediaan/backend/pkg/processing"
)

func RegisterEvaluasiRoutes(r *gin.RouterGroup, pool *pgxpool.Pool) {
	r.GET("/evaluasi/metrik", getMetrik(pool))
	r.POST("/evaluasi/sus", submitSUS(pool))
	r.GET("/evaluasi/sus/hasil", hasilSUS(pool))
}

func getMetrik(pool *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Ambil metrik dari ML service
		mlURL := processing.ServiceURL() + "/metrics"
		client := &http.Client{Timeout: 5 * time.Second}
		resp, err := client.Get(mlURL)

		var mlMetrics map[string]interface{}
		if err == nil && resp.StatusCode == 200 {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			json.Unmarshal(body, &mlMetrics)
		} else {
			mlMetrics = map[string]interface{}{"model_version": "unavailable"}
		}

		// Statistik dari DB
		var totalDokumen, totalDone, totalError int
		pool.QueryRow(c, `SELECT COUNT(*) FROM dokumen`).Scan(&totalDokumen)
		pool.QueryRow(c, `SELECT COUNT(*) FROM dokumen WHERE status='done'`).Scan(&totalDone)
		pool.QueryRow(c, `SELECT COUNT(*) FROM dokumen WHERE status='error'`).Scan(&totalError)

		var avgOCRConf, avgProcessingMs float64
		pool.QueryRow(c, `SELECT COALESCE(AVG(ocr_confidence),0) FROM dokumen WHERE status='done'`).Scan(&avgOCRConf)
		pool.QueryRow(c, `SELECT COALESCE(AVG(processing_time_ms),0) FROM dokumen WHERE status='done'`).Scan(&avgProcessingMs)

		var totalTransaksi, terverifikasi int
		pool.QueryRow(c, `SELECT COUNT(*) FROM transaksi`).Scan(&totalTransaksi)
		pool.QueryRow(c, `SELECT COUNT(*) FROM transaksi WHERE is_verified=true`).Scan(&terverifikasi)

		c.JSON(200, gin.H{
			"ocr": gin.H{
				"total_dokumen":     totalDokumen,
				"total_processed":   totalDone,
				"total_error":       totalError,
				"avg_confidence":    round2(avgOCRConf),
				"avg_processing_ms": round2(avgProcessingMs),
			},
			"ml":  mlMetrics,
			"transaksi": gin.H{
				"total":       totalTransaksi,
				"terverifikasi": terverifikasi,
			},
		})
	}
}

type SUSRequest struct {
	RespondenID string `json:"responden_id"`
	UMKMId      string `json:"umkm_id"`
	Q1          int    `json:"q1"`
	Q2          int    `json:"q2"`
	Q3          int    `json:"q3"`
	Q4          int    `json:"q4"`
	Q5          int    `json:"q5"`
	Q6          int    `json:"q6"`
	Q7          int    `json:"q7"`
	Q8          int    `json:"q8"`
	Q9          int    `json:"q9"`
	Q10         int    `json:"q10"`
}

func hitungSUS(r SUSRequest) float64 {
	odd := []int{r.Q1, r.Q3, r.Q5, r.Q7, r.Q9}
	even := []int{r.Q2, r.Q4, r.Q6, r.Q8, r.Q10}
	total := 0
	for _, v := range odd {
		total += v - 1
	}
	for _, v := range even {
		total += 5 - v
	}
	return float64(total) * 2.5
}

func kategoriSUS(s float64) string {
	switch {
	case s >= 90:
		return "Excellent"
	case s >= 80:
		return "Good"
	case s >= 70:
		return "OK"
	case s >= 50:
		return "Poor"
	default:
		return "Awful"
	}
}

func submitSUS(pool *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req SUSRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		// Validasi semua jawaban 1-5
		answers := []int{req.Q1, req.Q2, req.Q3, req.Q4, req.Q5,
			req.Q6, req.Q7, req.Q8, req.Q9, req.Q10}
		for _, a := range answers {
			if a < 1 || a > 5 {
				c.JSON(400, gin.H{"error": "Semua jawaban harus antara 1-5"})
				return
			}
		}

		if req.RespondenID == "" {
			req.RespondenID = uuid.New().String()
		}
		if req.UMKMId == "" {
			req.UMKMId = "default"
		}

		skor := hitungSUS(req)
		kat := kategoriSUS(skor)

		_, err := pool.Exec(c, `
			INSERT INTO sus_response
				(id, responden_id, umkm_id, q1,q2,q3,q4,q5,q6,q7,q8,q9,q10, skor_sus, kategori)
			VALUES (gen_random_uuid(),$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
		`, req.RespondenID, req.UMKMId,
			req.Q1, req.Q2, req.Q3, req.Q4, req.Q5,
			req.Q6, req.Q7, req.Q8, req.Q9, req.Q10,
			skor, kat)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		c.JSON(200, gin.H{
			"responden_id": req.RespondenID,
			"skor_sus":     skor,
			"kategori":     kat,
			"message":      "Terima kasih! Penilaian Anda telah disimpan.",
		})
	}
}

func hasilSUS(pool *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		var totalResponden int
		var avgSkor, minSkor, maxSkor float64
		pool.QueryRow(c, `
			SELECT COUNT(*), COALESCE(AVG(skor_sus),0),
				COALESCE(MIN(skor_sus),0), COALESCE(MAX(skor_sus),0)
			FROM sus_response
		`).Scan(&totalResponden, &avgSkor, &minSkor, &maxSkor)

		// Distribusi per kategori
		rows, _ := pool.Query(c, `
			SELECT kategori, COUNT(*) FROM sus_response GROUP BY kategori ORDER BY COUNT(*) DESC
		`)
		defer rows.Close()

		distribusi := map[string]int{}
		for rows.Next() {
			var kat string
			var cnt int
			rows.Scan(&kat, &cnt)
			distribusi[kat] = cnt
		}

		c.JSON(200, gin.H{
			"total_responden": totalResponden,
			"rata_rata":       round2(avgSkor),
			"min":             round2(minSkor),
			"max":             round2(maxSkor),
			"kategori":        kategoriSUS(avgSkor),
			"distribusi":      distribusi,
		})
	}
}

func round2(f float64) float64 {
	return float64(int(f*100+0.5)) / 100
}
