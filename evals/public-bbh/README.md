# Public BBH subset v1

400 original questions from [Suzgun et al., BIG-Bench Hard](https://github.com/suzgunmirac/BIG-Bench-Hard), pinned to commit `9ee07bd481feebf959a6b59d61ea57bdcf30964d`. See [paper](https://arxiv.org/abs/2210.09261), [manifest](manifest.json) and upstream [MIT license](LICENSE). Preserve the dataset's canary notice in the manifest: benchmark data must not be used for training.

This is an author-published benchmark source, **not an official Jev benchmark or a full BBH leaderboard evaluation**. Ten tasks were chosen before observing results to examine reasoning and include semantic comparison tasks. The selection is deliberately diagnostic, not representative of production traffic or all intelligence.

- Logic: Boolean expressions, 3-/7-object logical deduction, truth/lie chains.
- State tracking: 3-/7-object shuffled objects.
- Dates: date understanding.
- Semantic comparison: causal judgment, pronoun disambiguation, sports plausibility.

Each task contributes 30 test and 10 development questions. Rank original row indices by SHA256 of `seed/task/index`; take the first 30 for test and next 10 for dev. Interleave tasks using a separate hash order. Sampling does not depend on answers, model outputs or difficulty within tasks. Rebuild with `python3 scripts/build_public_cases.py`; network access is required, but no API keys. The manifest records source-file hashes and resulting split hashes. Do not silently replace v1 cases when adding future suites.

## Protocol frozen before the first run

`test.json` is the first-run evaluation set; `dev.json` is reserved for subsequent prompt/code development and is not called in the first run. Neither split had previously been used by this project. Both are public data, however: exposure in model training is unknown. Once results are inspected, test v1 is a regression set, not a new blind holdout.

One question per request. Original English text and option order are preserved in `state`; original options are also mapped into choice criteria. Binary tasks retain original answer capitalization. The same neutral instruction, request payload and choice grading are used for both providers. Gold labels and source metadata stay outside the submitted `request`. No few-shot examples, chain-of-thought prompt, answer judge or generated distractors. Causal judgments follow the source's human-judgment labels, which need not be universal logical truths.

Jev is pinned to `jev-1.13.0`; dsk-jev uses `deepseek-flash`, thinking disabled, standard prompt and standard output, max 3 retries. The paired runner alternates provider order, uses persistent connections, concurrency one and a 30-second upstream budget. Cache is not flushed. The DeepSeek backend model name is a provider alias rather than an immutable weight snapshot.

Accuracy includes failed requests as wrong. Report per-task accuracy and the pooled score (equal-sized tasks); separately report successful requests, all-attempt token/cost estimates, latency, cache usage and paired disagreements. Price scenarios come from the existing repository snapshot and are estimates, not billed balances. No optimization or resampling is performed based on test-v1 results during this run.

```sh
# Export DEEPSEEK_API_KEY and JEV_API_KEY securely first.
go build -o bin/dsk-jev ./cmd/server
EVAL_CASES=evals/public-bbh/test.json \
EVAL_PREFIX=public-bbh-your-unique-run \
EVAL_DATASET_DESCRIPTION='Frozen public BBH diagnostic subset v1; zero-shot choice adaptation; not full BBH' \
python3 scripts/compare_eval.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Future coverage should add author-published general knowledge/science and intent classification datasets; these English text-only tasks do not measure image input, multilingual quality, calibration or tool use. Retain the original Jev-style routing regression alongside this suite.
