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
	c := decision.Config{APIKey: os.Getenv("PROXY_API_KEY"), UpstreamKey: os.Getenv("DEEPSEEK_API_KEY"), BaseURL: env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"), UpstreamModel: env("DEEPSEEK_MODEL", "deepseek-flash")}
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
