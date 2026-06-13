import json
import math
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "reports" / "social"

W, H = 1080, 1440
BG = "#f5f7fb"
PAPER = "#ffffff"
INK = "#172033"
MUTED = "#64748b"
LINE = "#dbe3ef"
BLUE = "#2563eb"
ORANGE = "#f97316"
GREEN = "#059669"
PURPLE = "#7c3aed"
RED = "#dc2626"
SLATE = "#94a3b8"

FONT_PATH = Path("C:/Windows/Fonts/simhei.ttf")

MODEL_NAMES = {
    "yumu_gpt55": "gpt-5.5",
    "yumu_gemini35": "gemini-3.5-flash",
    "deepseek_v4": "deepseek-v4-pro",
    "mimo_v25": "mimo-v2.5-pro",
}
MODEL_ORDER = ["deepseek-v4-pro", "gemini-3.5-flash", "gpt-5.5", "mimo-v2.5-pro"]
MODEL_COLORS = {
    "deepseek-v4-pro": GREEN,
    "gemini-3.5-flash": PURPLE,
    "gpt-5.5": BLUE,
    "mimo-v2.5-pro": RED,
}
TASK_LABELS = {"practical_15": "15分应用文", "continuation_25": "25分读后续写"}
TASK_ORDER = ["practical_15", "continuation_25"]
LEVEL_LABELS = {"high": "上等", "medium": "中等", "low": "下等"}
LEVEL_ORDER = ["high", "medium", "low"]


def font(size):
    return ImageFont.truetype(str(FONT_PATH), size)


F = {
    "title": font(48),
    "subtitle": font(27),
    "h2": font(34),
    "body": font(25),
    "small": font(21),
    "tiny": font(18),
    "num": font(36),
}


def read_jsonl(name):
    path = DATA / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def mean(values):
    return sum(values) / len(values) if values else 0


def stdev(values):
    if not values:
        return 0
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def model_name(model_id):
    return MODEL_NAMES.get(model_id, model_id)


def new_canvas(title, subtitle=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((34, 30, W - 34, H - 30), radius=28, fill=PAPER, outline=LINE, width=2)
    d.text((74, 70), title, font=F["title"], fill=INK)
    if subtitle:
        draw_wrapped(d, subtitle, 74, 136, W - 148, F["subtitle"], MUTED, line_gap=10)
    return img, d


def draw_wrapped(d, text, x, y, max_w, fnt, fill=INK, line_gap=8):
    lines = []
    for para in text.split("\n"):
        current = ""
        for ch in para:
            test = current + ch
            if d.textlength(test, font=fnt) <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    line_h = fnt.size + line_gap
    for i, line in enumerate(lines):
        d.text((x, y + i * line_h), line, font=fnt, fill=fill)
    return y + len(lines) * line_h


def pill(d, xy, text, fill, fg="#ffffff"):
    x1, y1, x2, y2 = xy
    d.rounded_rectangle(xy, radius=(y2 - y1) // 2, fill=fill)
    tw = d.textlength(text, font=F["small"])
    d.text((x1 + (x2 - x1 - tw) / 2, y1 + 7), text, font=F["small"], fill=fg)


def card(d, xy, title, value, note, color=BLUE):
    x1, y1, x2, y2 = xy
    d.rounded_rectangle(xy, radius=18, fill="#f8fafc", outline=LINE, width=2)
    d.rectangle((x1, y1, x1 + 8, y2), fill=color)
    d.text((x1 + 26, y1 + 22), title, font=F["small"], fill=MUTED)
    d.text((x1 + 26, y1 + 58), value, font=F["num"], fill=INK)
    draw_wrapped(d, note, x1 + 26, y1 + 110, x2 - x1 - 52, F["tiny"], MUTED, line_gap=5)


def bar_chart(d, x, y, w, h, rows, keys, colors, y_min=None, y_max=None, legend=None):
    values = [row[key] for row in rows for key in keys]
    y_min = min(0, min(values)) if y_min is None else y_min
    y_max = max(values) if y_max is None else y_max
    if y_max == y_min:
        y_max += 1
    d.line((x, y + h, x + w, y + h), fill="#94a3b8", width=2)
    zero_y = y + h - (0 - y_min) / (y_max - y_min) * h
    if y_min < 0:
        d.line((x, zero_y, x + w, zero_y), fill="#94a3b8", width=2)
    group_w = w / len(rows)
    bar_w = min(34, group_w / (len(keys) + 1))
    for i, row in enumerate(rows):
        cx = x + group_w * i + group_w / 2
        start = cx - bar_w * len(keys) / 2
        for j, key in enumerate(keys):
            value = row[key]
            bh = abs(value) / (y_max - y_min) * h
            by = zero_y - bh if value >= 0 else zero_y
            bx = start + j * bar_w
            d.rounded_rectangle((bx, by, bx + bar_w - 5, by + bh), radius=5, fill=colors[j])
            label = f"{value:.2f}"
            tw = d.textlength(label, font=F["tiny"])
            d.text((bx + (bar_w - 5 - tw) / 2, by - 25), label, font=F["tiny"], fill=INK)
        draw_centered_label(d, row["label"], cx, y + h + 18, group_w - 6, F["tiny"], INK)
    if legend:
        lx = x
        ly = y + h + 88
        for i, label in enumerate(legend):
            d.rounded_rectangle((lx, ly, lx + 22, ly + 22), radius=5, fill=colors[i])
            d.text((lx + 30, ly - 1), label, font=F["small"], fill=MUTED)
            lx += 210


def horizontal_bars(d, x, y, w, rows, key, max_value=None, value_digits=2):
    max_value = max_value or max(row[key] for row in rows)
    row_h = 58
    for i, row in enumerate(rows):
        yy = y + i * row_h
        d.text((x, yy + 10), row["label"], font=F["small"], fill=INK)
        bx = x + 250
        bw = w - 330
        d.rounded_rectangle((bx, yy + 8, bx + bw, yy + 34), radius=10, fill="#e8eef7")
        fill_w = bw * row[key] / max_value
        d.rounded_rectangle((bx, yy + 8, bx + fill_w, yy + 34), radius=10, fill=row.get("color", BLUE))
        d.text((bx + bw + 16, yy + 5), f"{row[key]:.{value_digits}f}", font=F["small"], fill=INK)


def draw_centered_label(d, text, cx, y, max_w, fnt, fill):
    if d.textlength(text, font=fnt) <= max_w:
        d.text((cx - d.textlength(text, font=fnt) / 2, y), text, font=fnt, fill=fill)
        return
    parts = text.split(" / ")
    for i, part in enumerate(parts):
        tw = d.textlength(part, font=fnt)
        d.text((cx - tw / 2, y + i * (fnt.size + 4)), part, font=fnt, fill=fill)


def table(d, x, y, cols, rows, widths, row_h=42, header_fill="#e8eef7"):
    d.rounded_rectangle((x, y, x + sum(widths), y + row_h * (len(rows) + 1)), radius=12, fill="#fbfdff", outline=LINE, width=1)
    cx = x
    for col, width in zip(cols, widths):
        d.rectangle((cx, y, cx + width, y + row_h), fill=header_fill)
        d.text((cx + 10, y + 9), col, font=F["tiny"], fill=INK)
        cx += width
    for r, row in enumerate(rows):
        yy = y + row_h * (r + 1)
        cx = x
        if r % 2 == 1:
            d.rectangle((x, yy, x + sum(widths), yy + row_h), fill="#f8fafc")
        for value, width in zip(row, widths):
            d.text((cx + 10, yy + 9), str(value), font=F["tiny"], fill=INK)
            cx += width


def compute():
    topics = read_jsonl("topics")
    essays = read_jsonl("essays")
    grades = read_jsonl("grading_runs")
    opts = read_jsonl("optimized_essays")
    opt_grades = read_jsonl("optimized_grading_runs")
    essay_by_id = {row["essay_id"]: row for row in essays}
    opt_by_id = {row["optimized_essay_id"]: row for row in opts}
    by_model = defaultdict(lambda: {"n": 0, "abs": 0.0, "bias": 0.0})
    by_type_level = defaultdict(lambda: {"n": 0, "score": 0.0, "target": 0.0})
    repeated = defaultdict(list)
    source_scores = defaultdict(list)
    for grade in grades:
        score = number(grade.get("score"))
        if score is None:
            continue
        essay = essay_by_id[grade["essay_id"]]
        model = model_name(grade["grader_ai"])
        target = float(essay["target_score"])
        by_model[model]["n"] += 1
        by_model[model]["abs"] += abs(score - target)
        by_model[model]["bias"] += score - target
        by_type_level[(essay["essay_type"], essay["essay_level"])]["n"] += 1
        by_type_level[(essay["essay_type"], essay["essay_level"])]["score"] += score
        by_type_level[(essay["essay_type"], essay["essay_level"])]["target"] += target
        repeated[(model, grade["essay_id"])].append(score)
        source_scores[(grade["essay_id"], model)].append(score)

    panel = defaultdict(list)
    for (_model, eid), scores in repeated.items():
        panel[eid].append(mean(scores))
    panel = {eid: mean(vals) for eid, vals in panel.items()}

    level_rows = []
    for model in MODEL_ORDER:
        for level in LEVEL_ORDER:
            vals, biases, stds, agrees, fulls = [], [], [], [], []
            for (m, eid), scores in repeated.items():
                if m != model:
                    continue
                essay = essay_by_id[eid]
                if essay["essay_level"] != level:
                    continue
                avg = mean(scores)
                vals.append(avg)
                biases.append(avg - essay["target_score"])
                stds.append(stdev(scores))
                agrees.append(abs(avg - panel[eid]))
                fulls.append(essay["full_score"])
            full = mean(fulls)
            level_rows.append({
                "model": model,
                "level": LEVEL_LABELS[level],
                "avg": mean(vals),
                "bias": mean(biases),
                "std": mean(stds),
                "stability": 100 * (1 - mean(stds) / full),
                "agree": mean(agrees),
                "consistency": 100 * (1 - mean(agrees) / full),
            })

    opt_detail = defaultdict(lambda: {"before": [], "after": [], "gain": []})
    for grade in opt_grades:
        score = number(grade.get("score"))
        if score is None:
            continue
        opt = opt_by_id[grade["optimized_essay_id"]]
        essay = essay_by_id[opt["source_essay_id"]]
        optimizer = model_name(opt["optimizer_ai"])
        grader = model_name(grade["grader_ai"])
        before_scores = source_scores[(essay["essay_id"], grader)]
        before = mean(before_scores)
        key = (optimizer, essay["essay_type"])
        opt_detail[key]["before"].append(before)
        opt_detail[key]["after"].append(score)
        opt_detail[key]["gain"].append(score - before)

    return {
        "topics": topics,
        "essays": essays,
        "grades": grades,
        "opts": opts,
        "opt_grades": opt_grades,
        "by_model": by_model,
        "by_type_level": by_type_level,
        "repeated": repeated,
        "level_rows": level_rows,
        "opt_detail": opt_detail,
    }


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    img.save(path, quality=95)
    print(path)


def image_01(data):
    img, d = new_canvas("AI批改英语作文，靠谱吗？", "我用四个模型做了一次完整实验：命题、生成作文、重复批改、作文优化和交叉互评。")
    y = 240
    cards = [
        ("新题", "4套", "每个模型重新命制一套题"),
        ("作文", "160篇", "覆盖应用文与读后续写"),
        ("批改", "1920次", "每篇由四个模型各批三次"),
        ("优化", "256版", "满分作文再优化并互评"),
    ]
    for i, (t, v, n) in enumerate(cards):
        x = 86 + (i % 2) * 460
        yy = y + (i // 2) * 210
        card(d, (x, yy, x + 410, yy + 165), t, v, n, [BLUE, PURPLE, GREEN, ORANGE][i])
    y = 720
    d.text((86, y), "一句话结论", font=F["h2"], fill=INK)
    y += 60
    draw_wrapped(d, "AI批改的“稳定性”已经不错，同一模型反复批同一篇作文，分数波动不大；模型之间的“一致性”也基本可用。", 86, y, 908, F["body"], INK, 12)
    y += 170
    draw_wrapped(d, "但“准确性”还不够：中等和下等作文明显容易被高估，尤其是25分读后续写。它更适合做辅助评分和反馈，不适合直接替代正式阅卷。", 86, y, 908, F["body"], INK, 12)
    pill(d, (86, 1260, 440, 1310), "稳定性够好", GREEN)
    pill(d, (470, 1260, 824, 1310), "准确性需校准", ORANGE)
    save(img, "01_朋友圈封面_核心结论.png")


def image_02(data):
    img, d = new_canvas("实验流程与数据规模", "为了避免只看个例，我把命题、作文生成、批改和优化都做成批量流程。")
    steps = [
        ("1", "四个模型各命制一套题", "每套含15分应用文和25分读后续写"),
        ("2", "按上中下三档生成作文", "每题每模型生成5篇，共160篇"),
        ("3", "四个模型重复批改", "每篇作文每个模型批改3次，共1920条"),
        ("4", "满分作文优化互评", "256个优化版本，768次非本人互评"),
    ]
    y = 240
    for i, (num, title, note) in enumerate(steps):
        d.ellipse((88, y, 148, y + 60), fill=BLUE)
        d.text((108, y + 12), num, font=F["subtitle"], fill="#fff")
        d.text((180, y), title, font=F["h2"], fill=INK)
        draw_wrapped(d, note, 180, y + 48, 780, F["body"], MUTED)
        if i < len(steps) - 1:
            d.line((118, y + 72, 118, y + 145), fill=LINE, width=4)
        y += 190
    d.text((86, 1080), "目标分设置", font=F["h2"], fill=INK)
    table(d, 86, 1145, ["题型", "上等", "中等", "下等"], [["15分应用文", "15", "10", "5"], ["25分读后续写", "25", "17", "8"]], [270, 180, 180, 180], 54)
    save(img, "02_实验流程与规模.png")


def image_03(data):
    img, d = new_canvas("准确性：模型整体偏宽", "平均偏差全为正值，说明四个模型整体倾向于给高分。")
    rows = []
    for model in MODEL_ORDER:
        row = data["by_model"][model]
        n = row["n"]
        rows.append({"label": model, "mae": row["abs"] / n, "bias": row["bias"] / n})
    bar_chart(d, 90, 260, 900, 520, rows, ["mae", "bias"], [BLUE, ORANGE], y_max=3.3, legend=["平均绝对误差", "平均偏差"])
    y = 930
    d.text((86, y), "怎么读这张图", font=F["h2"], fill=INK)
    y += 62
    draw_wrapped(d, "平均绝对误差表示离目标分有多远；平均偏差表示偏高还是偏低。这里所有模型的平均偏差都是正数，说明不是随机误差，而是整体偏宽。", 86, y, 908, F["body"], INK)
    save(img, "03_准确性_总体偏宽.png")


def image_04(data):
    img, d = new_canvas("稳定性与一致性：重复评分很稳", "稳定性看同一模型三次批改是否乱跳；一致性看它是否接近四模型总体判断。")
    stability_rows = []
    consistency_rows = []
    for model in MODEL_ORDER:
        rows = [r for r in data["level_rows"] if r["model"] == model]
        stability_rows.append({"label": model, "score": mean([r["stability"] for r in rows]), "color": MODEL_COLORS[model]})
        consistency_rows.append({"label": model, "score": mean([r["consistency"] for r in rows]), "color": MODEL_COLORS[model]})
    d.text((86, 220), "稳定性分", font=F["h2"], fill=INK)
    horizontal_bars(d, 86, 285, 900, stability_rows, "score", 100, 1)
    d.text((86, 610), "一致性分", font=F["h2"], fill=INK)
    horizontal_bars(d, 86, 675, 900, consistency_rows, "score", 100, 1)
    draw_wrapped(d, "结论：重复批改本身比较稳定，模型之间也大体一致。真正的问题不是“分数乱跳”，而是“分数尺度偏宽”，特别是中低档作文。", 86, 1040, 908, F["body"], INK)
    save(img, "04_稳定性与一致性.png")


def image_05(data):
    img, d = new_canvas("最关键的问题：中低档被高估", "按题型和档位看，AI评分明显向高分段压缩。")
    rows = []
    for task in TASK_ORDER:
        for level in LEVEL_ORDER:
            row = data["by_type_level"][(task, level)]
            n = row["n"]
            rows.append({
                "label": f"{TASK_LABELS[task]} / {LEVEL_LABELS[level]}",
                "target": row["target"] / n,
                "score": row["score"] / n,
            })
    bar_chart(d, 72, 250, 940, 560, rows, ["target", "score"], [SLATE, BLUE], y_max=27, legend=["目标分", "AI平均分"])
    draw_wrapped(d, "25分读后续写中等作文：目标17分，平均被评到21.89分。下等作文目标8分，平均被评到11.84分。AI最容易把中低档作文“抬高”。", 86, 980, 908, F["body"], INK)
    save(img, "05_题型档位_目标分与AI评分.png")


def image_06(data):
    img, d = new_canvas("每个模型对不同档位的评分", "合并两类题型后看，上等略保守，中下等普遍偏宽。")
    cols = ["模型", "档位", "均分", "偏差", "稳定", "一致"]
    widths = [250, 100, 120, 120, 120, 120]
    rows = []
    for r in data["level_rows"]:
        rows.append([r["model"], r["level"], f"{r['avg']:.2f}", f"{r['bias']:.2f}", f"{r['stability']:.1f}", f"{r['consistency']:.1f}"])
    table(d, 70, 230, cols, rows, widths, 46)
    draw_wrapped(d, "看点：gpt-5.5 对下等作文最宽，平均偏差+4.50；mimo-v2.5-pro 对下等作文更严格，但一致性最低。", 86, 1195, 908, F["body"], INK)
    save(img, "06_模型分档评分表.png")


def image_07(data):
    img, d = new_canvas("读后续写更容易被高估", "两类题型分开看，25分读后续写的中等和下等偏差更大。")
    x0, y0 = 90, 260
    cell_w, cell_h = 145, 78
    d.text((x0 + 210, y0 - 58), "上等", font=F["small"], fill=INK)
    d.text((x0 + 355, y0 - 58), "中等", font=F["small"], fill=INK)
    d.text((x0 + 500, y0 - 58), "下等", font=F["small"], fill=INK)
    max_abs = 5.7
    for mi, model in enumerate(MODEL_ORDER):
        y = y0 + mi * (cell_h * 2 + 35)
        d.text((x0, y + 40), model, font=F["small"], fill=INK)
        for ti, task in enumerate(TASK_ORDER):
            d.text((x0 + 160, y + ti * cell_h + 26), TASK_LABELS[task], font=F["tiny"], fill=MUTED)
            for li, level in enumerate(LEVEL_ORDER):
                vals = []
                for (m, eid), scores in data["repeated"].items():
                    if m != model:
                        continue
                    # Re-read via closure unavailable; use compact lookup from score rows.
                # Use precomputed by_type_level for overall row fallback handled below.
        # Draw model/task/level from recalculation helper.
    # Simpler table heatmap values from known computation.
    detail = compute_detail_for_heatmap(data)
    for mi, model in enumerate(MODEL_ORDER):
        y = y0 + mi * (cell_h * 2 + 35)
        d.text((x0, y + 58), model, font=F["small"], fill=INK)
        for ti, task in enumerate(TASK_ORDER):
            d.text((x0 + 180, y + ti * cell_h + 26), TASK_LABELS[task], font=F["tiny"], fill=MUTED)
            for li, level in enumerate(LEVEL_ORDER):
                bias = detail[(model, task, level)]
                intensity = min(1, abs(bias) / max_abs)
                color = blend("#f8fafc", RED if bias >= 0 else BLUE, 0.2 + 0.7 * intensity)
                x = x0 + 310 + li * cell_w
                yy = y + ti * cell_h
                d.rounded_rectangle((x, yy, x + cell_w - 12, yy + cell_h - 12), radius=12, fill=color)
                text = f"{bias:+.2f}"
                tw = d.textlength(text, font=F["small"])
                d.text((x + (cell_w - 12 - tw) / 2, yy + 20), text, font=F["small"], fill=INK)
    draw_wrapped(d, "红色越深代表高估越严重。最突出的格子集中在读后续写中等与下等。", 86, 1215, 908, F["body"], INK)
    save(img, "07_模型题型档位偏差热力图.png")


def compute_detail_for_heatmap(data):
    essays = {row["essay_id"]: row for row in read_jsonl("essays")}
    out = {}
    for model in MODEL_ORDER:
        for task in TASK_ORDER:
            for level in LEVEL_ORDER:
                biases = []
                for (m, eid), scores in data["repeated"].items():
                    if m != model:
                        continue
                    essay = essays[eid]
                    if essay["essay_type"] == task and essay["essay_level"] == level:
                        biases.append(mean(scores) - essay["target_score"])
                out[(model, task, level)] = mean(biases)
    return out


def blend(c1, c2, t):
    def parse(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    a, b = parse(c1), parse(c2)
    vals = [int(a[i] * (1 - t) + b[i] * t) for i in range(3)]
    return "#" + "".join(f"{v:02x}" for v in vals)


def image_08(data):
    img, d = new_canvas("满分作文优化前后", "优化前后用同一批非本人评分模型对照，应用文和读后续写分开看。")
    y = 220
    for task in TASK_ORDER:
        d.text((86, y), TASK_LABELS[task], font=F["h2"], fill=INK)
        y += 58
        for model in MODEL_ORDER:
            item = data["opt_detail"][(model, task)]
            before, after, gain = mean(item["before"]), mean(item["after"]), mean(item["gain"])
            d.text((86, y + 6), model, font=F["small"], fill=INK)
            bx = 340
            bw = 500
            maxv = 25 if task == "continuation_25" else 15
            d.rounded_rectangle((bx, y, bx + bw, y + 16), radius=6, fill="#e8eef7")
            d.rounded_rectangle((bx, y + 24, bx + bw, y + 40), radius=6, fill="#e8eef7")
            d.rounded_rectangle((bx, y, bx + bw * before / maxv, y + 16), radius=6, fill=SLATE)
            d.rounded_rectangle((bx, y + 24, bx + bw * after / maxv, y + 40), radius=6, fill=BLUE)
            d.text((860, y - 3), f"{before:.2f}", font=F["tiny"], fill=MUTED)
            d.text((860, y + 21), f"{after:.2f}  提升{gain:+.2f}", font=F["tiny"], fill=INK)
            y += 62
        y += 40
    draw_wrapped(d, "满分作文本来提升空间很小。读后续写更敏感：gpt-5.5 提升最大，mimo-v2.5-pro 在续写上反而下降。", 86, 1190, 908, F["body"], INK)
    save(img, "08_优化前后对比.png")


def image_09(data):
    img, d = new_canvas("能不能用 AI 批改作文？", "我的判断：可以辅助，但不能裸奔。")
    items = [
        ("可以用", "课堂反馈、作文修改建议、初步分档、第二评分员。", GREEN),
        ("要谨慎", "中低档作文容易被高估，读后续写尤其明显。", ORANGE),
        ("不能直接替代", "正式考试给分、排名、奖惩，必须有人工作文锚点和复核。", RED),
    ]
    y = 260
    for title, body, color in items:
        d.rounded_rectangle((86, y, 994, y + 210), radius=22, fill="#f8fafc", outline=LINE, width=2)
        pill(d, (122, y + 30, 292, y + 78), title, color)
        draw_wrapped(d, body, 122, y + 104, 820, F["body"], INK, 10)
        y += 260
    d.text((86, 1088), "推荐流程", font=F["h2"], fill=INK)
    draw_wrapped(d, "AI初评 → 分项理由 → 与人工锚定作文校准 → 分差异常人工复核 → 再输出最终分。", 86, 1150, 908, F["body"], INK, 12)
    save(img, "09_最终判断与使用建议.png")


def main():
    data = compute()
    image_01(data)
    image_02(data)
    image_03(data)
    image_04(data)
    image_05(data)
    image_06(data)
    image_07(data)
    image_08(data)
    image_09(data)


if __name__ == "__main__":
    main()
