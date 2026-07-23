package db

import (
	"database/sql"
	"fmt"

	_ "github.com/go-sql-driver/mysql"
)

func NewMySQLPool(dsn string) (*sql.DB, error) {
	if dsn == "" {
		return nil, fmt.Errorf("DB_URL tidak diset")
	}
	pool, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, fmt.Errorf("gagal membuka koneksi database: %w", err)
	}
	pool.SetMaxOpenConns(25)
	pool.SetMaxIdleConns(25)
	if err := pool.Ping(); err != nil {
		return nil, fmt.Errorf("gagal ping database: %w", err)
	}
	return pool, nil
}
