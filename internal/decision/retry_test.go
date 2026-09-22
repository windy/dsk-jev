package decision

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

const goodArguments = `{"answers":{"q0":{"billing":0.9,"sales":0.1},"q1":{"0":0.05,"1":0.1,"2":0.85},"q2":0.2}}`

func reply(w http.ResponseWriter, args string) {
	write(w, 200, map[string]any{"choices": []any{map[string]any{"finish_reason": "tool_calls", "message": map[string]any{"tool_calls": []any{map[string]any{"type": "function", "function": map[string]string{"name": "submit_decisions", "arguments": args}}}}}}, "usage": map[string]any{"prompt_tokens": 100, "completion_tokens": 10, "prompt_cache_hit_tokens": 50}})
}
func retryServer(url string) *Server {
	return New(Config{APIKey: "local", BaseURL: url, MaxRetries: 3, RetryBaseDelay: time.Millisecond})
}
func TestThreeRetriesAndCumulativeUsage(t *testing.T) {
	var count atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if count.Add(1) < 4 {
			reply(w, `{"answers":{}}`)
		} else {
			reply(w, goodArguments)
		}
	}))
	defer upstream.Close()
	w := invoke(retryServer(upstream.URL), fixture, "local")
	if w.Code != 200 || count.Load() != 4 || w.Header().Get("X-Upstream-Attempts") != "4" {
		t.Fatal(w.Code, count.Load(), w.Body.String())
	}
	var response Response
	_ = json.Unmarshal(w.Body.Bytes(), &response)
	if response.Usage.InputTokens != 400 || response.Usage.OutputTokens != 40 || w.Header().Get("X-Upstream-Cached-Tokens") != "200" {
		t.Fatal(response.Usage, w.Header())
	}
}
func TestPartialRetryOnlyFailedQuestion(t *testing.T) {
	var count atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if count.Add(1) == 1 {
			reply(w, `{"answers":{"q0":{"billing":0.9,"sales":0.1},"q1":{"0":0.05,"1":0.1,"2":0.85},"q2":"bad"}}`)
			return
		}
		var req struct {
			Tools []struct {
				Function struct{ Parameters map[string]any }
			}
		}
		_ = json.NewDecoder(r.Body).Decode(&req)
		p := req.Tools[0].Function.Parameters["properties"].(map[string]any)["answers"].(map[string]any)["properties"].(map[string]any)
		if len(p) != 1 || p["q2"] == nil {
			t.Error("successful questions repeated", p)
		}
		reply(w, `{"answers":{"q2":0.1}}`)
	}))
	defer upstream.Close()
	w := invoke(retryServer(upstream.URL), fixture, "local")
	if w.Code != 200 || count.Load() != 2 {
		t.Fatal(w.Code, count.Load(), w.Body.String())
	}
	var response Response
	_ = json.Unmarshal(w.Body.Bytes(), &response)
	if response.Answers["a"].(map[string]any)["choice"] != "billing" || response.Answers["c"].(map[string]any)["noul"] != 0.1 {
		t.Fatal(response)
	}
}
func TestRetryExhaustion(t *testing.T) {
	var count atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { count.Add(1); reply(w, `{"answers":{}}`) }))
	defer upstream.Close()
	w := invoke(retryServer(upstream.URL), fixture, "local")
	if w.Code != 502 || count.Load() != 4 {
		t.Fatal(w.Code, count.Load())
	}
}
func TestPermanentErrorsNotRetried(t *testing.T) {
	for _, status := range []int{400, 401, 403, 422} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			var count atomic.Int32
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { count.Add(1); w.WriteHeader(status) }))
			defer upstream.Close()
			w := invoke(retryServer(upstream.URL), fixture, "local")
			if w.Code != 502 || count.Load() != 1 {
				t.Fatal(w.Code, count.Load())
			}
		})
	}
}
func TestTransientErrorsRetried(t *testing.T) {
	for _, status := range []int{408, 429, 500, 502, 503, 529} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			var count atomic.Int32
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if count.Add(1) == 1 {
					w.WriteHeader(status)
				} else {
					reply(w, goodArguments)
				}
			}))
			defer upstream.Close()
			w := invoke(retryServer(upstream.URL), fixture, "local")
			if w.Code != 200 || count.Load() != 2 {
				t.Fatal(w.Code, count.Load())
			}
		})
	}
}
func TestRetryAfterBudgetAndCancellation(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	if retryDelay(time.Millisecond, 1, "2", now) < 2*time.Second {
		t.Fatal("ignored seconds")
	}
	if retryDelay(time.Millisecond, 1, now.Add(3*time.Second).Format(http.TimeFormat), now) < 3*time.Second {
		t.Fatal("ignored date")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	if waitRetry(ctx, time.Second, 1, "10") == nil || time.Since(start) > time.Second {
		t.Fatal("ignored cancellation")
	}
	var count atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count.Add(1)
		w.Header().Set("Retry-After", "10")
		w.WriteHeader(429)
	}))
	defer upstream.Close()
	s := retryServer(upstream.URL)
	s.config.Timeout = 30 * time.Millisecond
	w := invoke(s, fixture, "local")
	if w.Code != 504 || count.Load() != 1 {
		t.Fatal(w.Code, count.Load())
	}
}
