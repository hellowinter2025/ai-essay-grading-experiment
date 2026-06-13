# AI英语作文评分实验

本仓库保存了一次完整的 AI 英语作文评分能力测试，内容包括命题、分档作文生成、重复批改、满分作文优化，以及优化版本的非本人互评。

原始参考题目位于 `题目.md`，包含两类高考英语写作任务：

- 15分应用文
- 25分读后续写

## 测试模型

本实验通过 OpenAI-compatible API 测试了四个模型：

| 模型 |
|---|
| `gpt-5.5` |
| `gemini-3.5-flash` |
| `deepseek-v4-pro` |
| `mimo-v2.5-pro` |

仓库中不包含任何 API 密钥。运行脚本只从本地环境变量读取密钥值。

## 实验流程

1. 四个模型各自基于原始题目重新命制一套题。
2. 每套题都包含一道15分应用文和一道25分读后续写。
3. 四个模型分别为每套题、每种题型生成五篇作文：
   - 两篇上等作文
   - 两篇中等作文
   - 一篇下等作文
4. 预设目标分如下：
   - 15分应用文：上等15分，中等10分，下等5分
   - 25分读后续写：上等25分，中等17分，下等8分
5. 所有原始作文由四个模型分别批改三次。
6. 所有上等作文再由四个模型分别给出优化建议和优化版本。
7. 每篇优化作文由非本人优化者的三个模型各批改一次。

## 数据规模

| 项目 | 数量 |
|---|---:|
| 新命制题目套数 | 4 |
| 原始生成作文 | 160 |
| 常规批改记录 | 1,920 |
| 优化作文版本 | 256 |
| 优化后互评记录 | 768 |

## 主要发现

四个模型整体都存在高估中低档作文的倾向，尤其是25分读后续写。目标为17分的读后续写中等作文，平均被评为21.89分。

三轮重复评分稳定性方面，`gemini-3.5-flash` 的平均标准差最低，其次是 `gpt-5.5`。

满分作文优化互评中，`gpt-5.5` 生成的优化版本平均得分率最高。

详细内容见：

- `REPORT.md`
- `reports/summary.md`
- `reports/report.html`

## 文件说明

| 路径 | 说明 |
|---|---|
| `题目.md` | 原始作文题目与评分标准 |
| `config/models.json` | 模型配置和环境变量名 |
| `config/experiment.json` | 实验参数 |
| `scripts/run_experiment.py` | 实验运行与统计脚本 |
| `scripts/build_html_report.py` | HTML可视化报告生成脚本 |
| `data/topics.jsonl` | 四个模型重新命制的题目 |
| `data/essays.jsonl` | 生成作文 |
| `data/grading_runs.jsonl` | 常规批改结果 |
| `data/optimized_essays.jsonl` | 优化建议与优化作文 |
| `data/optimized_grading_runs.jsonl` | 优化作文互评结果 |
| `reports/summary.md` | 主要数字摘要 |
| `reports/report.html` | 带统计图的HTML报告 |
| `reports/model_bias.csv` | 各评分模型误差统计 |
| `reports/optimizer_scores.csv` | 各优化模型互评得分统计 |

## 复现实验

在 Windows 环境变量或本地 `.env` 文件中设置：

```env
Yumu-key=
Deepseek-key=
Mimo-key=
```

然后运行：

```powershell
py scripts/run_experiment.py --phase smoke
py scripts/run_experiment.py --phase all
py scripts/build_html_report.py
```

脚本支持按阶段运行和基于 JSONL 文件的断点续跑。
