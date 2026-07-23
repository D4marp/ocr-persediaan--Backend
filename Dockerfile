FROM golang:1.22-alpine AS builder
ENV GOTOOLCHAIN=auto
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o server ./cmd/server

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    libgl1 \
    libglib2.0-0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY python/requirements.txt ./python/
RUN pip install --no-cache-dir -r python/requirements.txt

COPY python/ ./python/
COPY --from=builder /app/server .
COPY scripts/start.sh ./start.sh
RUN chmod +x start.sh && mkdir -p python/models uploads

EXPOSE 8080
CMD ["./start.sh"]
