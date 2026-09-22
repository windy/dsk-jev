# Jev / DeepSeek paired comparison

BBH author-released data, pinned revision, fixed hash sample: 30 questions per selected task, 10 tasks, 300 questions; zero-shot choice adaptation, no reasoning mode, no prompt tuning on this set; not a full BBH leaderboard score; sequential paired calls with alternating order, persistent connections, same host/time window, max3 retries/30s upstream budget. DeepSeek includes local proxy overhead. Warm cache not flushed; results are not cold-start or load-test measurements. Peak/offpeak are cost scenarios, not actual debit. All attempts including failures billed when usage is available.

UTC: 2026-09-22T11:58:36.656579+00:00 — 2026-09-22T12:04:43.237860+00:00

| Metric | Jev | DeepSeek standard |
|---|---:|---:|
| Successful requests | 300/300 | 300/300 |
| Correct judgments | 274/300 | 177/300 |
| P50 ms | 352.95 | 700.43 |
| P95 ms | 547.84 | 992.65 |
| Upstream attempts | 300 | 302 |
| Estimated USD (DeepSeek peak) | 0.005741400 | 0.059250708 |
| Estimated USD (DeepSeek offpeak) | 0.005741400 | 0.029625354 |
| USD / 1k requests (peak) | 0.019138 | 0.19750236 |
| USD / 1k correct judgments (peak) | 0.020954014598540145 | 0.3347497627118644 |

Accuracy applies only to the selected dataset and protocol. HTTP success does not imply a correct judgment. Full results contain all failures and answers; ledgers contain each attempt and cache usage. Missing usage produces a null total, not zero cost.

[Jev prices](https://docs.typesafe.ai/models) · [DeepSeek prices](https://api-docs.deepseek.com/quick_start/pricing/)
