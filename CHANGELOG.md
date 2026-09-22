# Changelog

## 0.1.0 — 2026-09-22 (experimental)

- Jev-compatible text decision endpoints backed by DeepSeek Flash with thinking disabled.
- Choice, Score and Noul, local probability validation and bounded partial retries.
- Optional image URL/Base64 input, multiple images and visual smoke fixtures.
- Per-attempt usage records, cache and connection telemetry, versioned cost estimates.
- Experimental compact output mode; standard output remains the default.
- Docker, offline CI, and Linux/macOS amd64/arm64 release archives with SHA-256 checksums.

Limitations: uncalibrated model probabilities, small synthetic evaluations, no demonstrated speed/cost advantage over Jev, and no production account/billing/rate-limit system. Plain-text output research is not shipped. macOS packages are not notarized.
