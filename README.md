# AI English Essay Grading Experiment

This repository contains a full experimental run for comparing OpenAI-compatible AI models on English writing task generation, essay generation, grading stability, and full-score essay optimization.

The source task is in `题目.md`. It contains two Gaokao-style English writing tasks:

- a 15-point practical writing task
- a 25-point continuation writing task

## Models

Four models were tested through OpenAI-compatible APIs:

| Model |
|---|
| `gpt-5.5` |
| `gemini-3.5-flash` |
| `deepseek-v4-pro` |
| `mimo-v2.5-pro` |

API keys are not included in this repository. Runtime configuration reads key names from environment variables only.

## Experiment Design

1. Each model generated one new task set.
2. Each task set contained both a 15-point practical writing task and a 25-point continuation writing task.
3. Each model generated five essays for every task and task type:
   - two high-level essays
   - two medium-level essays
   - one low-level essay
4. Target scores were fixed as follows:
   - practical writing: high 15, medium 10, low 5
   - continuation writing: high 25, medium 17, low 8
5. Each original essay was graded by all four models three times.
6. High-level essays were optimized by all four models.
7. Optimized essays were graded once by the three models that did not produce that optimized version.

## Data Scale

| Item | Count |
|---|---:|
| Generated task sets | 4 |
| Original essays | 160 |
| Regular grading records | 1,920 |
| Optimized essays | 256 |
| Optimized cross-grading records | 768 |

## Key Findings

The grading models tended to over-score medium and low essays, especially for the 25-point continuation writing task. The medium continuation essays had a target score of 17 but were graded at an average of 21.89.

For repeated grading stability, `gemini-3.5-flash` had the lowest average standard deviation, followed by `gpt-5.5`.

For full-score essay optimization, `gpt-5.5` produced the highest average cross-graded score rate among the tested optimizer models.

See `REPORT.md`, `reports/summary.md`, and `reports/report.html` for details.

## Files

| Path | Description |
|---|---|
| `题目.md` | Original writing tasks and grading standards |
| `config/models.json` | Model metadata and environment variable names |
| `config/experiment.json` | Experiment settings |
| `scripts/run_experiment.py` | Experiment runner and analyzer |
| `data/topics.jsonl` | Generated task sets |
| `data/essays.jsonl` | Generated essays |
| `data/grading_runs.jsonl` | Regular grading results |
| `data/optimized_essays.jsonl` | Optimization suggestions and optimized essays |
| `data/optimized_grading_runs.jsonl` | Cross-grading results for optimized essays |
| `reports/summary.md` | Main numeric summary |
| `reports/report.html` | Visual HTML report with inline charts |
| `reports/model_bias.csv` | Per-grader scoring bias |
| `reports/optimizer_scores.csv` | Per-optimizer cross-grading summary |

## Reproduction

Set the required environment variables in Windows or in a local `.env` file:

```env
Yumu-key=
Deepseek-key=
Mimo-key=
```

Then run:

```powershell
py scripts/run_experiment.py --phase smoke
py scripts/run_experiment.py --phase all
```

The script supports phase-by-phase and resumable execution through JSONL output files.
