package decision

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestUsageMissingAndInvalid(t *testing.T) {
	for _, raw := range []string{`null`, `{}`, `{"prompt_tokens":-1}`, `{"prompt_tokens":"100"}`} {
		i, o, c := parseUsage(json.RawMessage(raw))
		if i != nil || o != nil || c != nil {
			t.Fatal(raw, i, o, c)
		}
	}
	for _, raw := range []string{`{"prompt_tokens":100,"completion_tokens":10,"prompt_cache_hit_tokens":101}`, `{"prompt_tokens":100,"completion_tokens":10}`, `{"prompt_tokens":100,"completion_tokens":10,"prompt_cache_hit_tokens":50,"prompt_cache_miss_tokens":70}`} {
		i, o, c := parseUsage(json.RawMessage(raw))
		if i == nil || o == nil || c != nil {
			t.Fatal(raw, i, o, c)
		}
	}
	i, o, c := parseUsage(json.RawMessage(`{"prompt_tokens":100,"completion_tokens":10,"prompt_tokens_details":{"cached_tokens":0}}`))
	if i == nil || o == nil || c == nil || *c != 0 {
		t.Fatal(i, o, c)
	}
}
func TestLedgerIncludesFailedAttemptsAndCorrelatesRequest(t *testing.T) {
	path := filepath.Join(t.TempDir(), "usage.jsonl")
	ledger, err := OpenUsageLedger(path)
	if err != nil {
		t.Fatal(err)
	}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { reply(w, `{"answers":{}}`) }))
	defer upstream.Close()
	srv := retryServer(upstream.URL)
	srv.config.RecordAttempt = ledger.Record
	w := invoke(srv, fixture, "local")
	ledger.Close()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if w.Code != 502 || len(lines) != 4 {
		t.Fatal(w.Code, len(lines))
	}
	for n, line := range lines {
		var event AttemptUsage
		if json.Unmarshal([]byte(line), &event) != nil {
			t.Fatal(line)
		}
		if event.Attempt != n+1 || event.RequestID == "" || event.RequestID != w.Header().Get("X-Request-ID") || !event.UsageKnown || *event.InputTokens != 100 || *event.CachedTokens != 50 {
			t.Fatal(event)
		}
	}
}
