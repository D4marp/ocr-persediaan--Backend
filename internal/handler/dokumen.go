package handler

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"os"
	"path/filepath"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/ocr-persediaan/backend/pkg/processing"
)

type OCRResponse struct {
	Text             string  `json:"text"`
	Confidence       float64 `json:"confidence"`
	WordCount        int     `json:"word_count"`
	ProcessingTimeMs float64 `json:"processing_time_ms"`
}

type MLResponse struct {
	Jenis        string  `json:"jenis"`
	NamaProduk   string  `json:"nama_produk"`
	KodeBarang   string  `json:"kode_barang"`
	Jumlah       float64 `json:"jumlah"`
	Satuan       string  `json:"satuan"`
	HargaSatuan  float64 `json:"harga_satuan"`
	Total        float64 `json:"total"`
	Tanggal      string  `json:"tanggal"`
	MLConfidence float64 `json:"ml_confidence"`
	ModelUsed    string  `json:"model_used"`
}

func RegisterDokumenRoutes(r *gin.RouterGroup, pool *sql.DB) {
	r.POST("/dokumen/upload", uploadDokumen(pool))
	r.GET("/dokumen", listDokumen(pool))
	r.GET("/dokumen/:id", getDokumen(pool))
	r.DELETE("/dokumen/:id", deleteDokumen(pool))
}

func uploadDokumen(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		file, header, err := c.Request.FormFile("file")
		if err != nil {
			c.JSON(400, gin.H{"error": "File tidak ditemukan dalam request"})
			return
		}
		defer file.Close()

		ext := filepath.Ext(header.Filename)
		allowed := map[string]bool{".jpg": true, ".jpeg": true, ".png": true, ".webp": true}
		if !allowed[ext] {
			c.JSON(400, gin.H{"error": "Format tidak didukung. Gunakan JPG/PNG/WEBP"})
			return
		}

		fileBytes, err := io.ReadAll(file)
		if err != nil {
			c.JSON(500, gin.H{"error": "Gagal membaca file"})
			return
		}

		// Simpan file
		docID := uuid.New().String()
		uploadDir := os.Getenv("UPLOAD_DIR")
		if uploadDir == "" {
			uploadDir = "./uploads"
		}
		os.MkdirAll(uploadDir, 0755)
		filename := fmt.Sprintf("%s%s", docID, ext)
		filePath := filepath.Join(uploadDir, filename)

		if err := os.WriteFile(filePath, fileBytes, 0644); err != nil {
			c.JSON(500, gin.H{"error": "Gagal menyimpan file"})
			return
		}

		// Insert DB dengan status processing
		_, err = pool.ExecContext(c, `
			INSERT INTO dokumen (id, filename, file_path, status)
			VALUES (?, ?, ?, 'processing')
		`, docID, header.Filename, filePath)
		if err != nil {
			c.JSON(500, gin.H{"error": "Gagal menyimpan ke database"})
			return
		}

		start := time.Now()

		// Panggil OCR Service
		ocrResult, err := callOCRService(fileBytes, filename)
		if err != nil {
			pool.ExecContext(c, `UPDATE dokumen SET status='error' WHERE id=?`, docID)
			c.JSON(502, gin.H{"error": fmt.Sprintf("OCR service error: %v", err)})
			return
		}

		// Panggil ML Service
		mlResult, mlErr := callMLService(ocrResult.Text, docID)
		if mlErr != nil {
			mlResult = &MLResponse{ModelUsed: "unavailable"}
		}

		totalTime := time.Since(start).Milliseconds()

		// Update dokumen
		pool.ExecContext(c, `
			UPDATE dokumen
			SET status='done', ocr_text=?, ocr_confidence=?, processing_time_ms=?, updated_at=NOW()
			WHERE id=?
		`, ocrResult.Text, ocrResult.Confidence, totalTime, docID)

		// Simpan transaksi dari hasil ML
		var txID *string
		if mlResult.Jenis != "" && mlResult.ModelUsed != "unavailable" {
			id := uuid.New().String()
			txID = &id
			namaProduk := mlResult.NamaProduk
			if namaProduk == "" {
				namaProduk = "Produk Tidak Teridentifikasi"
			}
			pool.ExecContext(c, `
				INSERT INTO transaksi
					(id, dokumen_id, jenis, nama_produk, kode_barang, jumlah, satuan,
					 harga_satuan, total, ml_confidence, model_used)
				VALUES (?,?,?,?,?,?,?,?,?,?,?)
			`, id, docID, mlResult.Jenis, namaProduk, mlResult.KodeBarang,
				mlResult.Jumlah, mlResult.Satuan, mlResult.HargaSatuan,
				mlResult.Total, mlResult.MLConfidence, mlResult.ModelUsed)
		}

		c.JSON(200, gin.H{
			"dokumen_id":       docID,
			"transaksi_id":     txID,
			"ocr":              ocrResult,
			"transaksi":        mlResult,
			"processing_ms":    totalTime,
		})
	}
}

func listDokumen(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		umkmID := c.Query("umkm_id")
		query := `SELECT id, filename, status, ocr_confidence, processing_time_ms, created_at
			FROM dokumen`
		args := []interface{}{}
		if umkmID != "" {
			query += " WHERE umkm_id=?"
			args = append(args, umkmID)
		}
		query += " ORDER BY created_at DESC LIMIT 100"

		rows, err := pool.QueryContext(c, query, args...)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		defer rows.Close()

		type Row struct {
			ID               string    `json:"id"`
			Filename         string    `json:"filename"`
			Status           string    `json:"status"`
			OCRConfidence    *float64  `json:"ocr_confidence"`
			ProcessingTimeMs *float64  `json:"processing_time_ms"`
			CreatedAt        time.Time `json:"created_at"`
		}
		var docs []Row
		for rows.Next() {
			var d Row
			rows.Scan(&d.ID, &d.Filename, &d.Status, &d.OCRConfidence, &d.ProcessingTimeMs, &d.CreatedAt)
			docs = append(docs, d)
		}
		if docs == nil {
			docs = []Row{}
		}
		c.JSON(200, gin.H{"data": docs, "total": len(docs)})
	}
}

func getDokumen(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")

		var d struct {
			ID               string   `json:"id"`
			Filename         string   `json:"filename"`
			Status           string   `json:"status"`
			OCRText          *string  `json:"ocr_text"`
			OCRConfidence    *float64 `json:"ocr_confidence"`
			ProcessingTimeMs *float64 `json:"processing_time_ms"`
		}
		err := pool.QueryRowContext(c, `
			SELECT id, filename, status, ocr_text, ocr_confidence, processing_time_ms
			FROM dokumen WHERE id=?
		`, id).Scan(&d.ID, &d.Filename, &d.Status, &d.OCRText, &d.OCRConfidence, &d.ProcessingTimeMs)
		if err != nil {
			c.JSON(404, gin.H{"error": "Dokumen tidak ditemukan"})
			return
		}

		// Ambil transaksi terkait
		rows, _ := pool.QueryContext(c, `
			SELECT id, jenis, nama_produk, jumlah, satuan, total, ml_confidence, is_verified
			FROM transaksi WHERE dokumen_id=?
		`, id)
		defer rows.Close()

		var txs []map[string]interface{}
		for rows.Next() {
			var tx struct {
				ID           string   `json:"id"`
				Jenis        string   `json:"jenis"`
				NamaProduk   string   `json:"nama_produk"`
				Jumlah       *float64 `json:"jumlah"`
				Satuan       *string  `json:"satuan"`
				Total        *float64 `json:"total"`
				MLConfidence *float64 `json:"ml_confidence"`
				IsVerified   bool     `json:"is_verified"`
			}
			rows.Scan(&tx.ID, &tx.Jenis, &tx.NamaProduk, &tx.Jumlah,
				&tx.Satuan, &tx.Total, &tx.MLConfidence, &tx.IsVerified)
			txs = append(txs, map[string]interface{}{
				"id": tx.ID, "jenis": tx.Jenis, "nama_produk": tx.NamaProduk,
				"jumlah": tx.Jumlah, "satuan": tx.Satuan, "total": tx.Total,
				"ml_confidence": tx.MLConfidence, "is_verified": tx.IsVerified,
			})
		}

		c.JSON(200, gin.H{"dokumen": d, "transaksi": txs})
	}
}

func deleteDokumen(pool *sql.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		var filePath string
		pool.QueryRowContext(c, `SELECT file_path FROM dokumen WHERE id=?`, id).Scan(&filePath)
		pool.ExecContext(c, `DELETE FROM dokumen WHERE id=?`, id)
		if filePath != "" {
			os.Remove(filePath)
		}
		c.JSON(200, gin.H{"message": "Dokumen dihapus"})
	}
}

func callOCRService(fileBytes []byte, filename string) (*OCRResponse, error) {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	// CreateFormFile forces Content-Type: application/octet-stream, which the
	// worker's ALLOWED_TYPES check rejects. Build the part header manually so
	// the real image MIME type is preserved.
	mimeType := mime.TypeByExtension(filepath.Ext(filename))
	if mimeType == "" {
		mimeType = "application/octet-stream"
	}
	partHeader := textproto.MIMEHeader{}
	partHeader.Set("Content-Disposition", fmt.Sprintf(`form-data; name="file"; filename="%s"`, filename))
	partHeader.Set("Content-Type", mimeType)
	part, err := writer.CreatePart(partHeader)
	if err != nil {
		return nil, err
	}
	part.Write(fileBytes)
	writer.Close()

	ocrURL := processing.ServiceURL() + "/extract"
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(ocrURL, writer.FormDataContentType(), &buf)
	if err != nil {
		return nil, fmt.Errorf("OCR service tidak dapat dihubungi: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OCR service error %d: %s", resp.StatusCode, string(body))
	}

	var result OCRResponse
	json.NewDecoder(resp.Body).Decode(&result)
	return &result, nil
}

func callMLService(text, docID string) (*MLResponse, error) {
	mlURL := processing.ServiceURL() + "/classify"
	body, _ := json.Marshal(map[string]string{"text": text, "dokumen_id": docID})

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Post(mlURL, "application/json", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("ML service tidak dapat dihubungi: %w", err)
	}
	defer resp.Body.Close()

	var result MLResponse
	json.NewDecoder(resp.Body).Decode(&result)
	return &result, nil
}
