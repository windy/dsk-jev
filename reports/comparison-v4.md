# Jev / DeepSeek paired comparison

Frozen synthetic regression set (previously used for tuning), sequential paired calls with alternating order, persistent connections, same host/time window, max3 retries/30s upstream budget. DeepSeek includes local proxy overhead. Warm cache not flushed; results are not cold-start or load-test measurements. Peak/offpeak are cost scenarios, not actual debit. All attempts including failures billed when usage is available.

UTC: 2026-09-22T08:15:20.870792+00:00 — 2026-09-22T08:16:20.890957+00:00

| Metric | Jev | DeepSeek standard |
|---|---:|---:|
| Successful requests | 44/44 | 44/44 |
| Correct judgments | 139/140 | 138/140 |
| P50 ms | 318.19 | 909.39 |
| P95 ms | 374.11 | 1231.04 |
| Upstream attempts | 44 | 44 |
| Estimated USD (DeepSeek peak) | 0.001377684 | 0.009677712 |
| Estimated USD (DeepSeek offpeak) | 0.001377684 | 0.004838856 |
| USD / 1k requests (peak) | 0.031311 | 0.219948 |
| USD / 1k correct judgments (peak) | 0.009911395683453237 | 0.07012834782608696 |

Accuracy is on this small, hand-authored regression set only. HTTP success does not imply a correct judgment. Full results contain all failures and answers; ledgers contain each attempt and cache usage. Missing usage produces a null total, not zero cost.

[Jev prices](https://docs.typesafe.ai/models) · [DeepSeek prices](https://api-docs.deepseek.com/quick_start/pricing/)

DeepSeek input cache hit ratio: 87.12%. Most-used template: 26 calls; cached tokens each call: [896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 896, 4480]. A hit can cover only part of a template; this is not a guarantee of full-prefix reuse. Output accounts for 74.44% of estimated DeepSeek cost.
