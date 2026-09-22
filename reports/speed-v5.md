# Standard vs fast output encoding

Interleaved sequential A/B on same host, persistent connections, standard vs fast encoding (also shorter prompt). 3 retries/30s upstream budget. Warm cache not flushed. Existing regression and historical holdout, not unseen blind tests. USD costs are public peak/offpeak estimates. First-byte timings are HTTP bytes, not generated-token TTFT.

UTC: 2026-09-22T08:25:29.702430+00:00 — 2026-09-22T08:27:25.190019+00:00

| Metric | Standard | Fast |
|---|---:|---:|
| Success | 56/56 | 56/56 |
| Correct judgments | 157/157 | 156/157 |
| P50 ms | 808.47 | 826.28 |
| P95 ms | 1322.15 | 1902.61 |
| Output tokens | 11169 | 4647 |
| Attempts | 57 | 63 |
| Cache hit ratio | 0.8684038653782072 | 0.6048528396722298 |
| Peak USD / 1k requests | 0.2992073571428571 | 0.22284921428571428 |
| Reused connections | 56 | 62 |

Fast mode is experimental: upstream probability integers use thousandths; questions with >=16 options use a sparse representation of all nonzero probabilities. Go reconstructs every public probability key and derives confidence/score normally. This changes model conditioning and probability precision; passing classification accuracy does not establish calibrated probabilities. Default remains standard.
