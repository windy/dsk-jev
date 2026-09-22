package decision

import (
	"encoding/json"
	"os"
	"sync"
	"time"
)

type requestIDKey struct{}

// AttemptUsage contains metering facts, never a claimed invoice amount.
// Nil token counts mean unknown, not zero. Payloads and credentials are omitted.
type AttemptUsage struct {
	RequestID    string          `json:"request_id"`
	Provider     string          `json:"provider"`
	Model        string          `json:"model"`
	UpstreamID   string          `json:"upstream_id,omitempty"`
	TemplateID   string          `json:"template_id"`
	StartedAt    time.Time       `json:"started_at"`
	Attempt      int             `json:"attempt"`
	HTTPStatus   int             `json:"http_status"`
	LatencyMS    int64           `json:"latency_ms"`
	Outcome      string          `json:"outcome"`
	UsageKnown   bool            `json:"usage_known"`
	InputTokens  *int            `json:"input_tokens"`
	OutputTokens *int            `json:"output_tokens"`
	CachedTokens *int            `json:"cached_tokens"`
	RawUsage     json.RawMessage `json:"raw_usage,omitempty"`
}

type UsageLedger struct {
	mu   sync.Mutex
	file *os.File
}

func OpenUsageLedger(path string) (*UsageLedger, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return nil, err
	}
	return &UsageLedger{file: f}, nil
}
func (l *UsageLedger) Record(v AttemptUsage) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	return json.NewEncoder(l.file).Encode(v)
}
func (l *UsageLedger) Close() error { l.mu.Lock(); defer l.mu.Unlock(); return l.file.Close() }

func parseUsage(raw json.RawMessage) (input, output, cached *int) {
	var u struct {
		Input   *int `json:"prompt_tokens"`
		Output  *int `json:"completion_tokens"`
		Cache   *int `json:"prompt_cache_hit_tokens"`
		Miss    *int `json:"prompt_cache_miss_tokens"`
		Details struct {
			Cache *int `json:"cached_tokens"`
		} `json:"prompt_tokens_details"`
	}
	if json.Unmarshal(raw, &u) != nil {
		return
	}
	input, output = u.Input, u.Output
	if input != nil && *input < 0 {
		input = nil
	}
	if output != nil && *output < 0 {
		output = nil
	}
	cached = u.Cache
	if cached == nil {
		cached = u.Details.Cache
	}
	if cached != nil && (input == nil || *cached < 0 || *cached > *input) {
		cached = nil
	}
	if cached != nil && u.Cache != nil && u.Details.Cache != nil && *u.Cache != *u.Details.Cache {
		cached = nil
	}
	if cached != nil && u.Miss != nil && (*u.Miss < 0 || *cached+*u.Miss != *input) {
		cached = nil
	}
	return
}
