package decision

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

func sparseQuestion() compiledQuestion {
	q := compiledQuestion{ID: "large", Key: "q0", Type: "choice"}
	for i := 0; i < 32; i++ {
		q.Labels = append(q.Labels, fmt.Sprintf("label_%02d", i))
	}
	return q
}
func TestFastSparseRoundTripAndValidation(t *testing.T) {
	q := sparseQuestion()
	a, p, err := decodeFastPartial(`{"answers":{"q0":[[3,900],[20,100]]}}`, []compiledQuestion{q})
	if err != nil || len(p) != 0 {
		t.Fatal(err, p)
	}
	answer := a["large"].(map[string]any)
	probs := answer["probabilities"].(map[string]float64)
	if len(probs) != 32 || probs["label_03"] != .9 || probs["label_00"] != 0 || answer["choice"] != "label_03" {
		t.Fatal(answer)
	}
	for _, raw := range []string{`[]`, `null`, `[[3,500],[3,500]]`, `[[32,1000]]`, `[[3,50]]`, `[[3,0]]`, `[[3,1000.1]]`, `[[3]]`} {
		_, _, err := decodeFastPartial(`{"answers":{"q0":`+raw+`}}`, []compiledQuestion{q})
		if err == nil {
			t.Fatal("accepted", raw)
		}
	}
}
func TestFastPreservesPartialRetryAndPublicAnswers(t *testing.T) {
	var req Request
	json.Unmarshal([]byte(fixture), &req)
	qs, err := compile(req)
	if err != nil {
		t.Fatal(err)
	}
	a, p, err := decodeFastPartial(`{"answers":{"q0":[900,100],"q1":[50,100,850],"q2":0.2}}`, qs)
	expected, _, originalErr := decodePartial(goodArguments, qs)
	ab, _ := json.Marshal(a)
	eb, _ := json.Marshal(expected)
	if err != nil || originalErr != nil || len(p) != 0 || string(ab) != string(eb) {
		t.Fatal(string(ab), string(eb), err)
	}
	a, p, err = decodeFastPartial(`{"answers":{"q0":[900,100],"q1":[50,100,850],"q2":null}}`, qs)
	if err == nil || len(a) != 2 || len(p) != 1 || p[0].Key != "q2" {
		t.Fatal(a, p, err)
	}
}
func TestConnectionReuseAndReasoningDisabled(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		if body["thinking"].(map[string]any)["type"] != "disabled" || body["stream"] != false {
			t.Error("unexpected request", body)
		}
		reply(w, goodArguments)
	}))
	defer upstream.Close()
	var events []AttemptUsage
	srv := New(Config{APIKey: "local", BaseURL: upstream.URL, RecordAttempt: func(v AttemptUsage) error { events = append(events, v); return nil }})
	for i := 0; i < 2; i++ {
		if w := invoke(srv, fixture, "local"); w.Code != 200 {
			t.Fatal(w.Code)
		}
	}
	if len(events) != 2 || events[0].Network.ConnectionReused || !events[1].Network.ConnectionReused || events[1].Network.FirstByteMS == nil {
		t.Fatal(events)
	}
}
