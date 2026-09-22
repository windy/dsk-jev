package main

import (
	"context"
	"dsk-jev/internal/decision"
	"errors"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
)

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
func main() {
	c := decision.Config{APIKey: os.Getenv("PROXY_API_KEY"), UpstreamKey: os.Getenv("DEEPSEEK_API_KEY"), BaseURL: env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/beta"), UpstreamModel: env("DEEPSEEK_MODEL", "deepseek-flash")}
	if c.APIKey == "" || c.UpstreamKey == "" {
		slog.Error("PROXY_API_KEY and DEEPSEEK_API_KEY are required")
		os.Exit(1)
	}
	u, e := url.Parse(c.BaseURL)
	if e != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		slog.Error("invalid DEEPSEEK_BASE_URL")
		os.Exit(1)
	}
	c.Timeout, e = time.ParseDuration(env("UPSTREAM_TIMEOUT", "30s"))
	if e != nil || c.Timeout <= 0 {
		slog.Error("invalid UPSTREAM_TIMEOUT")
		os.Exit(1)
	}
	c.MaxRetries, e = strconv.Atoi(env("MAX_RETRIES", "3"))
	if e != nil || c.MaxRetries < 0 || c.MaxRetries > 10 {
		slog.Error("MAX_RETRIES must be 0..10")
		os.Exit(1)
	}
	mode := env("PROMPT_MODE", "standard")
	if mode != "compact" && mode != "standard" {
		slog.Error("PROMPT_MODE must be compact or standard")
		os.Exit(1)
	}
	c.CompactPrompt = mode == "compact"
	outputMode := env("OUTPUT_MODE", "standard")
	if outputMode != "standard" && outputMode != "fast" {
		slog.Error("OUTPUT_MODE must be standard or fast")
		os.Exit(1)
	}
	c.FastOutput = outputMode == "fast"
	if path := os.Getenv("USAGE_LEDGER_PATH"); path != "" {
		ledger, err := decision.OpenUsageLedger(path)
		if err != nil {
			slog.Error("cannot open usage ledger", "error", err)
			os.Exit(1)
		}
		defer ledger.Close()
		c.RecordAttempt = ledger.Record
	}
	srv := &http.Server{Addr: env("LISTEN_ADDR", "127.0.0.1:8080"), Handler: decision.New(c), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: c.Timeout + 10*time.Second, IdleTimeout: 60 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdown)
	}()
	slog.Info("listening", "addr", srv.Addr, "upstream_model", c.UpstreamModel)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("server failed", "error", err)
		os.Exit(1)
	}
}
