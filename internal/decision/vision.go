package decision

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
)

const maxImages = 8
const maxInlineImageBytes = 2 << 20

// ImageInput is an optional extension to Jev's text-only request protocol.
// Remote images are fetched by the upstream provider, never by this server.
type ImageInput struct {
	URL    string `json:"url"`
	Detail string `json:"detail,omitempty"`
}

func validateImages(images []ImageInput) error {
	if len(images) > maxImages {
		return fmt.Errorf("images must contain at most %d items", maxImages)
	}
	for i, img := range images {
		bad := func(message string) error { return fmt.Errorf("images[%d]: %s", i, message) }
		switch img.Detail {
		case "", "auto", "low", "high", "original":
		default:
			return bad("detail must be auto, low, high or original")
		}
		if strings.HasPrefix(img.URL, "data:") {
			header, encoded, ok := strings.Cut(img.URL, ",")
			mime := strings.TrimSuffix(strings.TrimPrefix(header, "data:"), ";base64")
			if !ok || !strings.HasSuffix(header, ";base64") {
				return bad("expected a base64 image data URL")
			}
			switch mime {
			case "image/png", "image/jpeg", "image/gif", "image/webp":
			default:
				return bad("supported image types are PNG, JPEG, GIF and WebP")
			}
			if len(encoded) > base64.StdEncoding.EncodedLen(maxInlineImageBytes) {
				return bad("inline image exceeds 2 MiB decoded limit")
			}
			data, err := base64.StdEncoding.Strict().DecodeString(encoded)
			if err != nil || len(data) == 0 {
				return bad("invalid base64 image data")
			}
			if len(data) > maxInlineImageBytes {
				return bad("inline image exceeds 2 MiB decoded limit")
			}
			if http.DetectContentType(data) != mime {
				return bad("image bytes do not match declared media type")
			}
		} else {
			if len(img.URL) > 8192 {
				return bad("image URL exceeds 8192 bytes")
			}
			u, err := url.ParseRequestURI(img.URL)
			if err != nil || u.Hostname() == "" || (u.Scheme != "https" && u.Scheme != "http") || u.User != nil || u.Fragment != "" || strings.Contains(img.URL, "#") {
				return bad("url must be an HTTP(S) URL without credentials or fragment, or a base64 image data URL")
			}
		}
	}
	return nil
}

func userContent(state json.RawMessage, images []ImageInput) any {
	if len(images) == 0 {
		return string(state)
	}
	blocks := []any{map[string]any{"type": "text", "text": string(state)}}
	for _, img := range images {
		ref := map[string]string{"url": img.URL}
		if img.Detail != "" {
			ref["detail"] = img.Detail
		}
		blocks = append(blocks, map[string]any{"type": "image_url", "image_url": ref})
	}
	return blocks
}
