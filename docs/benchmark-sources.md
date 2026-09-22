# Benchmark sources and selection

Reviewed 2026-09-22. “Official” below means the provider's own documentation or the dataset authors' release, not a third-party Jev comparison.

## What Jev itself says

[TypeSafe's Jev 1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13), reviewed by the provider on September 17, lists numeric precision, date comparisons and multi-hop indirection among known weaknesses. It also describes common-sense judgment as a strength. This motivates testing specific capabilities; it does not establish that another model is better. The [official reranking cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe) is a narrow retrieval example, not a general intelligence leaderboard.

## Author-published evaluation suites

| Source | Purpose | Status here |
|---|---|---|
| [BIG-Bench Hard / Suzgun et al.](https://github.com/suzgunmirac/BIG-Bench-Hard), [paper](https://arxiv.org/abs/2210.09261) | Multi-step reasoning plus language/semantic tasks | Imported 400 original questions across 10 selected tasks: 300 test, 100 dev; immutable upstream commit, source hashes and MIT notice recorded |
| [AI2 ARC / Allen Institute for AI](https://huggingface.co/datasets/allenai/ai2_arc) | Science questions with original multiple-choice answers; complementary knowledge coverage | Candidate for a separate next suite; not included in current scores |
| [BIG-Bench Extra Hard / Google DeepMind](https://github.com/google-deepmind/bbeh) | More demanding reasoning; many tasks require free-form answers | Candidate for future stress tests; do not invent distractors merely to force compatibility with a choice API |

See [BBH adaptation protocol](../evals/public-bbh/README.md). The first public suite is a diagnostic sample, not a comprehensive balanced estimate of all user workloads. Include every sampled question and every failure, and report task-level results so easy and hard tasks cannot hide one another. Preserve the earlier routing/intent regression, which measures a different workload.

## How this should drive optimization

1. Freeze the 300-question baseline and evaluate both systems without prompt tuning.
2. Diagnose errors using the separate 100-question development split. Compare prompt/representation changes against unchanged defaults; record speed, cost, format failures and correctness together.
3. If considering an opt-in reasoning mode, benchmark it separately. Forced tool use and reasoning compatibility must be verified; do not silently change the low-latency default or claim that enabled reasoning costs nothing.
4. Evaluate any selected change on a newly frozen independent sample before making a fresh superiority claim. The inspected v1 test set becomes regression data.

Public benchmarks may be present in model training data. We do not know either provider's exposure. Small English text-only subsets do not measure multilingual robustness, image understanding, probability calibration or real production task frequencies. A diagnostic result cannot support an unqualified “smarter than Jev” claim.
