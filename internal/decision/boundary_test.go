package decision

import (
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCriteriaBoundaries(t *testing.T) {
	for _, n := range []int{0, 1, 2, 255, 256} {
		t.Run(fmt.Sprintf("choice_%d", n), func(t *testing.T) {
			m := map[string]any{}
			for i := 0; i < n; i++ {
				m[fmt.Sprint(i)] = nil
			}
			criteria, _ := json.Marshal(m)
			_, err := compile(Request{State: json.RawMessage(`"text"`), Questions: map[string]Question{"x": {Type: "choice", Instructions: json.RawMessage(`"pick"`), Criteria: criteria}}})
			if (err == nil) != (n >= 1 && n <= 255) {
				t.Fatal(n, err)
			}
		})
	}
	for _, n := range []int{0, 1, 2, 10, 11} {
		t.Run(fmt.Sprintf("score_%d", n), func(t *testing.T) {
			a := make([]string, n)
			criteria, _ := json.Marshal(a)
			_, err := compile(Request{State: json.RawMessage(`[]`), Questions: map[string]Question{"x": {Type: "score", Instructions: json.RawMessage(`{}`), Criteria: criteria}}})
			if (err == nil) != (n >= 2 && n <= 10) {
				t.Fatal(n, err)
			}
		})
	}
}
func TestRoutes(t *testing.T) {
	for _, tc := range []struct {
		method, path string
		status       int
	}{{"GET", "/healthz", 200}, {"GET", "/v1/systemone", 405}, {"POST", "/v1/models", 405}, {"GET", "/missing", 404}} {
		t.Run(tc.method+tc.path, func(t *testing.T) {
			r := httptest.NewRequest(tc.method, tc.path, nil)
			r.Header.Set("Authorization", "Bearer key")
			w := httptest.NewRecorder()
			New(Config{APIKey: "key"}).ServeHTTP(w, r)
			if w.Code != tc.status {
				t.Fatal(w.Code)
			}
		})
	}
}
func TestStructuredCriteriaAndIDs(t *testing.T) {
	var req Request
	if err := json.Unmarshal([]byte(`{"state":["用户请求退款"],"questions":{"题目/~\"":{"type":"score","instructions":{"question":"评级"},"criteria":["低",{"description":"高"}]}}}`), &req); err != nil {
		t.Fatal(err)
	}
	qs, err := compile(req)
	if err != nil {
		t.Fatal(err)
	}
	out, err := decodeAnswers(`{"answers":[[0.1,0.9]]}`, qs)
	if err != nil {
		t.Fatal(err)
	}
	a := out["题目/~\""].(map[string]any)
	if a["legend"].(map[string]string)["1"] != `{"description":"高"}` {
		t.Fatal(a)
	}
}
func TestOversizedRequest(t *testing.T) {
	w := invoke(New(Config{APIKey: "local"}), `{"state":"`+strings.Repeat("a", 4<<20)+`"}`, "local")
	if w.Code != 422 {
		t.Fatal(w.Code)
	}
}
func TestRoundingAndTies(t *testing.T) {
	var req Request
	_ = json.Unmarshal([]byte(fixture), &req)
	qs, _ := compile(req)
	a, err := decodeAnswers(`{"answers":[[0.499,0.499],[0.333,0.333,0.333],0]}`, qs)
	if err != nil {
		t.Fatal(err)
	}
	if a["a"].(map[string]any)["choice"] != "billing" {
		t.Fatal(a)
	}
	if confidence([]float64{1}, false) != 1 {
		t.Fatal("single choice")
	}
}
