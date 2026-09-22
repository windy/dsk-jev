package decision

import (
	"net/http/httptrace"
	"sync"
	"time"
)

// First response byte is an HTTP timing, not model TTFT: a provider may send
// keepalive whitespace before inference finishes.
type NetworkTiming struct {
	ConnectionReused   bool   `json:"connection_reused"`
	ConnectionObserved bool   `json:"connection_observed"`
	GetConnectionMS    *int64 `json:"get_connection_ms"`
	FirstByteMS        *int64 `json:"first_byte_ms"`
	AfterFirstByteMS   *int64 `json:"after_first_byte_ms"`
}
type attemptTrace struct {
	mu                            sync.Mutex
	start, timeGetConn, firstByte time.Time
	timing                        NetworkTiming
}

func newAttemptTrace(start time.Time) (*attemptTrace, *httptrace.ClientTrace) {
	t := &attemptTrace{start: start}
	return t, &httptrace.ClientTrace{
		GetConn: func(string) { t.mu.Lock(); defer t.mu.Unlock(); t.timeGetConn = time.Now() },
		GotConn: func(info httptrace.GotConnInfo) {
			t.mu.Lock()
			defer t.mu.Unlock()
			t.timing.ConnectionObserved = true
			t.timing.ConnectionReused = info.Reused
			ms := time.Since(t.timeGetConn).Milliseconds()
			t.timing.GetConnectionMS = &ms
		},
		GotFirstResponseByte: func() {
			t.mu.Lock()
			defer t.mu.Unlock()
			t.firstByte = time.Now()
			ms := time.Since(start).Milliseconds()
			t.timing.FirstByteMS = &ms
		},
	}
}
func (t *attemptTrace) snapshot() NetworkTiming {
	t.mu.Lock()
	defer t.mu.Unlock()
	v := t.timing
	if !t.firstByte.IsZero() {
		ms := time.Since(t.firstByte).Milliseconds()
		v.AfterFirstByteMS = &ms
	}
	return v
}
