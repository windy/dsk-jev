# Standard vs fast output encoding

Interleaved sequential A/B on same host, persistent connections, standard vs fast encoding (also shorter prompt). 3 retries/30s upstream budget. Warm cache not flushed. Existing regression and historical holdout, not unseen blind tests. USD costs are public peak/offpeak estimates. First-byte timings are HTTP bytes, not generated-token TTFT.

UTC: 2026-09-22T08:28:21.335247+00:00 — 2026-09-22T08:29:56.416959+00:00

| Metric | Standard | Fast |
|---|---:|---:|
| Success | 56/56 | 56/56 |
| Correct judgments | 155/157 | 155/157 |
| P50 ms | 798.11 | 750.34 |
| P95 ms | 1278.99 | 1174.91 |
| Output tokens | 6783 | 3625 |
| Attempts | 57 | 58 |
| Cache hit ratio | 0.8502672182131104 | 0.5344965792368063 |
| Peak USD / 1k requests | 0.20451642857142857 | 0.2145237857142857 |
| Reused connections | 56 | 57 |

Fast mode is experimental: choice/score use dense thousandth-integer arrays or sparse [index,weight] arrays at >=16 options; noul remains an unscaled probability. Go reconstructs every public probability key and derives confidence/score normally. This changes model conditioning and probability precision; passing classification accuracy does not establish calibrated probabilities. Default remains standard.

## Interpretation

Output tokens fell 46.56%; P50 improved 5.99% and P95 8.13% in this run. The 255-option case fell from 4591.75 ms / 1820 output tokens to 607.87 ms / 43 output tokens; both were correct without retries. Most of the dramatic improvement is in large-option output, not small requests.

Estimated aggregate peak cost increased 4.89% in this run ($0.011452920 to $0.012013332). New fast templates had 53.45% input cache hits versus 85.03% for standard; this mixed-template run is not evidence that fast mode is cheaper in steady state. Both modes reused every observed connection after the initial connection, with connection-acquisition P50/P95 below 1 ms. Non-streaming HTTP first-byte timing cannot isolate actual model decoding time. The request explicitly disables thinking; the upstream did not return a reasoning-token breakdown, so its absence is not proof of zero reasoning tokens.

Validation: Go race tests, Go vet, pricing unit tests, and official TypeSafe SDK smoke test for the default mode passed. Fast decoder tests verify matching public results, sparse reconstruction, rejection of bad probabilities/indices, and preservation of partial retries. Default remains standard; enable the tested experiment with OUTPUT_MODE=fast.
