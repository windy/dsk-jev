package decision

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const fixture = `{"model":"jev-latest","state":{"message":"重复扣款，请今天处理"},"questions":{"a":{"type":"choice","instructions":"部门","criteria":{"billing":"账单","sales":null}},"b":{"type":"score","instructions":"紧急程度","criteria":["不急",{"description":"尽快"},"今天"]},"c":{"type":"noul","instructions":"明确要求退款？"}}}`

func invoke(h http.Handler, body, key string) *httptest.ResponseRecorder {
	r := httptest.NewRequest("POST", "/v1/systemone", strings.NewReader(body))
	r.Header.Set("Authorization", "Bearer "+key)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}
func TestEndToEnd(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" || r.Header.Get("Authorization") != "Bearer upstream" {
			t.Error("wrong upstream routing/auth")
		}
		var body struct {
			Model          string
			Thinking       struct{ Type string }
			Messages       []struct{ Role, Content string }
			ResponseFormat map[string]string `json:"response_format"`
		}
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body.Model != "deepseek-flash" || body.Thinking.Type != "disabled" || body.ResponseFormat["type"] != "json_object" {
			t.Errorf("bad upstream request: %+v", body)
		}
		if len(body.Messages) != 2 || strings.Contains(body.Messages[0].Content, "重复扣款") {
			t.Error("state leaked into stable prefix")
		}
		write(w, 200, map[string]any{"choices": []any{map[string]any{"finish_reason": "stop", "message": map[string]string{"content": `{"answers":[[0.9,0.1],[0.05,0.1,0.85],0.2]}`}}}, "usage": map[string]int{"prompt_tokens": 200, "completion_tokens": 25}})
	}))
	defer upstream.Close()
	s := New(Config{APIKey: "local", UpstreamKey: "upstream", BaseURL: upstream.URL, UpstreamModel: "deepseek-flash"})
	w := invoke(s, fixture, "local")
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	var response Response
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
		t.Fatal(err)
	}
	a := response.Answers["a"].(map[string]any)
	b := response.Answers["b"].(map[string]any)
	c := response.Answers["c"].(map[string]any)
	if a["choice"] != "billing" || math.Abs(a["confidence"].(float64)-0.8) > 1e-9 || math.Abs(b["score"].(float64)-1.8) > 1e-9 || c["noul"] != 0.2 {
		t.Fatal(response)
	}
	if _, ok := c["confidence"]; ok {
		t.Error("noul must not have confidence")
	}
	if response.Usage.InputTokens != 200 || response.Usage.OutputTokens != 25 {
		t.Fatal(response.Usage)
	}
}
func TestRejectInvalidRequestsBeforeUpstream(t *testing.T) {
	s := New(Config{APIKey: "local"})
	for _, body := range []string{`{}`, `null`, fixture + ` {}`, strings.Replace(fixture, `"jev-latest"`, `"unknown"`, 1), strings.Replace(fixture, `"instructions":"部门"`, `"instructions":12`, 1), strings.Replace(fixture, `"criteria":{"billing":"账单","sales":null}`, `"criteria":{}`, 1)} {
		if w := invoke(s, body, "local"); w.Code != 422 {
			t.Errorf("%d: %s", w.Code, body)
		}
	}
	if w := invoke(s, fixture, "wrong"); w.Code != 401 {
		t.Fatal(w.Code)
	}
}
func TestBadUpstream(t *testing.T) {
	for _, tc := range []struct {
		status int
		body   string
		want   int
	}{{429, "secret", 429}, {503, "secret", 529}, {401, "secret", 502}, {200, `{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}`, 502}, {200, `{"choices":[{"finish_reason":"stop","message":{"content":"{\"answers\":[]}"}}]}`, 502}} {
		t.Run(fmt.Sprint(tc.status, tc.body), func(t *testing.T) {
			u := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Retry-After", "2")
				w.WriteHeader(tc.status)
				io.WriteString(w, tc.body)
			}))
			defer u.Close()
			w := invoke(New(Config{APIKey: "local", BaseURL: u.URL}), fixture, "local")
			if w.Code != tc.want || strings.Contains(w.Body.String(), "secret") {
				t.Fatal(w.Code, w.Body.String())
			}
			if tc.status == 429 && w.Header().Get("Retry-After") != "2" {
				t.Error("lost retry-after")
			}
		})
	}
}
func TestProbabilityValidation(t *testing.T) {
	var r Request
	_ = json.Unmarshal([]byte(fixture), &r)
	qs, _ := compile(r)
	for _, s := range []string{`{"answers":[[0,0],[0,0,1],0.5]}`, `{"answers":[[1.1,-0.1],[0,0,1],0.5]}`, `{"answers":[[null,1],[0,0,1],0.5]}`, `{"answers":[[0,1],[0,0,1],null]}`, `{"answers":[[0,1],[0,0,1],true]}`, `{"answers":[[0,1],[0,0,1],2]}`, `{"answers":[[0,1],[0,1],0.5]}`} {
		if _, err := decodeAnswers(s, qs); err == nil {
			t.Error("accepted", s)
		}
	}
	for _, p := range [][]float64{{1, 0, 0}, {0.2, 0.6, 0.2}, {1.0 / 3, 1.0 / 3, 1.0 / 3}} {
		v := confidence(p, true)
		if v < 0 || v > 1 {
			t.Fatal(v)
		}
	}
	if math.Abs(confidence([]float64{0.05, 0.1, 0.85}, true)-0.7) > 1e-9 {
		t.Error("score confidence formula")
	}
}
func TestTimeout(t *testing.T) {
	release := make(chan struct{})
	u := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { <-release }))
	defer u.Close()
	w := invoke(New(Config{APIKey: "local", BaseURL: u.URL, Timeout: 20 * time.Millisecond}), fixture, "local")
	close(release)
	if w.Code != 504 {
		t.Fatal(w.Code)
	}
}
func TestModels(t *testing.T) {
	s := New(Config{APIKey: "local"})
	r := httptest.NewRequest("GET", "/v1/models", nil)
	r.Header.Set("Authorization", "Bearer local")
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 200 || !strings.Contains(w.Body.String(), "jev-latest") {
		t.Fatal(w.Body.String())
	}
}
