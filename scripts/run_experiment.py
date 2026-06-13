import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
CONFIG = ROOT / "config"


def load_dotenv_without_echo() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_windows_env_without_echo(names: set) -> None:
    if os.name != "nt":
        return
    try:
        import winreg
    except ImportError:
        return
    locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    for name in names:
        if os.environ.get(name):
            continue
        for root, subkey in locations:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    value, _ = winreg.QueryValueEx(key, name)
            except OSError:
                continue
            if value:
                os.environ[name] = str(value)
                break


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def existing_ids(path: Path, field: str) -> set:
    return {row.get(field) for row in read_jsonl(path)}


def redact(text: str) -> str:
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key|key)['\"]?\s*[:=]\s*['\"]?[^'\"\s,}]+", r"\1=[REDACTED]", text)
    return text


def extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        candidate = extract_balanced_json_text(text)
        if not candidate:
            raise
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            return json.loads(complete_partial_json(candidate), strict=False)


def extract_balanced_json_text(text: str) -> str:
    start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
    if not start_positions:
        return ""
    start = min(start_positions)
    opening = text[start]
    stack = [opening]
    in_string = False
    escape = False
    for index in range(start + 1, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if not stack:
                break
            expected = "}" if stack[-1] == "{" else "]"
            if char != expected:
                break
            stack.pop()
            if not stack:
                return text[start:index + 1]
    return text[start:]


def complete_partial_json(text: str) -> str:
    text = text.rstrip()
    stack = []
    in_string = False
    escape = False
    for char in text:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if stack:
                stack.pop()
    if escape:
        text += "\\"
    if in_string:
        text += '"'
    while stack:
        text += "}" if stack.pop() == "{" else "]"
    return text


class OpenAICompatibleClient:
    def __init__(self, model_cfg: dict, semaphore: asyncio.Semaphore):
        self.cfg = model_cfg
        self.semaphore = semaphore
        self.api_key = os.environ.get(model_cfg["api_key_env"])
        self.url = model_cfg["base_url"].rstrip("/") + "/chat/completions"

    async def chat_json(self, messages: list, temperature: float = 0.4):
        async with self.semaphore:
            return await asyncio.to_thread(self._chat_json_sync, messages, temperature)

    def _chat_json_sync(self, messages: list, temperature: float):
        if not self.api_key:
            raise RuntimeError(f"Missing environment variable: {self.cfg['api_key_env']}")
        payload = {
            "model": self.cfg["model"],
            "messages": messages,
            "temperature": temperature,
        }
        if self.cfg.get("supports_response_format", True):
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(redact(f"HTTP {exc.code}: {raw[:1200]}")) from exc
        except Exception as exc:
            raise RuntimeError(redact(str(exc))) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(redact(f"Invalid JSON API response from {self.cfg['id']}: {raw[:500]}")) from exc
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")
        if not content and message.get("reasoning_content"):
            content = message.get("reasoning_content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        try:
            return extract_json(str(content))
        except Exception as exc:
            choice_preview = {
                "finish_reason": choice.get("finish_reason"),
                "message_keys": sorted(message.keys()) if isinstance(message, dict) else [],
                "message": message,
            }
            raise RuntimeError(
                redact(
                    f"Invalid JSON message content from {self.cfg['id']}: "
                    f"content={str(content)[:300]} choice={json.dumps(choice_preview, ensure_ascii=False)[:700]}"
                )
            ) from exc


def system_prompt():
    return (
        "你是严谨的高考英语写作命题、作文生成与评分实验助手。"
        "必须只输出合法 JSON，不要输出 Markdown。"
    )


def topic_prompt(original: str, model_id: str):
    return [
        {"role": "system", "content": system_prompt()},
        {
            "role": "user",
            "content": (
                "请基于下面原始题目和评分标准，重新命制一套不同但同级别的高考英语写作题。"
                "必须包含一道15分应用文和一道25分读后续写，并分别给出评分标准。"
                "应用文约80词；续写约150词；不得复用原题故事或具体场景。"
                "输出 JSON：{topic_author_ai, practical_15:{title,prompt,requirements,rubric}, "
                "continuation_25:{title,material,paragraph_starters,requirements,rubric}}。\n"
                f"topic_author_ai={model_id}\n\n原始材料：\n{original}"
            ),
        },
    ]


def essay_prompt(topic: dict, essay_type: str, level: str, target_score: int, full_score: int, seq: int):
    task = topic[essay_type]
    return [
        {"role": "system", "content": system_prompt()},
        {
            "role": "user",
            "content": (
                "请为评分实验生成一篇英语学生作文。必须有意控制质量，使其符合指定目标分，"
                "不要在作文中说明目标分或等级。"
                f"题型={essay_type}，等级={level}，目标分={target_score}/{full_score}，序号={seq}。\n"
                "输出 JSON：{essay_text, intended_quality_notes}。\n"
                f"题目与评分标准：\n{json.dumps(task, ensure_ascii=False)}"
            ),
        },
    ]


def grading_prompt(topic: dict, essay_type: str, essay_text: str, full_score: int):
    return [
        {"role": "system", "content": system_prompt()},
        {
            "role": "user",
            "content": (
                "请严格依据题目和评分标准批改下面英语作文。给出整数分。"
                "输出 JSON：{score, band, content_coverage, language_quality, structure_coherence, "
                "format_or_plot_fit, major_errors, reason}。\n"
                f"满分={full_score}\n题目与评分标准：\n{json.dumps(topic[essay_type], ensure_ascii=False)}\n\n作文：\n{essay_text}"
            ),
        },
    ]


def optimization_prompt(topic: dict, essay_type: str, essay_text: str, full_score: int):
    return [
        {"role": "system", "content": system_prompt()},
        {
            "role": "user",
            "content": (
                "下面是一篇满分目标英语作文。请给出可执行优化建议，并提供一个更自然、更高级、"
                "但仍适合高中考试写作的优化版本。不得改变题目要求。"
                "输出 JSON：{suggestions:[...], optimized_essay}。\n"
                f"满分={full_score}\n题目：\n{json.dumps(topic[essay_type], ensure_ascii=False)}\n\n原作文：\n{essay_text}"
            ),
        },
    ]


async def call_with_retries(client, messages, temperature=0.4):
    last_error = None
    for attempt in range(3):
        try:
            return await client.chat_json(messages, temperature=temperature)
        except Exception as exc:
            message = str(exc)
            if (
                "response_format" in message
                or "Invalid JSON API response" in message
                or "Expecting value" in message
            ):
                client.cfg["supports_response_format"] = False
            last_error = exc
            await asyncio.sleep(2 + attempt * 3 + random.random())
    raise last_error


async def run_streamed(tasks: list, worker, label: str):
    total = len(tasks)
    if total == 0:
        print(f"{label}: nothing to do")
        return []
    print(f"{label}: {total} pending")
    results = []
    completed = 0
    errors = 0
    for future in asyncio.as_completed([worker(task) for task in tasks]):
        try:
            result = await future
            results.append(result)
        except Exception as exc:
            errors += 1
            result = redact(str(exc))
            results.append(exc)
            print(f"{label}: error {errors}: {result[:1000]}", flush=True)
        completed += 1
        if completed == total or completed % 10 == 0:
            print(f"{label}: {completed}/{total} done, errors={errors}", flush=True)
    return results


def clients_from_config():
    load_dotenv_without_echo()
    models = load_json(CONFIG / "models.json")
    load_windows_env_without_echo({m["api_key_env"] for m in models})
    semaphores = {m["id"]: asyncio.Semaphore(1) for m in models}
    return {m["id"]: OpenAICompatibleClient(m, semaphores[m["id"]]) for m in models}, models


def report_missing_env(models: list) -> list:
    missing = sorted({m["api_key_env"] for m in models if not os.environ.get(m["api_key_env"])})
    return missing


async def run_smoke(clients: dict, models: list):
    missing = report_missing_env(models)
    if missing:
        print("Missing environment variables: " + ", ".join(missing))
        return 2
    async def one(model):
        try:
            data = await call_with_retries(
                clients[model["id"]],
                [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": "输出 JSON：{\"ok\":true,\"message\":\"ready\"}"},
                ],
                temperature=0,
            )
            return model["id"], isinstance(data, (dict, list)), None
        except Exception as exc:
            return model["id"], False, redact(str(exc))
    results = await asyncio.gather(*(one(m) for m in models), return_exceptions=True)
    for item in results:
        if isinstance(item, Exception):
            print("smoke_error: " + redact(str(item)))
        elif item[2]:
            print(f"smoke {item[0]}: error: {item[2]}")
        else:
            print(f"smoke {item[0]}: {'ok' if item[1] else 'unexpected'}")
    return 0 if all((not isinstance(r, Exception)) and r[1] for r in results) else 1


async def run_topics(clients: dict, models: list, original: str):
    out = DATA / "topics.jsonl"
    done = existing_ids(out, "topic_id")
    async def one(model):
        topic_id = f"topic_{model['id']}"
        if topic_id in done:
            return "skip", topic_id
        data = await call_with_retries(clients[model["id"]], topic_prompt(original, model["id"]))
        row = {
            "topic_id": topic_id,
            "topic_author_ai": model["id"],
            "created_at": int(time.time()),
            **data,
        }
        append_jsonl(out, row)
        return "ok", topic_id
    await run_streamed(models, one, "topics")


async def run_essays(clients: dict, models: list, experiment: dict):
    topics = read_jsonl(DATA / "topics.jsonl")
    out = DATA / "essays.jsonl"
    done = existing_ids(out, "essay_id")
    levels = experiment["levels"]
    counts = experiment["essay_counts_per_model_topic_type"]
    tasks = []
    for topic in topics:
        for essay_type in ["practical_15", "continuation_25"]:
            full_score = 15 if essay_type == "practical_15" else 25
            for model in models:
                for level, count in counts.items():
                    for seq in range(1, count + 1):
                        essay_id = f"essay_{topic['topic_id']}_{essay_type}_{model['id']}_{level}_{seq}"
                        if essay_id in done:
                            continue
                        tasks.append((essay_id, topic, essay_type, model, level, seq, levels[essay_type][level], full_score))
    async def one(item):
        essay_id, topic, essay_type, model, level, seq, target_score, full_score = item
        data = await call_with_retries(
            clients[model["id"]],
            essay_prompt(topic, essay_type, level, target_score, full_score, seq),
            temperature=0.7,
        )
        append_jsonl(out, {
            "essay_id": essay_id,
            "topic_id": topic["topic_id"],
            "essay_type": essay_type,
            "essay_author_ai": model["id"],
            "essay_level": level,
            "target_score": target_score,
            "full_score": full_score,
            "essay_text": data["essay_text"],
            "intended_quality_notes": data.get("intended_quality_notes", ""),
            "created_at": int(time.time()),
        })
        return essay_id
    await run_streamed(tasks, one, "essays")


async def run_grading(clients: dict, models: list, experiment: dict):
    topics = {row["topic_id"]: row for row in read_jsonl(DATA / "topics.jsonl")}
    essays = read_jsonl(DATA / "essays.jsonl")
    out = DATA / "grading_runs.jsonl"
    done = existing_ids(out, "grading_id")
    tasks = []
    for essay in essays:
        for model in models:
            for repeat in range(1, experiment["grading_repeats"] + 1):
                grading_id = f"grade_{essay['essay_id']}_{model['id']}_{repeat}"
                if grading_id not in done:
                    tasks.append((grading_id, essay, model, repeat))
    async def one(item):
        grading_id, essay, model, repeat = item
        data = await call_with_retries(
            clients[model["id"]],
            grading_prompt(topics[essay["topic_id"]], essay["essay_type"], essay["essay_text"], essay["full_score"]),
            temperature=0.2,
        )
        append_jsonl(out, {
            "grading_id": grading_id,
            "essay_id": essay["essay_id"],
            "grader_ai": model["id"],
            "grading_round": repeat,
            "score": data.get("score"),
            "result": data,
            "created_at": int(time.time()),
        })
        return grading_id
    await run_streamed(tasks, one, "grading")


async def run_optimization(clients: dict, models: list):
    topics = {row["topic_id"]: row for row in read_jsonl(DATA / "topics.jsonl")}
    essays = [row for row in read_jsonl(DATA / "essays.jsonl") if row["essay_level"] == "high"]
    out = DATA / "optimized_essays.jsonl"
    done = existing_ids(out, "optimized_essay_id")
    tasks = []
    for essay in essays:
        for model in models:
            optimized_essay_id = f"opt_{essay['essay_id']}_{model['id']}"
            if optimized_essay_id not in done:
                tasks.append((optimized_essay_id, essay, model))
    async def one(item):
        optimized_essay_id, essay, model = item
        data = await call_with_retries(
            clients[model["id"]],
            optimization_prompt(topics[essay["topic_id"]], essay["essay_type"], essay["essay_text"], essay["full_score"]),
            temperature=0.45,
        )
        append_jsonl(out, {
            "optimized_essay_id": optimized_essay_id,
            "source_essay_id": essay["essay_id"],
            "optimizer_ai": model["id"],
            "optimized_essay": data["optimized_essay"],
            "suggestions": data.get("suggestions", []),
            "created_at": int(time.time()),
        })
        return optimized_essay_id
    await run_streamed(tasks, one, "optimization")


async def run_optimized_grading(clients: dict, models: list):
    topics = {row["topic_id"]: row for row in read_jsonl(DATA / "topics.jsonl")}
    essays = {row["essay_id"]: row for row in read_jsonl(DATA / "essays.jsonl")}
    optimized = read_jsonl(DATA / "optimized_essays.jsonl")
    out = DATA / "optimized_grading_runs.jsonl"
    done = existing_ids(out, "optimized_grading_id")
    tasks = []
    for opt in optimized:
        src = essays[opt["source_essay_id"]]
        for model in models:
            if model["id"] == opt["optimizer_ai"]:
                continue
            grading_id = f"optgrade_{opt['optimized_essay_id']}_{model['id']}_1"
            if grading_id not in done:
                tasks.append((grading_id, opt, src, model))
    async def one(item):
        grading_id, opt, src, model = item
        data = await call_with_retries(
            clients[model["id"]],
            grading_prompt(topics[src["topic_id"]], src["essay_type"], opt["optimized_essay"], src["full_score"]),
            temperature=0.2,
        )
        append_jsonl(out, {
            "optimized_grading_id": grading_id,
            "optimized_essay_id": opt["optimized_essay_id"],
            "source_essay_id": src["essay_id"],
            "grader_ai": model["id"],
            "score": data.get("score"),
            "result": data,
            "created_at": int(time.time()),
        })
        return grading_id
    await run_streamed(tasks, one, "optimized-grading")


def analyze():
    REPORTS.mkdir(parents=True, exist_ok=True)
    essays = read_jsonl(DATA / "essays.jsonl")
    grades = read_jsonl(DATA / "grading_runs.jsonl")
    optimized = read_jsonl(DATA / "optimized_essays.jsonl")
    opt_grades = read_jsonl(DATA / "optimized_grading_runs.jsonl")
    essay_by_id = {e["essay_id"]: e for e in essays}
    opt_by_id = {e["optimized_essay_id"]: e for e in optimized}
    by_model = {}
    by_type_level = {}
    score_groups = {}
    for grade in grades:
        essay = essay_by_id.get(grade["essay_id"])
        score = to_number(grade.get("score"))
        if not essay or not isinstance(score, (int, float)):
            continue
        row = by_model.setdefault(grade["grader_ai"], {"n": 0, "abs_error": 0.0, "bias": 0.0})
        row["n"] += 1
        row["abs_error"] += abs(score - essay["target_score"])
        row["bias"] += score - essay["target_score"]
        key = (essay["essay_type"], essay["essay_level"])
        type_row = by_type_level.setdefault(key, {"n": 0, "score": 0.0, "target": 0.0})
        type_row["n"] += 1
        type_row["score"] += score
        type_row["target"] += essay["target_score"]
        score_groups.setdefault((grade["grader_ai"], grade["essay_id"]), []).append(score)
    stability = {}
    for (grader, _essay_id), scores in score_groups.items():
        if len(scores) < 2:
            continue
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        row = stability.setdefault(grader, {"n": 0, "std": 0.0})
        row["n"] += 1
        row["std"] += variance ** 0.5
    by_optimizer = {}
    for grade in opt_grades:
        opt = opt_by_id.get(grade["optimized_essay_id"])
        score = to_number(grade.get("score"))
        if not opt or not isinstance(score, (int, float)):
            continue
        src = essay_by_id.get(opt["source_essay_id"], {})
        row = by_optimizer.setdefault(opt["optimizer_ai"], {"n": 0, "score": 0.0, "full": 0.0})
        row["n"] += 1
        row["score"] += score
        row["full"] += src.get("full_score", 0)
    lines = ["# AI作文评分实验摘要", ""]
    lines.append("## 数据规模")
    lines.append("")
    lines.append(f"- 题目数：{len(read_jsonl(DATA / 'topics.jsonl'))}")
    lines.append(f"- 原始作文数：{len(essays)}")
    lines.append(f"- 常规批改数：{len(grades)}")
    lines.append(f"- 优化作文数：{len(optimized)}")
    lines.append(f"- 优化后互评数：{len(opt_grades)}")
    lines.append("")
    lines.append("## 常规评分模型")
    lines.append("")
    lines.append("| 评分模型 | 样本数 | 平均绝对误差 | 平均偏差 |")
    lines.append("|---|---:|---:|---:|")
    for model_id, row in sorted(by_model.items(), key=lambda item: display_model_name(item[0])):
        n = row["n"] or 1
        lines.append(f"| {display_model_name(model_id)} | {row['n']} | {row['abs_error'] / n:.2f} | {row['bias'] / n:.2f} |")
    lines.append("")
    lines.append("## 三次评分稳定性")
    lines.append("")
    lines.append("| 评分模型 | 作文组数 | 平均标准差 |")
    lines.append("|---|---:|---:|")
    for model_id, row in sorted(stability.items(), key=lambda item: display_model_name(item[0])):
        n = row["n"] or 1
        lines.append(f"| {display_model_name(model_id)} | {row['n']} | {row['std'] / n:.2f} |")
    lines.append("")
    lines.append("## 题型与档位")
    lines.append("")
    lines.append("| 题型 | 档位 | 样本数 | 平均目标分 | 平均评分 | 平均偏差 |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for (essay_type, level), row in sorted(by_type_level.items()):
        n = row["n"] or 1
        avg_score = row["score"] / n
        avg_target = row["target"] / n
        lines.append(f"| {display_task_name(essay_type)} | {display_level_name(level)} | {row['n']} | {avg_target:.2f} | {avg_score:.2f} | {avg_score - avg_target:.2f} |")
    lines.append("")
    lines.append("## 满分作文优化互评")
    lines.append("")
    lines.append("| 优化模型 | 非本人互评数 | 平均得分 | 平均满分 | 得分率 |")
    lines.append("|---|---:|---:|---:|---:|")
    for model_id, row in sorted(by_optimizer.items(), key=lambda item: display_model_name(item[0])):
        n = row["n"] or 1
        avg_score = row["score"] / n
        avg_full = row["full"] / n
        rate = avg_score / avg_full if avg_full else 0
        lines.append(f"| {display_model_name(model_id)} | {row['n']} | {avg_score:.2f} | {avg_full:.2f} | {rate:.3f} |")
    (REPORTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (REPORTS / "model_bias.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["评分模型", "样本数", "平均绝对误差", "平均偏差"])
        for model_id, row in sorted(by_model.items(), key=lambda item: display_model_name(item[0])):
            n = row["n"] or 1
            writer.writerow([display_model_name(model_id), row["n"], f"{row['abs_error'] / n:.4f}", f"{row['bias'] / n:.4f}"])
    with (REPORTS / "optimizer_scores.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["优化模型", "非本人互评记录数", "平均得分", "平均满分", "得分率"])
        for model_id, row in sorted(by_optimizer.items(), key=lambda item: display_model_name(item[0])):
            n = row["n"] or 1
            avg_score = row["score"] / n
            avg_full = row["full"] / n
            writer.writerow([display_model_name(model_id), row["n"], f"{avg_score:.4f}", f"{avg_full:.4f}", f"{(avg_score / avg_full if avg_full else 0):.4f}"])
    print("report: reports/summary.md")


def display_model_name(model_id: str) -> str:
    return {
        "yumu_gpt55": "gpt-5.5",
        "yumu_gemini35": "gemini-3.5-flash",
        "deepseek_v4": "deepseek-v4-pro",
        "mimo_v25": "mimo-v2.5-pro",
    }.get(model_id, model_id)


def display_task_name(task_id: str) -> str:
    return {
        "practical_15": "15分应用文",
        "continuation_25": "25分读后续写",
    }.get(task_id, task_id)


def display_level_name(level_id: str) -> str:
    return {
        "high": "上等",
        "medium": "中等",
        "low": "下等",
    }.get(level_id, level_id)


def to_number(value):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            number = float(match.group(0))
            return int(number) if number.is_integer() else number
    return None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["smoke", "topics", "essays", "grading", "optimization", "optimized-grading", "analyze", "all"], default="smoke")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    clients, models = clients_from_config()
    if args.phase == "analyze":
        analyze()
        return 0
    if args.phase != "smoke":
        missing = report_missing_env(models)
        if missing:
            print("Missing environment variables: " + ", ".join(missing))
            return 2
    original = (ROOT / "题目.md").read_text(encoding="utf-8")
    experiment = load_json(CONFIG / "experiment.json")
    if args.phase == "smoke":
        return await run_smoke(clients, models)
    if args.phase in ["topics", "all"]:
        await run_topics(clients, models, original)
    if args.phase in ["essays", "all"]:
        await run_essays(clients, models, experiment)
    if args.phase in ["grading", "all"]:
        await run_grading(clients, models, experiment)
    if args.phase in ["optimization", "all"]:
        await run_optimization(clients, models)
    if args.phase in ["optimized-grading", "all"]:
        await run_optimized_grading(clients, models)
    if args.phase == "all":
        analyze()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
