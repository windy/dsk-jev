# Benchmarks and limitations

These are small, hand-authored synthetic evaluations from September 22, 2026, not independent production or blind benchmarks. The regression set was used during development; the historical holdout has since been inspected. Network timing and provider cache state vary. Do not combine measurements from different runs into a single winning claim.

## Default-mode paired text comparison

Source: [comparison-v4 summary](../reports/comparison-v4-summary.json), [raw results](../reports/comparison-v4-results.json), [methodology](../reports/comparison-v4.md).

Same host/time window, 44 requests / 140 judgments per provider, alternating provider order, persistent HTTP connections, concurrency 1. Up to 3 retries within a 30-second upstream budget (none occurred). DeepSeek uses standard prompt/output, thinking disabled. Jev and DeepSeek may tokenize the same input differently.

| Metric | Jev | dsk-jev / DeepSeek |
|---|---:|---:|
| Successful requests | 44/44 | 44/44 |
| Correct / all expected judgments | 139/140 | 138/140 |
| P50 end-to-end | 318 ms | 909 ms |
| P95 end-to-end | 374 ms | 1,231 ms |
| Estimated USD / 1,000 requests | 0.0313 | 0.2199 peak / 0.1100 offpeak |
| Input cache-hit fraction | Not reported | 87.1% |

This run does not show a latency, accuracy or cost advantage over Jev. Costs are estimates from the [versioned public price snapshot](../config/pricing.json), not actual debits; taxes, credits and hosting are excluded. Failed attempts with known usage belong in costs; unknown usage must not be treated as free. Failure judgments count against effective accuracy. Choice uses exact winner, Noul uses >=0.5, Score rounds to the nearest level; this is not confidence calibration.

Reproduce after building the binary and setting both provider keys (paid):

```sh
EVAL_PREFIX=my-new-comparison python3 scripts/compare_eval.py
```

## Compact output experiment (separate run)

[Speed-v6 report](../reports/speed-v6.md), [summary](../reports/speed-v6-summary.json). 56 requests / 157 judgments per arm, interleaved standard/fast, same host, persistent connections and bounded retries. Both got 155/157 correct. P50: 798 vs 750 ms; P95: 1,279 vs 1,175 ms. Output tokens: 6,783 vs 3,625. Total peak cost increased about 4.9% with the new format; its cache-hit fraction was 53.4% vs 85.0%. Cache state was not controlled. Fast mode is experimental and is not the default.

```sh
EVAL_PREFIX=my-new-speed-test python3 scripts/speed_eval.py
```

## Vision smoke test

[Visual fixtures](../examples/images/), [results](../reports/vision-smoke/results.json), [summary](../reports/vision-smoke/summary.json). Two deterministic color-swapped images plus a two-image comparison, tested in standard and fast modes: 6/6 requests, 14/14 judgments, 0.66–0.96 seconds, no retries. Images were embedded as PNG data URLs. Remote URL forwarding is covered by mock tests. This validates the actual image path; it does not establish real-world vision accuracy or superiority over Jev. Native Jev is text-only, so this is not a head-to-head image-quality comparison.

```sh
VISION_EVAL_PREFIX=my-new-vision-test python3 scripts/vision_smoke.py
```

## Historical archive

[Report index](../reports/README.md). Historical files stay at their original paths so scripts and dataset provenance remain usable. Some old scripts overwrite report names; prefer the unique-prefix commands above. Paid evaluation scripts are never run by CI. More difficult reasoning, calibrated probabilities, realistic vision tasks and repeated controlled latency measurements remain future work.
