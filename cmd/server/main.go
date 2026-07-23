package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/ocr-persediaan/backend/internal/handler"
	"github.com/ocr-persediaan/backend/pkg/db"
)

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file, using environment variables")
	}

	pool, err := db.NewMySQLPool(os.Getenv("DB_URL"))
	if err != nil {
		log.Fatalf("DB connection failed: %v", err)
	}
	defer pool.Close()

	r := gin.Default()
	r.MaxMultipartMemory = 10 << 20

	// CORS
	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type,Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	r.GET("/health", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })

	v1 := r.Group("/api/v1")
	handler.RegisterDokumenRoutes(v1, pool)
	handler.RegisterTransaksiRoutes(v1, pool)
	handler.RegisterLaporanRoutes(v1, pool)
	handler.RegisterEvaluasiRoutes(v1, pool)
	handler.RegisterMLRoutes(v1)

	port := os.Getenv("APP_PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("Server running on :%s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
