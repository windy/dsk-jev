package decision

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
)

type Question struct {
	Type         string          `json:"type"`
	Instructions json.RawMessage `json:"instructions"`
	Criteria     json.RawMessage `json:"criteria,omitempty"`
}
type Request struct {
	Model     string              `json:"model"`
	State     json.RawMessage     `json:"state"`
	Questions map[string]Question `json:"questions"`
}
type Usage struct {
	InputTokens  int `json:"input_tokens"`
	OutputTokens int `json:"output_tokens"`
}
type Response struct {
	Model   string         `json:"model"`
	Answers map[string]any `json:"answers"`
	Usage   Usage          `json:"usage"`
}
type compiledQuestion struct {
	ID           string            `json:"-"`
	Key          string            `json:"id"`
	Type         string            `json:"type"`
	Instructions json.RawMessage   `json:"instructions"`
	Criteria     any               `json:"criteria,omitempty"`
	Labels       []string          `json:"-"`
	Legend       map[string]string `json:"-"`
}

func description(v json.RawMessage, nullable bool) bool {
	var x any
	if json.Unmarshal(v, &x) != nil {
		return false
	}
	switch x.(type) {
	case string, map[string]any, []any:
		return true
	case nil:
		return nullable
	}
	return false
}
func compile(r Request) ([]compiledQuestion, error) {
	if !description(r.State, false) {
		return nil, fmt.Errorf("state must be a string, object or array")
	}
	if len(r.Questions) == 0 {
		return nil, fmt.Errorf("questions must not be empty")
	}
	ids := make([]string, 0, len(r.Questions))
	for id := range r.Questions {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	out := make([]compiledQuestion, 0, len(ids))
	for _, id := range ids {
		q := r.Questions[id]
		fail := func() ([]compiledQuestion, error) {
			return nil, fmt.Errorf("invalid questions[%q]: check type, instructions and criteria", id)
		}
		if !description(q.Instructions, false) {
			return fail()
		}
		c := compiledQuestion{ID: id, Key: fmt.Sprintf("q%d", len(out)), Type: q.Type, Instructions: canonicalJSON(q.Instructions)}
		switch q.Type {
		case "choice":
			var m map[string]json.RawMessage
			if json.Unmarshal(q.Criteria, &m) != nil || len(m) < 1 || len(m) > 255 {
				return fail()
			}
			for k, v := range m {
				if !description(v, true) {
					return fail()
				}
				c.Labels = append(c.Labels, k)
			}
			sort.Strings(c.Labels)
			for k, v := range m {
				m[k] = canonicalJSON(v)
			}
			c.Criteria = m
		case "score":
			var levels []json.RawMessage
			if json.Unmarshal(q.Criteria, &levels) != nil || len(levels) < 2 || len(levels) > 10 {
				return fail()
			}
			c.Legend = map[string]string{}
			for i, v := range levels {
				if !description(v, false) {
					return fail()
				}
				k := strconv.Itoa(i)
				c.Labels = append(c.Labels, k)
				var s string
				if json.Unmarshal(v, &s) != nil {
					b, _ := json.Marshal(canonicalJSON(v))
					s = string(b)
				}
				c.Legend[k] = s
			}
			c.Criteria = c.Legend
		case "noul":
			if len(q.Criteria) > 0 && string(q.Criteria) != "null" {
				var m map[string]json.RawMessage
				if json.Unmarshal(q.Criteria, &m) != nil {
					return fail()
				}
				for k, v := range m {
					if (k != "true" && k != "false") || !description(v, false) {
						return fail()
					}
				}
				for k, v := range m {
					m[k] = canonicalJSON(v)
				}
				c.Criteria = m
			}
		default:
			return fail()
		}
		out = append(out, c)
	}
	return out, nil
}

// Formulae follow TypeSafe's public System One adapter; see THIRD_PARTY_NOTICES.
func confidence(p []float64, score bool) float64 {
	if len(p) == 1 {
		return 1
	}
	mode := 0
	for i := range p {
		if p[i] > p[mode] {
			mode = i
		}
	}
	if !score {
		u := 1 / float64(len(p))
		return math.Max(0, (p[mode]-u)/(1-u))
	}
	distance, uniform := 0.0, 0.0
	center := float64(len(p)-1) / 2
	for i, v := range p {
		distance += v * math.Abs(float64(i-mode))
		uniform += math.Abs(float64(i)-center) / float64(len(p))
	}
	return math.Max(0, 1-distance/uniform)
}
func decodeOrderedAnswers(content string, qs []compiledQuestion) (map[string]any, error) {
	var raw struct {
		Answers []json.RawMessage `json:"answers"`
	}
	if json.Unmarshal([]byte(content), &raw) != nil || len(raw.Answers) != len(qs) {
		return nil, fmt.Errorf("invalid answer count or JSON")
	}
	out := map[string]any{}
	for i, q := range qs {
		a := map[string]any{"type": q.Type}
		if q.Type == "noul" {
			var p *float64
			if json.Unmarshal(raw.Answers[i], &p) != nil || p == nil || *p < 0 || *p > 1 {
				return nil, fmt.Errorf("invalid noul probability")
			}
			a["noul"] = *p
		} else {
			var values []*float64
			if json.Unmarshal(raw.Answers[i], &values) != nil || len(values) != len(q.Labels) {
				return nil, fmt.Errorf("invalid probability array")
			}
			sum := 0.0
			p := make([]float64, len(values))
			for j, v := range values {
				if v == nil || *v < 0 || *v > 1 {
					return nil, fmt.Errorf("invalid probability")
				}
				p[j] = *v
				sum += *v
			}
			// Normalize rounding drift only, never manufacture a distribution from garbage.
			if math.Abs(sum-1) > 0.02 {
				return nil, fmt.Errorf("probabilities must sum to one")
			}
			probs := map[string]float64{}
			score := 0.0
			mode := 0
			for j := range p {
				p[j] /= sum
			}
			for j := range p {
				probs[q.Labels[j]] = p[j]
				score += float64(j) * p[j]
				if p[j] > p[mode] {
					mode = j
				}
			}
			a["probabilities"] = probs
			a["confidence"] = confidence(p, q.Type == "score")
			if q.Type == "choice" {
				a["choice"] = q.Labels[mode]
			} else {
				a["score"] = score
				a["legend"] = q.Legend
			}
		}
		out[q.ID] = a
	}
	return out, nil
}

// Bind generated probabilities to explicit IDs before deriving public answers.
// Reject missing/unknown IDs instead of silently assigning them by position.
func decodeAnswers(content string, qs []compiledQuestion) (map[string]any, error) {
	var envelope struct {
		Answers map[string]json.RawMessage `json:"answers"`
	}
	if err := json.Unmarshal([]byte(content), &envelope); err != nil || len(envelope.Answers) != len(qs) {
		return nil, fmt.Errorf("answer_keys_mismatch")
	}
	values := make([]json.RawMessage, len(qs))
	for i, q := range qs {
		raw, ok := envelope.Answers[q.Key]
		if !ok {
			return nil, fmt.Errorf("question_%d_missing", i)
		}
		if q.Type == "noul" {
			values[i] = raw
			continue
		}
		var probs map[string]json.RawMessage
		if json.Unmarshal(raw, &probs) != nil || len(probs) != len(q.Labels) {
			return nil, fmt.Errorf("question_%d_option_count_mismatch", i)
		}
		ordered := make([]json.RawMessage, len(q.Labels))
		for j, label := range q.Labels {
			v, ok := probs[label]
			if !ok {
				return nil, fmt.Errorf("question_%d_option_missing", i)
			}
			ordered[j] = v
		}
		values[i], _ = json.Marshal(ordered)
	}
	ordered, _ := json.Marshal(map[string]any{"answers": values})
	return decodeOrderedAnswers(string(ordered), qs)
}

func outputSchema(qs []compiledQuestion) map[string]any {
	object := func(props map[string]any, required []string) map[string]any {
		return map[string]any{"type": "object", "properties": props, "required": required, "additionalProperties": false}
	}
	props := map[string]any{}
	keys := []string{}
	for _, q := range qs {
		desc := string(q.Instructions)
		var schema map[string]any
		if q.Type == "noul" {
			criteria, _ := json.Marshal(q.Criteria)
			schema = map[string]any{"type": "number", "minimum": 0, "maximum": 1, "description": "Probability of yes/true. " + desc + " Criteria: " + string(criteria)}
		} else {
			levels := map[string]any{}
			raw, _ := json.Marshal(q.Criteria)
			var criteria map[string]json.RawMessage
			_ = json.Unmarshal(raw, &criteria)
			for _, label := range q.Labels {
				levels[label] = map[string]any{"type": "number", "minimum": 0, "maximum": 1, "description": string(criteria[label])}
			}
			schema = object(levels, q.Labels)
			schema["description"] = q.Type + ": " + desc + " Return probabilities summing to 1 across all keys."
		}
		props[q.Key] = schema
		keys = append(keys, q.Key)
	}
	return object(map[string]any{"answers": object(props, keys)}, []string{"answers"})
}

// Canonicalize descriptions so whitespace and object-key order from callers do
// not unnecessarily change the stable upstream prefix. Preserve JSON numbers.
func canonicalJSON(raw json.RawMessage) json.RawMessage {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var value any
	if dec.Decode(&value) != nil {
		return raw
	}
	b, err := json.Marshal(value)
	if err != nil {
		return raw
	}
	return b
}
