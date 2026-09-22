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
	out, err := decodeOrderedAnswers(`{"answers":[[0.1,0.9]]}`, qs)
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
	a, err := decodeOrderedAnswers(`{"answers":[[0.499,0.499],[0.333,0.333,0.333],0]}`, qs)
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

func TestKeyedAnswers(t *testing.T) {
	var req Request
	_ = json.Unmarshal([]byte(fixture), &req)
	qs, _ := compile(req)
	valid := `{"answers":{"q2":0.2,"q1":{"2":0.85,"0":0.05,"1":0.1},"q0":{"sales":0.1,"billing":0.9}}}`
	out, err := decodeAnswers(valid, qs)
	if err != nil {
		t.Fatal(err)
	}
	if out["a"].(map[string]any)["choice"] != "billing" {
		t.Fatal(out)
	}
	for _, v := range []string{
		strings.Replace(valid, `"q2"`, `"wrong"`, 1),
		strings.Replace(valid, `"sales"`, `"unknown"`, 1),
		strings.Replace(valid, `"sales":0.1,`, "", 1),
		strings.Replace(valid, `"sales":0.1`, `"extra":0,"sales":0.1`, 1),
		`{"answers":[[0.9,0.1],[0.05,0.1,0.85],0.2]}`,
	} {
		if _, err := decodeAnswers(v, qs); err == nil {
			t.Fatal("accepted mismatched IDs", v)
		}
	}
}

func TestOutputSchemaRequiredFields(t *testing.T) {
	var req Request
	_ = json.Unmarshal([]byte(fixture), &req)
	qs, _ := compile(req)
	var visit func(map[string]any)
	visit = func(s map[string]any) {
		if s["type"] == "number" {
			if s["minimum"] != 0 || s["maximum"] != 1 {
				t.Fatal(s)
			}
			return
		}
		if s["type"] != "object" || s["additionalProperties"] != false {
			t.Fatal(s)
		}
		props := s["properties"].(map[string]any)
		required := s["required"].([]string)
		if len(props) != len(required) {
			t.Fatal("optional schema fields")
		}
		for _, key := range required {
			child, ok := props[key]
			if !ok {
				t.Fatal(key)
			}
			visit(child.(map[string]any))
		}
	}
	visit(outputSchema(qs))
}

func TestCanonicalSchemaCachePrefix(t *testing.T) {
	a := `{"state":"one","questions":{"x":{"type":"choice","instructions":{"b":2,"a":"pick"},"criteria":{"yes":{"z":0,"a":"true"},"no":null}}}}`
	b := `{"state":"two","questions":{"x":{"criteria":{"no":null,"yes":{"a":"true","z":0}},"instructions":{ "a":"pick", "b":2 },"type":"choice"}}}`
	var x, y Request
	_ = json.Unmarshal([]byte(a), &x)
	_ = json.Unmarshal([]byte(b), &y)
	qx, _ := compile(x)
	qy, _ := compile(y)
	sx, _ := json.Marshal(outputSchema(qx))
	sy, _ := json.Marshal(outputSchema(qy))
	if string(sx) != string(sy) {
		t.Fatalf("semantically identical descriptions changed cache prefix: %s vs %s", sx, sy)
	}
}
