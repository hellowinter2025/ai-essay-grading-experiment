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
        parts.append(f'<text x="{margin["left"] - 14}" y="{y + cell_h / 2 + 5:.1f}" class="ylab" text-anchor="end">{esc(task)}</text>')
        for c, level in enumerate(levels):
            value = data.get((task, level), 0)
            x = margin["left"] + c * cell_w
            color = heat_color(value, max_abs)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w - 8:.1f}" height="{cell_h - 8:.1f}" rx="8" fill="{color}"/>')
            parts.append(f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 5:.1f}" class="heatvalue" text-anchor="middle">{fmt(value)}</text>')
    for c, level in enumerate(levels):
        x = margin["left"] + c * cell_w + cell_w / 2
        parts.append(f'<text x="{x:.1f}" y="{height - 18}" class="xlab" text-anchor="middle">{esc(level)}</text>')
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
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" opacity="0.72"><title>{esc(point["model"])} target {fmt(point["target"])} avg {fmt(point["score"])}</title></circle>')
    parts.append(f'<text x="{margin["left"] + plot_w / 2}" y="{height - 4}" class="axislabel" text-anchor="middle">Target score</text>')
    parts.append(f'<text x="18" y="{margin["top"] + plot_h / 2}" class="axislabel" transform="rotate(-90 18 {margin["top"] + plot_h / 2})" text-anchor="middle">Average AI score</text>')
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
    parts.append(f'<text x="{margin["left"] + plot_w / 2}" y="{height - 8}" class="axislabel" text-anchor="middle">Score bucket</text>')
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

    for grade in grades:
        score = number(grade.get("score"))
        essay = essay_by_id.get(grade["essay_id"])
        if score is None or not essay:
            continue
        name = model_name(grade["grader_ai"])
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

    optimizer = defaultdict(lambda: {"n": 0, "score": 0.0, "full": 0.0})
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
    for key in sorted(by_type_level):
        task, level = key
        row = by_type_level[key]
        n = row["n"]
        avg_target = row["target"] / n
        avg_score = row["score"] / n
        label = f"{task.replace('_', ' ')} / {level}"
        type_rows.append({"label": label, "target": avg_target, "score": avg_score})
        heat_rows.append({"task": task, "level": level, "bias": avg_score - avg_target})

    optimizer_rows = []
    for name in sorted(optimizer):
        row = optimizer[name]
        n = row["n"]
        rate = (row["score"] / n) / (row["full"] / n)
        optimizer_rows.append({"label": name, "rate": rate, "color": COLORS.get(name, "#2563eb")})

    model_type_rows = []
    for name in sorted({k[0] for k in by_model_type}):
        practical = mean(by_model_type[(name, "practical_15")])
        continuation = mean(by_model_type[(name, "continuation_25")])
        model_type_rows.append({"label": name, "practical": practical, "continuation": continuation})

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI English Essay Grading Experiment - Visual Report</title>
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
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
    section {{ margin-top: 18px; padding: 20px; overflow: hidden; }}
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
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #e2e8f0; text-align: left; }}
    th {{ color: #475569; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
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
    <h1>AI English Essay Grading Experiment</h1>
    <p>A visual report on task generation, controlled essay generation, repeated grading, full-score essay optimization, and non-self cross-grading across four AI models.</p>
  </header>
  <main>
    <div class="cards">
      <div class="card"><b>{len(topics)}</b><span>Generated task sets</span></div>
      <div class="card"><b>{len(essays)}</b><span>Original essays</span></div>
      <div class="card"><b>{len(grades)}</b><span>Regular grading records</span></div>
      <div class="card"><b>{len(optimized)}</b><span>Optimized essays</span></div>
      <div class="card"><b>{len(opt_grades)}</b><span>Optimized cross-grades</span></div>
    </div>

    <section>
      <h2>Executive Summary</h2>
      <p class="note">The main pattern is generous grading for medium and low essays, especially in the 25-point continuation task. High-level essays were slightly under-scored near the ceiling.</p>
      <div class="callout">The clearest calibration issue: continuation essays targeting 17 points were graded at an average of 21.89, a positive bias of 4.89 points.</div>
    </section>

    <section>
      {bar_chart("Regular grading accuracy", "Mean absolute error and mean bias by model", model_rows, ["mae", "bias"], ["Mean absolute error", "Mean bias"], ["#2563eb", "#f97316"])}
    </section>

    <section class="grid2">
      <div>{horizontal_bar_chart("Repeated grading stability", "Average standard deviation across three runs; lower is steadier", stability_rows, "std", "color", width=540, height=330)}</div>
      <div>{horizontal_bar_chart("Full-score optimization", "Non-self cross-graded score rate after optimization", optimizer_rows, "rate", "color", width=540, height=330)}</div>
    </section>

    <section>
      {bar_chart("Target score vs average AI score", "Grouped by task type and intended essay level", type_rows, ["target", "score"], ["Target", "Average AI score"], ["#64748b", "#f59e0b"], height=430)}
    </section>

    <section class="grid2">
      <div>{heatmap("Bias heatmap", "Positive values mean over-scoring; negative values mean under-scoring", heat_rows, width=540, height=330)}</div>
      <div>{bar_chart("Bias by task type and grader", "Average score minus target score", model_type_rows, ["practical", "continuation"], ["Practical writing", "Continuation writing"], ["#14b8a6", "#ef4444"], width=540, height=330)}</div>
    </section>

    <section>
      {scatter_chart("Essay-level calibration map", "Each point is one essay averaged over one grader's three repeated scores", scatter_points)}
    </section>

    <section>
      {distribution_chart("Score distribution", "All regular grading scores, bucketed by two-point intervals", distribution_rows)}
    </section>

    <section>
      <h2>Model Tables</h2>
      <p class="note">All names below are standard model names. Channel or provider prefixes are intentionally omitted from the report display.</p>
      {table(["Model", "Samples", "Mean absolute error", "Mean bias"], [[r["label"], by_model[r["label"]]["n"], fmt(r["mae"]), fmt(r["bias"])] for r in model_rows])}
      {table(["Optimizer model", "Cross-grading records", "Score rate"], [[r["label"], optimizer[r["label"]]["n"], fmt(r["rate"], 3)] for r in optimizer_rows])}
    </section>
  </main>
</body>
</html>
"""
    (REPORTS / "report.html").write_text(html_doc, encoding="utf-8")
    print("report: reports/report.html")


if __name__ == "__main__":
    main()
