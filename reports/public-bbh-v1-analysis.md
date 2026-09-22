# Public BBH subset: paired accuracy breakdown

300 fixed questions, 10 selected tasks × 30, zero-shot choice adaptation. This is not the full BBH benchmark or an official Jev evaluation. See [dataset and frozen protocol](../evals/public-bbh/README.md).

| Task | Jev | dsk-jev | Difference (percentage points) |
|---|---:|---:|---:|
| boolean_expressions | 30/30 | 25/30 | -16.7 |
| causal_judgement | 18/30 | 15/30 | -10.0 |
| date_understanding | 26/30 | 20/30 | -20.0 |
| disambiguation_qa | 25/30 | 17/30 | -26.7 |
| logical_deduction_seven_objects | 29/30 | 17/30 | -40.0 |
| logical_deduction_three_objects | 30/30 | 28/30 | -6.7 |
| sports_understanding | 26/30 | 23/30 | -10.0 |
| tracking_shuffled_objects_seven_objects | 30/30 | 2/30 | -93.3 |
| tracking_shuffled_objects_three_objects | 30/30 | 13/30 | -56.7 |
| web_of_lies | 30/30 | 17/30 | -43.3 |

Paired outcomes: both correct 168; only dsk-jev correct 9; only Jev correct 106; both wrong 17.

Exploratory exact two-sided McNemar p=3.693e-22. This paired test conditions on discordant outcomes and treats cases as independent; templated questions within a task may be correlated. It does not establish production superiority, training-data independence or account for selection of tasks. Per-task p-values in JSON are exploratory and unadjusted for multiple comparisons.

[Latency, cost and methodology](public-bbh-v1.md) · [Raw results](public-bbh-v1-results.json) · [Usage summary](public-bbh-v1-summary.json)
