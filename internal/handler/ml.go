package handler

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/ocr-persediaan/backend/pkg/processing"
)

func RegisterMLRoutes(r *gin.RouterGroup) {
	r.GET("/ml/dataset", getMLDataset())
	r.GET("/ml/models", getMLModels())
	r.POST("/ml/train", trainML())
	r.POST("/ml/seed", seedML())
}

func getMLModels() gin.HandlerFunc {
	return func(c *gin.Context) {
		mlURL := processing.ServiceURL() + "/models"
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Get(mlURL)
		if err != nil {
			c.JSON(502, gin.H{"error": "ML service tidak dapat dihubungi"})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		var result map[string]interface{}
		json.Unmarshal(body, &result)
		c.JSON(resp.StatusCode, result)
	}
}

func getMLDataset() gin.HandlerFunc {
	return func(c *gin.Context) {
		mlURL := processing.ServiceURL() + "/dataset"
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Get(mlURL)
		if err != nil {
			c.JSON(502, gin.H{"error": "ML service tidak dapat dihubungi"})
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		var result map[string]interface{}
		json.Unmarshal(body, &result)
		c.JSON(resp.StatusCode, result)
	}
}

func trainML() gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			Data []struct {
				Text  string `json:"text" binding:"required"`
				Jenis string `json:"jenis" binding:"required"`
			} `json:"data" binding:"required"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		mlURL := processing.ServiceURL() + "/train"
		body, _ := json.Marshal(map[string]interface{}{"data": req.Data})
		client := &http.Client{Timeout: 60 * time.Second}
		resp, err := client.Post(mlURL, "application/json", bytes.NewBuffer(body))
		if err != nil {
			c.JSON(502, gin.H{"error": "ML service tidak dapat dihubungi"})
			return
		}
		defer resp.Body.Close()
		respBody, _ := io.ReadAll(resp.Body)
		var result map[string]interface{}
		json.Unmarshal(respBody, &result)
		c.JSON(resp.StatusCode, result)
	}
}

func seedML() gin.HandlerFunc {
	return func(c *gin.Context) {
		mlURL := processing.ServiceURL() + "/seed"
		client := &http.Client{Timeout: 60 * time.Second}
		resp, err := client.Post(mlURL, "application/json", nil)
		if err != nil {
			c.JSON(502, gin.H{"error": "ML service tidak dapat dihubungi"})
			return
		}
		defer resp.Body.Close()
		respBody, _ := io.ReadAll(resp.Body)
		var result map[string]interface{}
		json.Unmarshal(respBody, &result)
		c.JSON(resp.StatusCode, result)
	}
}
