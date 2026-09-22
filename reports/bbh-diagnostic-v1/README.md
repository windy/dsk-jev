# BBH development diagnosis: reasoning and output constraints

2026-09-22. Diagnostic experiments, not a new Jev comparison or a production release. Current product defaults remain thinking-disabled. Source: the frozen [BBH development split](../../evals/public-bbh/README.md).

## Findings

The captured Go requests preserve all 40 source questions and every option exactly. No mapping or question-transfer defect was found. A generic prompt alone did not recover accuracy. Low thinking substantially improved this development sample, at additional latency and cost. Relaxing tool selection and output budget without enabling thinking did not reproduce the gain. This supports reasoning configuration as an important bottleneck, rather than a conclusion that DeepSeek cannot solve these tasks. It does not isolate all model-internal causes.

## First phase: 40 questions, five arms

First four questions per task in the pre-existing development-file hash order; 10 tasks, one run each. Arms rotated per case, persistent HTTPS, concurrency one, no retries, 60-second timeout. Baseline payloads were captured from the real Go proxy against a local fake upstream, then replayed directly to DeepSeek. All arms therefore measure upstream latency, not full proxy latency. Original labels stay outside provider requests. No Jev calls were made in this experiment.

| Configuration | Correct / 40 | Valid / 40 | P50 ms | P95 ms | Estimated peak USD, whole arm |
|---|---:|---:|---:|---:|---:|
| Current proxy payload, thinking off | 24 | 40 | 888 | 1228 | 0.007757 |
| Neutral prompt + forced probability tool, thinking off | 21 | 40 | 878 | 1110 | 0.008417 |
| Label only, thinking off, 128-token cap | 18 | 37 | 715 | 1142 | 0.002224 |
| Label only, low thinking, 8192-token cap | 37 | 40 | 1325 | 4482 | 0.014800 |
| Neutral prompt + probability tool, low thinking, auto tool | 37 | 39 | 1601 | 13599 | 0.044215 |

The full-probability low-thinking arm costs about 5.7× the baseline in this run. The faster label-only arm does not supply the Jev probability/confidence contract, so it is a diagnostic, not a drop-in replacement. These are snapshot price estimates, not actual debits; cache state was not controlled. Reasoning tokens are included in completion usage. Offpeak estimates and all usage are in summary.json.

One low-thinking probability response consumed all 8,192 completion tokens and stopped without an answer after 42.30 seconds. It counts as wrong and invalid. This exceeds the product default 30-second budget. Therefore the 37/40 diagnostic result must not be presented as a production result under the current timeout. Three short direct-off responses were invalid (including truncation or extra explanation); these also count as wrong.

### Task counts

| Task (four questions each) | Baseline | Neutral prompt, off | Label, low | Probability tool, low |
|---|---:|---:|---:|---:|
| boolean_expressions | 4 | 3 | 4 | 4 |
| causal_judgement | 2 | 1 | 3 | 2 |
| date_understanding | 2 | 3 | 4 | 4 |
| disambiguation_qa | 3 | 4 | 2 | 3 |
| logical_deduction_seven_objects | 2 | 1 | 4 | 4 |
| logical_deduction_three_objects | 4 | 4 | 4 | 4 |
| sports_understanding | 3 | 3 | 4 | 4 |
| tracking_shuffled_objects_seven_objects | 0 | 0 | 4 | 4 |
| tracking_shuffled_objects_three_objects | 2 | 1 | 4 | 4 |
| web_of_lies | 2 | 1 | 4 | 4 |

## Follow-up controls: 20 overlapping development questions

The first two questions per task in the same frozen order. This subset was selected by position, not by correctness. These are overlapping cases, not 20 additional independent questions. Controls ran afterward, so their latency/cache measurements are a separate phase.

| Configuration | Correct / 20 | Valid / 20 | P50 ms | P95 ms |
|---|---:|---:|---:|---:|
| Neutral prompt + auto probability tool, thinking off, 8192 cap | 13 | 20 | 897 | 2123 |
| Label only, thinking off, 8192 cap | 11 | 18 | 681 | 1495 |
| Original proxy prompt + probability tool, low thinking, auto tool | 17 | 18 | 1296 | 3966 |

For the same 20 IDs in the first phase:
- Current proxy payload, thinking off: 13/20 correct.
- Neutral prompt + forced probability tool, thinking off: 11/20 correct.
- Label only, thinking off, 128-token cap: 8/20 correct.
- Label only, low thinking, 8192-token cap: 18/20 correct.
- Neutral prompt + probability tool, low thinking, auto tool: 18/20 correct.

The original-prompt low-thinking arm returned ordinary text containing a complete probability JSON object twice instead of calling the tool. Current production parsing correctly rejects these under its forced-tool contract. An offline candidate fallback using the same option/range/sum validation accepts both JSON objects, but only one answer is correct: validity would become 20/20 and correctness 18/20, not 20/20. This is a secondary reparse, not a fresh model run or an implemented product feature. One of those responses took 31.49 seconds, again exceeding the product default budget.

## Practical recovery path

1. Keep fast/default and quality configurations distinct. These results do not justify promising fast-mode latency together with reasoning-mode accuracy.
2. A quality configuration can preserve the probability schema while enabling low thinking. DeepSeek requires auto tool selection with thinking; a named/required tool is unsupported. Use a clear tool-call instruction, and consider a strictly validated JSON-text fallback only for that configuration. Do not synthesize a one-hot probability distribution from a bare answer.
3. Define a reasoning token budget and end-to-end deadline, then test their effect. A larger budget alone did not solve the task; reasoning can still run long or produce no final answer. Repeating a valid but incorrect distribution is not a reliable reasoning strategy.
4. Evaluate any implementation on the remaining 60 development cases and a newly frozen evaluation sample; include latency tails, all attempts, output failures, cache and cost. The inspected 40 cases are development evidence, not a blind claim of superiority.

No production prompt or inference behavior was changed in this diagnostic. Public BBH training exposure is unknown. Four examples per task and single stochastic runs are too small for precise task-level claims. The earlier 300-question Jev result must not be compared numerically to this different 40-question sample.

## Reproduce (paid)

Build `bin/dsk-jev` and securely export `DEEPSEEK_API_KEY` first. Use new output-directory names:

```sh
DIAG_PREFIX=my-diagnostic python3 scripts/diagnose_bbh.py
DIAG_PREFIX=my-controls DIAG_PER_TASK=2 \
  DIAG_ARMS=neutral_tool_auto_off,direct_off_long,baseline_tool_low \
  python3 scripts/diagnose_bbh.py
```

[First-phase manifest](manifest.json) · [Captured actual payloads](baseline-payloads.json) · [Results](results.jsonl) · [Summary](summary.json) · [Control results](../bbh-diagnostic-controls-v1/results.jsonl) · [Control summary](../bbh-diagnostic-controls-v1/summary.json)

[DeepSeek thinking parameters](https://api-docs.deepseek.com/guides/thinking_mode/) · [Tool-choice constraints](https://api-docs.deepseek.com/api/create-chat-completion/)
