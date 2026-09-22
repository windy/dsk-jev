# v0.1.0 — Experimental multimodal decision API

Jev-compatible Choice, Score and Noul endpoints in Go, backed by DeepSeek Flash with thinking disabled. Adds optional image URL/Base64 input, partial retries, token/cache observability and an experimental compact output mode.

## Try it

Download the archive for your OS/architecture, verify it against SHA256SUMS, extract it, set PROXY_API_KEY and DEEPSEEK_API_KEY, and run ./dsk-jev. Default address: 127.0.0.1:8080. Send examples/ticket.json or examples/vision.json using the README curl command. Calls incur upstream API charges. Docker instructions are in README.

macOS archives are not Apple-notarized. Source builds are available with Go 1.26.1+.

## Scope

Experimental release, not an official TypeSafe or DeepSeek product. Does not run Jev weights. Image input is a protocol extension. Confidence is not independently calibrated; current evaluations do not establish better speed, cost, or complex reasoning than Jev. No built-in tenant management, TLS, rate limiting or transactional billing. Plain-text protocol experiments are not shipped.

See docs/benchmarks.md for evidence and limitations. MIT licensed; third-party notices included.
