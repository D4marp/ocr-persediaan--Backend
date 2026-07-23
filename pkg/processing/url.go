package processing

import "os"

func ServiceURL() string {
	if url := os.Getenv("PROCESSING_SERVICE_URL"); url != "" {
		return url
	}
	return "http://127.0.0.1:8090"
}
