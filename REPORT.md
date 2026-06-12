# AI English Essay Grading Experiment Report

## 1. Purpose

This experiment tested whether four OpenAI-compatible AI models can reliably perform several tasks related to Gaokao-style English writing assessment:

- create new writing tasks and scoring rubrics from an existing reference task
- generate essays at controlled score levels
- grade essays repeatedly and consistently
- improve full-score target essays
- cross-grade optimized essays without self-evaluation by the optimizer

The experiment used the source material in `题目.md`, which contains a 15-point practical writing task and a 25-point continuation writing task.

## 2. Tested Models

| Model ID | Model |
|---|---|
| `yumu_gpt55` | `gpt-5.5` |
| `yumu_gemini35` | `gemini-3.5-flash` |
| `deepseek_v4` | `deepseek-v4-pro` |
| `mimo_v25` | `mimo-v2.5-pro` |

The experiment runner treats each model as a separate worker. At most one request per model is active at the same time.

## 3. Experimental Procedure

Each model first generated one new task set. Each generated set contains:

- one 15-point practical writing task
- one 25-point continuation writing task
- scoring rubrics for both task types

For every generated task set and every task type, each model generated five essays:

- two high-level essays
- two medium-level essays
- one low-level essay

The target scores were:

| Task Type | High | Medium | Low |
|---|---:|---:|---:|
| Practical writing | 15 | 10 | 5 |
| Continuation writing | 25 | 17 | 8 |

Each original essay was then graded by all four models three times. High-level essays were optimized by all four models. Each optimized essay was graded once by the three non-optimizer models.

## 4. Data Scale

| Dataset | Count |
|---|---:|
| Generated task sets | 4 |
| Original essays | 160 |
| Regular grading records | 1,920 |
| Optimized essays | 256 |
| Optimized cross-grading records | 768 |

All records are stored as JSONL files in `data/`.

## 5. Regular Grading Accuracy

| Grading Model | Samples | Mean Absolute Error | Mean Bias |
|---|---:|---:|---:|
| `deepseek_v4` | 480 | 2.75 | 2.33 |
| `mimo_v25` | 480 | 2.53 | 1.30 |
| `yumu_gemini35` | 480 | 2.52 | 1.98 |
| `yumu_gpt55` | 480 | 2.90 | 2.04 |

All four graders showed positive mean bias, meaning they tended to assign scores above the target scores used during essay generation. `mimo_v25` had the lowest mean bias, while `yumu_gemini35` had the lowest mean absolute error by a small margin.

## 6. Repeated Grading Stability

| Grading Model | Essay Groups | Average Standard Deviation |
|---|---:|---:|
| `deepseek_v4` | 160 | 0.47 |
| `mimo_v25` | 160 | 0.57 |
| `yumu_gemini35` | 160 | 0.19 |
| `yumu_gpt55` | 160 | 0.24 |

`yumu_gemini35` and `yumu_gpt55` were the most stable across three repeated grading runs. This does not necessarily mean they were the most accurate, but their repeated scores varied less.

## 7. Task-Type and Level Effects

| Task Type | Level | Samples | Mean Target | Mean Score | Mean Bias |
|---|---|---:|---:|---:|---:|
| continuation_25 | high | 384 | 25.00 | 23.66 | -1.34 |
| continuation_25 | low | 192 | 8.00 | 11.84 | 3.84 |
| continuation_25 | medium | 384 | 17.00 | 21.89 | 4.89 |
| practical_15 | high | 384 | 15.00 | 14.64 | -0.36 |
| practical_15 | low | 192 | 5.00 | 6.87 | 1.87 |
| practical_15 | medium | 384 | 10.00 | 13.52 | 3.52 |

The largest issue is score compression toward the upper range. Medium and low essays were often graded too highly. This was especially visible for continuation writing, where medium essays targeted at 17 points received an average score of 21.89.

High-level essays were slightly under-scored on average. This suggests that the graders were conservative near full score but generous with weaker essays.

## 8. Full-Score Essay Optimization

| Optimizer Model | Cross-Grading Records | Mean Score | Mean Full Score | Score Rate |
|---|---:|---:|---:|---:|
| `deepseek_v4` | 192 | 19.09 | 20.00 | 0.955 |
| `mimo_v25` | 192 | 19.15 | 20.00 | 0.957 |
| `yumu_gemini35` | 192 | 19.20 | 20.00 | 0.960 |
| `yumu_gpt55` | 192 | 19.35 | 20.00 | 0.967 |

The optimizer comparison combines 15-point and 25-point tasks, so the mean full score is 20.00. `yumu_gpt55` produced the highest average optimized essay score rate under non-self cross-grading.

## 9. Operational Notes

The experiment was run with resumable JSONL outputs. One long regular-grading run reached the execution timeout after 1,890 records; the runner was resumed and completed the remaining records. One optimization response contained non-strict JSON string formatting; the parser was improved to support non-strict JSON parsing and partial JSON recovery, then the missing record was rerun.

No API key values are stored in this repository. API key names are kept in configuration, while values are read from local environment variables at runtime.

## 10. Conclusion

The experiment suggests that these models can follow essay grading rubrics and produce stable scores, but they are not well calibrated across score levels. Their most important weakness is over-scoring medium and low-quality essays, especially in continuation writing.

For practical use, AI grading should be calibrated with human-scored anchor essays. A future experiment should add human reference scores, item-level rubric labels, and pairwise ranking tasks to separate grading consistency from grading correctness.
