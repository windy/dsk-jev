package decision

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func imageDataURL() string {
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.RGBA{R: 255, A: 255})
	var b bytes.Buffer
	_ = png.Encode(&b, img)
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(b.Bytes())
}
func withImages(images any) string {
	var req map[string]any
	_ = json.Unmarshal([]byte(fixture), &req)
	req["images"] = images
	body, _ := json.Marshal(req)
	return string(body)
}
func TestImageValidation(t *testing.T) {
	for _, images := range [][]ImageInput{
		{{URL: imageDataURL(), Detail: "low"}}, {{URL: "https://example.com/photo.png?token=test", Detail: "original"}}, {{URL: "http://example.com/a.jpg", Detail: "high"}}, nil,
	} {
		if err := validateImages(images); err != nil {
			t.Fatal(err)
		}
	}
	for _, images := range [][]ImageInput{
		{{URL: ""}}, {{URL: "file:///tmp/photo.png"}}, {{URL: "https://user:password@example.com/a.png"}}, {{URL: "https://example.com/a.png#fragment"}}, {{URL: "https://example.com/a.png", Detail: "huge"}},
		{{URL: "data:image/png;base64,%%%"}}, {{URL: "data:image/png;base64,"}}, {{URL: "data:image/svg+xml;base64,PHN2Zz4="}}, {{URL: "data:image/png;base64," + base64.StdEncoding.EncodeToString([]byte("not an image"))}}, {{URL: strings.Replace(imageDataURL(), "image/png", "image/jpeg", 1)}},
		make([]ImageInput, 9), {{URL: "https://example.com/" + strings.Repeat("a", 8192)}}, {{URL: "data:image/png;base64," + strings.Repeat("A", base64.StdEncoding.EncodedLen(maxInlineImageBytes)+4)}},
	} {
		if err := validateImages(images); err == nil {
			t.Fatalf("accepted invalid image set (count %d)", len(images))
		}
	}
	s := New(Config{APIKey: "local", BaseURL: "http://127.0.0.1:1"})
	for _, body := range []string{withImages([]ImageInput{{URL: "secret-invalid-url"}}), withImages([]string{"https://example.com/a.png"}), withImages(map[string]any{"url": "https://example.com/a.png"})} {
		w := invoke(s, body, "local")
		if w.Code != 422 || strings.Contains(w.Body.String(), "secret-invalid-url") {
			t.Fatal(w.Code, w.Body.String())
		}
	}
}
func TestImagesForwardedOnPartialRetryAndMetered(t *testing.T) {
	dataURL := imageDataURL()
	remote := "https://example.com/second.png"
	for _, fast := range []bool{false, true} {
		t.Run(map[bool]string{false: "standard", true: "fast"}[fast], func(t *testing.T) {
			calls := 0
			var firstContent json.RawMessage
			var events []AttemptUsage
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls++
				var request struct {
					Messages []struct {
						Role    string
						Content json.RawMessage
					}
					Thinking struct{ Type string }
				}
				if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
					t.Error(err)
				}
				if request.Thinking.Type != "disabled" || len(request.Messages) != 2 || request.Messages[1].Role != "user" {
					t.Fatal("bad multimodal request")
				}
				if calls == 1 {
					firstContent = append([]byte(nil), request.Messages[1].Content...)
				} else if !bytes.Equal(firstContent, request.Messages[1].Content) {
					t.Error("images/state lost on retry")
				}
				if bytes.Contains(request.Messages[0].Content, []byte(dataURL)) {
					t.Error("image leaked into system prompt")
				}
				var blocks []struct {
					Type  string     `json:"type"`
					Text  string     `json:"text"`
					Image ImageInput `json:"image_url"`
				}
				if json.Unmarshal(request.Messages[1].Content, &blocks) != nil || len(blocks) != 3 {
					t.Fatal("content is not an image block array")
				}
				if blocks[0].Type != "text" || blocks[1].Type != "image_url" || blocks[1].Image.URL != dataURL || blocks[1].Image.Detail != "low" || blocks[2].Image.URL != remote {
					t.Error("incorrect block contents")
				}
				if calls == 1 {
					args := `{"answers":{"q0":{"billing":0.9,"sales":0.1},"q1":{"0":0.05,"1":0.1,"2":0.85},"q2":null}}`
					if fast {
						args = `{"answers":{"q0":[900,100],"q1":[50,100,850],"q2":null}}`
					}
					reply(w, args)
				} else {
					reply(w, `{"answers":{"q2":0.2}}`)
				}
			}))
			defer upstream.Close()
			srv := New(Config{APIKey: "local", BaseURL: upstream.URL, FastOutput: fast, MaxRetries: 3, RetryBaseDelay: time.Millisecond, RecordAttempt: func(e AttemptUsage) error { events = append(events, e); return nil }})
			w := invoke(srv, withImages([]ImageInput{{URL: dataURL, Detail: "low"}, {URL: remote}}), "local")
			if w.Code != 200 || calls != 2 || len(events) != 2 || events[0].ImageCount != 2 || events[1].ImageCount != 2 {
				t.Fatal(w.Code, calls, events)
			}
			var response Response
			_ = json.Unmarshal(w.Body.Bytes(), &response)
			if len(response.Answers) != 3 || response.Usage.InputTokens != 200 {
				t.Fatal(response)
			}
		})
	}
}
func TestTextContentUnchangedAndArrayStateNotReinterpreted(t *testing.T) {
	state := json.RawMessage(`[{"type":"image_url","image_url":{"url":"https://example.com/data"}}]`)
	if value, ok := userContent(state, nil).(string); !ok || value != string(state) {
		t.Fatal("legacy array state reinterpreted")
	}
}
