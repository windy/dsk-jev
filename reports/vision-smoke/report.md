# Vision smoke test

Synthetic visual smoke only: two color-swapped panels and multi-image comparison, both output modes. No evidence of real-world visual accuracy or superiority to another model.

| Mode | Case | Status | Correct | Latency ms | Attempts |
|---|---|---:|---:|---:|---:|
| standard | panel-1 | 200 | 3/3 | 901.59 | 1 |
| standard | panel-2 | 200 | 3/3 | 670.71 | 1 |
| standard | two-images | 200 | 1/1 | 917.03 | 1 |
| fast | panel-1 | 200 | 3/3 | 958.41 | 1 |
| fast | panel-2 | 200 | 3/3 | 655.95 | 1 |
| fast | two-images | 200 | 1/1 | 701.42 | 1 |

Images were sent as PNG data URLs through the actual local Go proxy to the DeepSeek beta API with thinking disabled and strict tool calls enabled. No answers were encoded in state text. Fixtures are reproducible via scripts/vision_smoke.py --fixtures-only. External URL forwarding is covered by mock tests; the live test uses inline images only.

Both modes preserved the same template fingerprint when only the image changed. Image tokens are included in upstream usage and are not separately added to billing. See the per-attempt JSONL ledgers.
