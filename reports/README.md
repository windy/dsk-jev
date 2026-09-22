# Historical evaluation archive

Start with [the consolidated benchmark report](../docs/benchmarks.md). These files are retained as evidence, not independent claims that every experimental variant is better.

- `comparison-v4*`: paired Jev/default DeepSeek comparison, retry/cache/cost accounting.
- `speed-v5*`, `speed-v6*`: upstream output compression experiments, including unsuccessful variants.
- `vision-smoke/`: synthetic live image-path smoke test.
- `v3*`, `cache-*`: retry and continuous-prefix-cache experiments.
- `v2*`, `live-*`, `jev-*`: earlier protocol and baseline evaluations.

Original paths are preserved for reproducibility. Logs and fixture answers are synthetic development data. Do not commit production logs, private inputs or credentials here. Results from different timing windows must not be mixed into a purported paired comparison.

## Public benchmark evaluation

[BBH subset v1 protocol](../evals/public-bbh/README.md): 300 paired evaluation questions plus 100 reserved development questions, from author-published sources. Kept separate from the historical synthetic regression reports.
