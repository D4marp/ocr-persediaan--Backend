package db

import (
	"database/sql"
	"fmt"

	_ "github.com/go-sql-driver/mysql"
)

type Config struct {
	Host     string
	Port     string
	User     string
	Password string
	Name     string
}

func NewMySQLPool(cfg Config) (*sql.DB, error) {
	if cfg.Host == "" || cfg.User == "" || cfg.Name == "" {
		return nil, fmt.Errorf("DB_HOST/DB_USER/DB_NAME tidak diset")
	}
	if cfg.Port == "" {
		cfg.Port = "3306"
	}
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&loc=Local",
		cfg.User, cfg.Password, cfg.Host, cfg.Port, cfg.Name)

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
