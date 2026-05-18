import json
import re


def parse_questions(raw: str) -> list[dict] | None:
    raw = raw.strip()
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list) or not data:
        return None

    for item in data:
        if not isinstance(item, dict):
            return None
        if not all(k in item for k in ("question", "options", "correct_index", "explanation")):
            return None
        if not isinstance(item["options"], list) or len(item["options"]) != 4:
            return None
        if not isinstance(item["correct_index"], int) or not (0 <= item["correct_index"] <= 3):
            return None

    return data
