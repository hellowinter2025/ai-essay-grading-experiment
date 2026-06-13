import html
import json
import math
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


MODEL_NAMES = {
    "yumu_gpt55": "gpt-5.5",
    "yumu_gemini35": "gemini-3.5-flash",
    "deepseek_v4": "deepseek-v4-pro",
    "mimo_v25": "mimo-v2.5-pro",
}

COLORS = {
    "gpt-5.5": "#2563eb",
    "gemini-3.5-flash": "#7c3aed",
    "deepseek-v4-pro": "#059669",
    "mimo-v2.5-pro": "#dc2626",
    "target": "#64748b",
    "score": "#f59e0b",
}

TASK_LABELS = {
    "practical_15": "15分应用文",
    "continuation_25": "25分读后续写",
}

LEVEL_LABELS = {
    "high": "上等",
    "medium": "中等",
    "low": "下等",
}

TASK_ORDER = ["practical_15", "continuation_25"]
LEVEL_ORDER = ["high", "medium", "low"]


def read_jsonl(name):
    path = DATA / f"{name}.jsonl"
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def model_name(model_id):
    return MODEL_NAMES.get(model_id, model_id)


def esc(value):
    return html.escape(str(value), quote=True)


def fmt(value, digits=2):
    return f"{value:.{digits}f}"


def mean(values):
    return sum(values) / len(values) if values else 0


def stdev(values):
    if not values:
        return 0
    avg = mean(values)
    return math.sqrt(sum((v - avg) ** 2 for v in values) / len(values))


def bar_chart(title, subtitle, rows, value_keys, labels, colors, width=920, height=360):
    margin = {"top": 54, "right": 26, "bottom": 74, "left": 58}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    max_value = max([0.1] + [abs(row[key]) for row in rows for key in value_keys])
    if any(row[key] < 0 for row in rows for key in value_keys):
        max_abs = max_value
        y_zero = margin["top"] + plot_h / 2
        scale = (plot_h / 2 - 10) / max_abs
        y_for = lambda value: y_zero - value * scale
        h_for = lambda value: abs(value) * scale
    else:
        y_zero = margin["top"] + plot_h
        scale = plot_h / max_value
        y_for = lambda value: y_zero - value * scale
        h_for = lambda value: value * scale
    group_w = plot_w / max(1, len(rows))
    bar_w = min(34, group_w / (len(value_keys) + 1))
    parts = svg_shell(width, height, title, subtitle)
    parts.append(f'<line x1="{margin["left"]}" y1="{y_zero:.1f}" x2="{width - margin["right"]}" y2="{y_zero:.1f}" class="axis"/>')
    for i, row in enumerate(rows):
        center = margin["left"] + group_w * i + group_w / 2
        start = center - (bar_w * len(value_keys)) / 2
        for j, key in enumerate(value_keys):
            value = row[key]
            x = start + j * bar_w
            y = min(y_for(value), y_zero)
            h = max(1, h_for(value))
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 4:.1f}" height="{h:.1f}" rx="4" fill="{colors[j]}"/>')
            parts.append(f'<text x="{x + (bar_w - 4) / 2:.1f}" y="{y - 7:.1f}" class="value" text-anchor="middle">{fmt(value)}</text>')
        parts.append(f'<text x="{center:.1f}" y="{height - 40}" class="xlab" text-anchor="middle">{esc(row["label"])}</text>')
    legend_x = margin["left"]
    for i, label in enumerate(labels):
        x = legend_x + i * 170
        parts.append(f'<rect x="{x}" y="{height - 24}" width="12" height="12" rx="2" fill="{colors[i]}"/>')
        parts.append(f'<text x="{x + 18}" y="{height - 14}" class="legend">{esc(label)}</text>')
    return "".join(parts) + "</svg>"


def horizontal_bar_chart(title, subtitle, rows, value_key, color_key=None, width=920, height=350):
    margin = {"top": 56, "right": 38, "bottom": 28, "left": 180}
    row_h = (height - margin["top"] - margin["bottom"]) / max(1, len(rows))
    max_value = max([0.1] + [row[value_key] for row in rows])
    parts = svg_shell(width, height, title, subtitle)
    for i, row in enumerate(rows):
        y = margin["top"] + i * row_h + 9
        bar_h = min(26, row_h - 12)
        w = (width - margin["left"] - margin["right"]) * row[value_key] / max_value
        color = row.get(color_key, "#2563eb") if color_key else "#2563eb"
        parts.append(f'<text x="{margin["left"] - 12}" y="{y + bar_h * .68:.1f}" class="ylab" text-anchor="end">{esc(row["label"])}</text>')
        parts.append(f'<rect x="{margin["left"]}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="5" fill="{color}"/>')
        parts.append(f'<text x="{margin["left"] + w + 8:.1f}" y="{y + bar_h * .68:.1f}" class="value">{fmt(row[value_key], 3)}</text>')
    return "".join(parts) + "</svg>"


def heatmap(title, subtitle, rows, width=920, height=320):
    tasks = ["practical_15", "continuation_25"]
    levels = ["high", "medium", "low"]
    data = {(r["task"], r["level"]): r["bias"] for r in rows}
    margin = {"top": 66, "right": 34, "bottom": 42, "left": 170}
    cell_w = (width - margin["left"] - margin["right"]) / len(levels)
    cell_h = (height - margin["top"] - margin["bottom"]) / len(tasks)
    max_abs = max([0.1] + [abs(v) for v in data.values()])
    parts = svg_shell(width, height, title, subtitle)
    for r, task in enumerate(tasks):
        y = margin["top"] + r * cell_h
        parts.append(f'<text x="{margin["left"] - 14}" y="{y + cell_h / 2 + 5:.1f}" class="ylab" text-anchor="end">{esc(TASK_LABELS.get(task, task))}</text>')
        for c, level in enumerate(levels):
            value = data.get((task, level), 0)
            x = margin["left"] + c * cell_w
            color = heat_color(value, max_abs)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w - 8:.1f}" height="{cell_h - 8:.1f}" rx="8" fill="{color}"/>')
            parts.append(f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 5:.1f}" class="heatvalue" text-anchor="middle">{fmt(value)}</text>')
    for c, level in enumerate(levels):
        x = margin["left"] + c * cell_w + cell_w / 2
        parts.append(f'<text x="{x:.1f}" y="{height - 18}" class="xlab" text-anchor="middle">{esc(LEVEL_LABELS.get(level, level))}</text>')
    return "".join(parts) + "</svg>"


def heat_color(value, max_abs):
    ratio = min(1, abs(value) / max_abs)
    if value >= 0:
        r, g, b = 220, 38, 38
    else:
        r, g, b = 37, 99, 235
    base = 248
    mix = 0.18 + ratio * 0.72
    rr = int(base * (1 - mix) + r * mix)
    gg = int(base * (1 - mix) + g * mix)
    bb = int(base * (1 - mix) + b * mix)
    return f"rgb({rr},{gg},{bb})"


def scatter_chart(title, subtitle, points, width=920, height=390):
    margin = {"top": 58, "right": 34, "bottom": 54, "left": 60}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    max_score = 25
    parts = svg_shell(width, height, title, subtitle)
    parts.append(f'<rect x="{margin["left"]}" y="{margin["top"]}" width="{plot_w}" height="{plot_h}" rx="10" fill="#f8fafc" stroke="#dbe3ef"/>')
    for tick in [5, 10, 15, 20, 25]:
        x = margin["left"] + plot_w * tick / max_score
        y = margin["top"] + plot_h - plot_h * tick / max_score
        parts.append(f'<line x1="{x:.1f}" y1="{margin["top"]}" x2="{x:.1f}" y2="{margin["top"] + plot_h}" class="grid"/>')
        parts.append(f'<line x1="{margin["left"]}" y1="{y:.1f}" x2="{margin["left"] + plot_w}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 24}" class="tick" text-anchor="middle">{tick}</text>')
        parts.append(f'<text x="{margin["left"] - 10}" y="{y + 4:.1f}" class="tick" text-anchor="end">{tick}</text>')
    parts.append(f'<line x1="{margin["left"]}" y1="{margin["top"] + plot_h}" x2="{margin["left"] + plot_w}" y2="{margin["top"]}" stroke="#0f172a" stroke-width="1.4" stroke-dasharray="5 5"/>')
    for point in points:
        x = margin["left"] + plot_w * point["target"] / max_score
        y = margin["top"] + plot_h - plot_h * point["score"] / max_score
        color = COLORS.get(point["model"], "#2563eb")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" opacity="0.72"><title>{esc(point["model"])} 目标分 {fmt(point["target"])} 平均分 {fmt(point["score"])}</title></circle>')
    parts.append(f'<text x="{margin["left"] + plot_w / 2}" y="{height - 4}" class="axislabel" text-anchor="middle">目标分</text>')
    parts.append(f'<text x="18" y="{margin["top"] + plot_h / 2}" class="axislabel" transform="rotate(-90 18 {margin["top"] + plot_h / 2})" text-anchor="middle">AI平均评分</text>')
    return "".join(parts) + "</svg>"


def distribution_chart(title, subtitle, rows, width=920, height=360):
    margin = {"top": 56, "right": 30, "bottom": 62, "left": 56}
    bins = list(range(0, 27, 2))
    counts = defaultdict(int)
    for row in rows:
        score = max(0, min(25, int(row["score"] // 2 * 2)))
        counts[score] += 1
    max_count = max([1] + list(counts.values()))
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    bar_w = plot_w / len(bins)
    parts = svg_shell(width, height, title, subtitle)
    for i, bin_start in enumerate(bins):
        count = counts[bin_start]
        x = margin["left"] + i * bar_w + 2
        h = plot_h * count / max_count
        y = margin["top"] + plot_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 5:.1f}" height="{h:.1f}" rx="4" fill="#0ea5e9"/>')
        if count:
            parts.append(f'<text x="{x + (bar_w - 5) / 2:.1f}" y="{y - 6:.1f}" class="value" text-anchor="middle">{count}</text>')
        parts.append(f'<text x="{x + (bar_w - 5) / 2:.1f}" y="{height - 32}" class="tick" text-anchor="middle">{bin_start}</text>')
    parts.append(f'<text x="{margin["left"] + plot_w / 2}" y="{height - 8}" class="axislabel" text-anchor="middle">分数区间</text>')
    return "".join(parts) + "</svg>"


def paired_bar_chart(title, subtitle, rows, width=920, height=560):
    margin = {"top": 70, "right": 78, "bottom": 42, "left": 172}
    plot_w = width - margin["left"] - margin["right"]
    max_value = max([0.1] + [row["before"] for row in rows] + [row["after"] for row in rows])
    scale = plot_w / max_value
    grouped = {task: [row for row in rows if row["task"] == task] for task in TASK_ORDER}
    row_h = 42
    gap = 38
    y = margin["top"]
    parts = svg_shell(width, height, title, subtitle)
    for task in TASK_ORDER:
        task_rows = grouped.get(task, [])
        if not task_rows:
            continue
        parts.append(f'<text x="24" y="{y + 2}" class="chart-subtitle">{TASK_LABELS[task]}</text>')
        y += 14
        for row in task_rows:
            label_y = y + 23
            parts.append(f'<text x="{margin["left"] - 14}" y="{label_y}" class="ylab" text-anchor="end">{esc(row["model"])}</text>')
            before_w = row["before"] * scale
            after_w = row["after"] * scale
            parts.append(f'<rect x="{margin["left"]}" y="{y + 3}" width="{before_w:.1f}" height="14" rx="4" fill="#94a3b8"/>')
            parts.append(f'<rect x="{margin["left"]}" y="{y + 22}" width="{after_w:.1f}" height="14" rx="4" fill="#2563eb"/>')
            parts.append(f'<text x="{margin["left"] + before_w + 7:.1f}" y="{y + 15}" class="value">{fmt(row["before"])}</text>')
            parts.append(f'<text x="{margin["left"] + after_w + 7:.1f}" y="{y + 34}" class="value">{fmt(row["after"])} / 提升 {fmt(row["gain"])}</text>')
            y += row_h
        y += gap
    legend_y = height - 22
    parts.append(f'<rect x="{margin["left"]}" y="{legend_y}" width="12" height="12" rx="2" fill="#94a3b8"/>')
    parts.append(f'<text x="{margin["left"] + 18}" y="{legend_y + 10}" class="legend">优化前</text>')
    parts.append(f'<rect x="{margin["left"] + 110}" y="{legend_y}" width="12" height="12" rx="2" fill="#2563eb"/>')
    parts.append(f'<text x="{margin["left"] + 128}" y="{legend_y + 10}" class="legend">优化后</text>')
    return "".join(parts) + "</svg>"


def svg_shell(width, height, title, subtitle):
    return [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<text x="24" y="30" class="chart-title">{esc(title)}</text>',
        f'<text x="24" y="50" class="chart-subtitle">{esc(subtitle)}</text>',
    ]


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    topics = read_jsonl("topics")
    essays = read_jsonl("essays")
    grades = read_jsonl("grading_runs")
    optimized = read_jsonl("optimized_essays")
    opt_grades = read_jsonl("optimized_grading_runs")

    essay_by_id = {row["essay_id"]: row for row in essays}
    opt_by_id = {row["optimized_essay_id"]: row for row in optimized}

    by_model = defaultdict(lambda: {"n": 0, "abs": 0.0, "bias": 0.0})
    by_model_type = defaultdict(list)
    by_type_level = defaultdict(lambda: {"n": 0, "target": 0.0, "score": 0.0})
    repeated = defaultdict(list)
    scatter_points = []
    distribution_rows = []
    source_scores = defaultdict(list)

    for grade in grades:
        score = number(grade.get("score"))
        essay = essay_by_id.get(grade["essay_id"])
        if score is None or not essay:
            continue
        name = model_name(grade["grader_ai"])
        source_scores[(grade["essay_id"], name)].append(score)
        target = float(essay["target_score"])
        by_model[name]["n"] += 1
        by_model[name]["abs"] += abs(score - target)
        by_model[name]["bias"] += score - target
        by_model_type[(name, essay["essay_type"])].append(score - target)
        by_type_level[(essay["essay_type"], essay["essay_level"])]["n"] += 1
        by_type_level[(essay["essay_type"], essay["essay_level"])]["target"] += target
        by_type_level[(essay["essay_type"], essay["essay_level"])]["score"] += score
        repeated[(name, grade["essay_id"])].append(score)
        distribution_rows.append({"score": score})

    for (name, essay_id), values in repeated.items():
        essay = essay_by_id[essay_id]
        scatter_points.append({"model": name, "target": float(essay["target_score"]), "score": mean(values)})

    stability = defaultdict(list)
    for (name, _essay_id), values in repeated.items():
        if len(values) >= 2:
            stability[name].append(stdev(values))

    panel_mean = defaultdict(list)
    for (_name, essay_id), values in repeated.items():
        panel_mean[essay_id].append(mean(values))
    panel_mean = {essay_id: mean(values) for essay_id, values in panel_mean.items()}

    level_detail_rows = []
    regular_detail_rows = []
    for name in sorted({key[0] for key in repeated}):
        for level in LEVEL_ORDER:
            vals = []
            biases = []
            repeat_stds = []
            agreement_devs = []
            fulls = []
            for (model, essay_id), scores in repeated.items():
                if model != name:
                    continue
                essay = essay_by_id[essay_id]
                if essay["essay_level"] != level:
                    continue
                avg_score = mean(scores)
                vals.append(avg_score)
                biases.append(avg_score - float(essay["target_score"]))
                repeat_stds.append(stdev(scores))
                agreement_devs.append(abs(avg_score - panel_mean[essay_id]))
                fulls.append(float(essay["full_score"]))
            if vals:
                full = mean(fulls)
                level_detail_rows.append({
                    "模型": name,
                    "档位": LEVEL_LABELS[level],
                    "样本数": len(vals),
                    "平均评分": fmt(mean(vals)),
                    "平均偏差": fmt(mean(biases)),
                    "三轮标准差": fmt(mean(repeat_stds)),
                    "稳定性分": fmt(max(0, 100 * (1 - mean(repeat_stds) / full)), 1),
                    "一致偏离": fmt(mean(agreement_devs)),
                    "一致性分": fmt(max(0, 100 * (1 - mean(agreement_devs) / full)), 1),
                })
        for task in TASK_ORDER:
            for level in LEVEL_ORDER:
                vals = []
                abs_errors = []
                biases = []
                repeat_stds = []
                agreement_devs = []
                fulls = []
                targets = []
                for (model, essay_id), scores in repeated.items():
                    if model != name:
                        continue
                    essay = essay_by_id[essay_id]
                    if essay["essay_type"] != task or essay["essay_level"] != level:
                        continue
                    avg_score = mean(scores)
                    target = float(essay["target_score"])
                    vals.append(avg_score)
                    targets.append(target)
                    abs_errors.append(abs(avg_score - target))
                    biases.append(avg_score - target)
                    repeat_stds.append(stdev(scores))
                    agreement_devs.append(abs(avg_score - panel_mean[essay_id]))
                    fulls.append(float(essay["full_score"]))
                if vals:
                    full = mean(fulls)
                    regular_detail_rows.append({
                        "模型": name,
                        "题型": TASK_LABELS[task],
                        "档位": LEVEL_LABELS[level],
                        "样本数": len(vals),
                        "目标分": fmt(mean(targets)),
                        "平均评分": fmt(mean(vals)),
                        "平均绝对误差": fmt(mean(abs_errors)),
                        "平均偏差": fmt(mean(biases)),
                        "三轮标准差": fmt(mean(repeat_stds)),
                        "稳定性分": fmt(max(0, 100 * (1 - mean(repeat_stds) / full)), 1),
                        "一致偏离": fmt(mean(agreement_devs)),
                        "一致性分": fmt(max(0, 100 * (1 - mean(agreement_devs) / full)), 1),
                    })

    optimizer = defaultdict(lambda: {"n": 0, "score": 0.0, "full": 0.0})
    optimization_detail = defaultdict(lambda: {"before": [], "after": [], "gain": []})
    for grade in opt_grades:
        score = number(grade.get("score"))
        opt = opt_by_id.get(grade["optimized_essay_id"])
        if score is None or not opt:
            continue
        src = essay_by_id.get(opt["source_essay_id"])
        if not src:
            continue
        name = model_name(opt["optimizer_ai"])
        optimizer[name]["n"] += 1
        optimizer[name]["score"] += score
        optimizer[name]["full"] += float(src["full_score"])
        grader_name = model_name(grade["grader_ai"])
        before_scores = source_scores.get((src["essay_id"], grader_name), [])
        if before_scores:
            before = mean(before_scores)
            key = (name, src["essay_type"])
            optimization_detail[key]["before"].append(before)
            optimization_detail[key]["after"].append(score)
            optimization_detail[key]["gain"].append(score - before)

    model_rows = []
    for name in sorted(by_model):
        row = by_model[name]
        n = row["n"]
        model_rows.append({
            "label": name,
            "mae": row["abs"] / n,
            "bias": row["bias"] / n,
            "color": COLORS.get(name, "#2563eb"),
        })

    stability_rows = []
    for name in sorted(stability):
        stability_rows.append({
            "label": name,
            "std": mean(stability[name]),
            "color": COLORS.get(name, "#2563eb"),
        })

    type_rows = []
    heat_rows = []
    for task in TASK_ORDER:
        for level in LEVEL_ORDER:
            key = (task, level)
            if key not in by_type_level:
                continue
            row = by_type_level[key]
            n = row["n"]
            avg_target = row["target"] / n
            avg_score = row["score"] / n
            label = f"{TASK_LABELS.get(task, task)} / {LEVEL_LABELS.get(level, level)}"
            type_rows.append({"label": label, "target": avg_target, "score": avg_score})
            heat_rows.append({"task": task, "level": level, "bias": avg_score - avg_target})

    optimizer_rows = []
    for name in sorted(optimizer):
        row = optimizer[name]
        n = row["n"]
        rate = (row["score"] / n) / (row["full"] / n)
        optimizer_rows.append({"label": name, "rate": rate, "color": COLORS.get(name, "#2563eb")})

    optimization_rows = []
    optimization_chart_rows = []
    for name in sorted({key[0] for key in optimization_detail}):
        for task in TASK_ORDER:
            data = optimization_detail.get((name, task))
            if not data or not data["after"]:
                continue
            before = mean(data["before"])
            after = mean(data["after"])
            gain = mean(data["gain"])
            full = 15 if task == "practical_15" else 25
            optimization_rows.append({
                "优化模型": name,
                "题型": TASK_LABELS[task],
                "互评记录数": len(data["after"]),
                "优化前平均分": fmt(before),
                "优化后平均分": fmt(after),
                "平均提升": fmt(gain),
                "优化后得分率": fmt(after / full, 3),
            })
            optimization_chart_rows.append({
                "label": f"{name} / {TASK_LABELS[task]}",
                "model": name,
                "task": task,
                "before": before,
                "after": after,
                "gain": gain,
            })

    model_type_rows = []
    for name in sorted({k[0] for k in by_model_type}):
        practical = mean(by_model_type[(name, "practical_15")])
        continuation = mean(by_model_type[(name, "continuation_25")])
        model_type_rows.append({"label": name, "practical": practical, "continuation": continuation})

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI英语作文评分实验可视化报告</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #64748b;
      --line: #dbe3ef;
      --paper: #ffffff;
      --wash: #f4f7fb;
      --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--wash);
      line-height: 1.55;
    }}
    header {{
      background: #0f172a;
      color: white;
      padding: 44px max(24px, calc((100vw - 1120px) / 2)) 34px;
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(30px, 5vw, 56px); line-height: 1.04; letter-spacing: 0; }}
    header p {{ max-width: 850px; margin: 0; color: #cbd5e1; font-size: 18px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 26px 24px 54px; }}
    .cards {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-top: -42px; }}
    .card, section {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, .08);
    }}
    .card {{ padding: 18px; min-height: 104px; }}
    .card b {{ display: block; font-size: 28px; line-height: 1; margin-bottom: 8px; }}
    .card span {{ color: var(--muted); font-size: 13px; }}
    section {{ margin-top: 18px; padding: 20px; overflow-x: auto; overflow-y: hidden; }}
    h2 {{ margin: 0 0 8px; font-size: 22px; letter-spacing: 0; }}
    .note {{ color: var(--muted); margin: 0 0 18px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .chart {{ width: 100%; height: auto; display: block; background: #fff; border: 1px solid #e6edf7; border-radius: 8px; }}
    .chart-title {{ font-size: 20px; font-weight: 760; fill: #172033; }}
    .chart-subtitle, .legend, .tick, .axislabel {{ font-size: 12px; fill: #64748b; }}
    .xlab, .ylab {{ font-size: 12px; fill: #334155; }}
    .value {{ font-size: 11px; fill: #172033; font-weight: 700; }}
    .heatvalue {{ font-size: 16px; fill: #0f172a; font-weight: 800; }}
    .axis {{ stroke: #94a3b8; stroke-width: 1.2; }}
    .grid {{ stroke: #e2e8f0; stroke-width: 1; }}
    table {{ width: 100%; min-width: 760px; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #e2e8f0; text-align: left; }}
    th {{ color: #475569; font-size: 12px; letter-spacing: 0; }}
    .callout {{ border-left: 4px solid var(--accent); padding: 12px 14px; background: #eff6ff; border-radius: 6px; }}
    @media (max-width: 860px) {{
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid2 {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 520px) {{
      main {{ padding-left: 14px; padding-right: 14px; }}
      .cards {{ grid-template-columns: 1fr; }}
      section {{ padding: 14px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AI英语作文评分实验</h1>
    <p>四个模型围绕高考英语写作完成命题、分档作文生成、三轮批改、满分作文优化与非本人互评后的可视化结果。</p>
  </header>
  <main>
    <div class="cards">
      <div class="card"><b>{len(topics)}</b><span>新命制题目套数</span></div>
      <div class="card"><b>{len(essays)}</b><span>原始生成作文</span></div>
      <div class="card"><b>{len(grades)}</b><span>常规批改记录</span></div>
      <div class="card"><b>{len(optimized)}</b><span>优化作文版本</span></div>
      <div class="card"><b>{len(opt_grades)}</b><span>优化后互评记录</span></div>
    </div>

    <section>
      <h2>核心结论</h2>
      <p class="note">主要现象是模型普遍高估中低档作文，尤其是25分读后续写。上等作文接近满分时，模型反而略微保守。</p>
      <div class="callout">最明显的校准问题：目标为17分的读后续写中等作文，平均被评到21.89分，平均高估4.89分。</div>
    </section>

    <section>
      {bar_chart("常规评分准确性", "各模型的平均绝对误差与平均偏差", model_rows, ["mae", "bias"], ["平均绝对误差", "平均偏差"], ["#2563eb", "#f97316"])}
    </section>

    <section class="grid2">
      <div>{horizontal_bar_chart("三轮评分稳定性", "三次重复批改的平均标准差，越低越稳定", stability_rows, "std", "color", width=540, height=330)}</div>
      <div>{horizontal_bar_chart("满分作文优化效果", "优化版本经非本人模型互评后的平均得分率", optimizer_rows, "rate", "color", width=540, height=330)}</div>
    </section>

    <section>
      {bar_chart("目标分与AI平均评分", "按题型和预设档位分组", type_rows, ["target", "score"], ["目标分", "AI平均评分"], ["#64748b", "#f59e0b"], height=430)}
    </section>

    <section>
      <h2>常规评分：各模型在不同档位上的表现</h2>
      <p class="note">稳定性分由同一模型三次重复评分的平均标准差换算而来；一致性分由该模型平均分与四模型总体平均分的距离换算而来。两个分数均为0-100，越高越好。</p>
      {table(["模型", "档位", "样本数", "平均评分", "平均偏差", "三轮标准差", "稳定性分", "一致偏离", "一致性分"], [[r["模型"], r["档位"], r["样本数"], r["平均评分"], r["平均偏差"], r["三轮标准差"], r["稳定性分"], r["一致偏离"], r["一致性分"]] for r in level_detail_rows])}
    </section>

    <section>
      <h2>常规评分：按题型、模型、档位细分</h2>
      <p class="note">该表展示每个评分模型对15分应用文和25分读后续写中上等、中等、下等作文的具体评分表现。</p>
      {table(["模型", "题型", "档位", "样本数", "目标分", "平均评分", "平均绝对误差", "平均偏差", "三轮标准差", "稳定性分", "一致偏离", "一致性分"], [[r["模型"], r["题型"], r["档位"], r["样本数"], r["目标分"], r["平均评分"], r["平均绝对误差"], r["平均偏差"], r["三轮标准差"], r["稳定性分"], r["一致偏离"], r["一致性分"]] for r in regular_detail_rows])}
    </section>

    <section>
      <h2>AI批改可用性分析：稳定性、一致性与准确性</h2>
      <p><b>稳定性</b>回答的是“同一个模型对同一篇作文反复批改，分数会不会乱跳”。本实验用三轮评分标准差衡量稳定性。结果显示，四个模型的三轮标准差整体较低，`gemini-3.5-flash` 平均标准差为0.19，`gpt-5.5` 为0.24，`deepseek-v4-pro` 为0.47，`mimo-v2.5-pro` 为0.57。按满分换算后的稳定性分大多在95分以上，说明这些模型在重复评分时相当稳定，适合做同一口径下的多次复核。</p>
      <p><b>一致性</b>回答的是“某个模型和其他模型的判断是否接近”。本实验用某模型平均分与四模型总体平均分的距离来衡量一致偏离，并换算成一致性分。上等和中等作文的一致性分普遍较高，多数在96分以上；但下等作文的一致性明显下降，例如 `mimo-v2.5-pro` 在下等作文上的一致性分为89.5，`gpt-5.5` 为91.8。这说明模型越面对低质量作文，分歧越大，尤其是低分作文到底该扣到多低，不同模型判断并不完全一致。</p>
      <p><b>准确性</b>回答的是“模型给分是否接近预设目标分”。这是最关键、也最薄弱的部分。四个模型的平均绝对误差在2.52到2.90分之间，平均偏差全部为正，说明整体偏宽。问题集中在中低档作文：15分应用文中等作文目标10分，平均被评到13.52分；25分读后续写中等作文目标17分，平均被评到21.89分；25分读后续写下等作文目标8分，平均被评到11.84分。也就是说，模型并非随机不准，而是系统性地把中低档作文往高分段推。</p>
      <p><b>综合判断</b>：如果用途是课堂反馈、作文修改建议、初步分档、辅助教师发现问题，AI批改已经有一定可用性，因为它稳定、反馈快、重复评分波动小。但如果用途是考试最终给分、排名、奖惩或替代人工评分，本实验结果还不够。最大原因不是模型不稳定，而是分数校准不足：它们对中等和下等作文过于宽松，尤其不适合单独判断低分作文和读后续写中档作文。</p>
      <p><b>建议用法</b>：更合理的方式是把AI作为“第二评分员”或“初筛评分员”，并用人工锚定作文校准分数。实际部署时应准备一批人工定分样本，分别覆盖上等、中等、下等和两类题型，让模型先对齐这些锚点，再输出最终分数。同时应要求模型给出分项扣分理由，而不只输出总分。</p>
    </section>

    <section class="grid2">
      <div>{heatmap("偏差热力图", "正值代表高估，负值代表低估", heat_rows, width=540, height=330)}</div>
      <div>{bar_chart("各评分模型在两类题型上的偏差", "AI评分减去目标分", model_type_rows, ["practical", "continuation"], ["15分应用文", "25分读后续写"], ["#14b8a6", "#ef4444"], width=540, height=330)}</div>
    </section>

    <section>
      {scatter_chart("作文级校准散点图", "每个点代表某篇作文在某个评分模型三次批改后的平均分", scatter_points)}
    </section>

    <section>
      {distribution_chart("常规批改分数分布", "所有常规批改分数，按2分区间统计", distribution_rows)}
    </section>

    <section>
      {paired_bar_chart("满分作文优化前后对比", "按题型分面展示；每行同一模型的优化前与优化后得分，避免长标签挤压", optimization_chart_rows, height=560)}
    </section>

    <section>
      <h2>作文优化：按模型和题型拆分</h2>
      <p class="note">优化前平均分与优化后平均分使用同一组非本人评分模型进行对照，因此更适合观察优化版本是否真的带来评分提升。</p>
      <p>应用文部分整体已经接近满分，四个模型的优化后平均分都在14.62分以上，提升幅度集中在0.03到0.15分之间。`gemini-3.5-flash` 的应用文优化提升最大，从14.54分升至14.69分；`mimo-v2.5-pro` 的优化后得分率最高，达到0.992，但它的提升幅度只有0.03分，说明原文在非本人评分中已经非常接近满分。</p>
      <p>读后续写部分的差异更有解释价值。`gpt-5.5` 的优化版本从23.82分提升到23.99分，是续写中提升最大的模型；`deepseek-v4-pro` 与 `gemini-3.5-flash` 也有小幅正向提升。`mimo-v2.5-pro` 的续写优化后平均分从23.74分下降到23.42分，说明它给出的优化可能改变了续写中的情节自然度、语言匹配度或评分模型偏好的表达方式。</p>
      <p>因此，满分作文优化阶段不能只看“优化后绝对分”。应用文更容易被优化到接近满分，读后续写则更敏感：优化文本如果语言更华丽但情节衔接或原文融洽度下降，可能反而降低互评分数。</p>
      {table(["优化模型", "题型", "互评记录数", "优化前平均分", "优化后平均分", "平均提升", "优化后得分率"], [[r["优化模型"], r["题型"], r["互评记录数"], r["优化前平均分"], r["优化后平均分"], r["平均提升"], r["优化后得分率"]] for r in optimization_rows])}
    </section>

    <section>
      <h2>模型数据表</h2>
      <p class="note">下表均使用标准模型名称，报告展示中不使用渠道或接口前缀。</p>
      {table(["模型", "样本数", "平均绝对误差", "平均偏差"], [[r["label"], by_model[r["label"]]["n"], fmt(r["mae"]), fmt(r["bias"])] for r in model_rows])}
      {table(["优化模型", "非本人互评记录数", "得分率"], [[r["label"], optimizer[r["label"]]["n"], fmt(r["rate"], 3)] for r in optimizer_rows])}
    </section>
  </main>
</body>
</html>
"""
    (REPORTS / "report.html").write_text(html_doc, encoding="utf-8")
    print("report: reports/report.html")


if __name__ == "__main__":
    main()
