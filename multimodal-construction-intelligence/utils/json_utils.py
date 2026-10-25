"""Reusable helpers for turning (possibly messy) LLM text into validated JSON.

Pipeline used by every AI module (EPIC 4 - JSON contracts):
    1. extract_json()  - strip code fences, find the JSON object, parse
    2. repair          - fix trailing commas, smart quotes, truncated output
    3. coercion helpers (clamp_number / choice / text / str_list) - validate fields
    4. caller falls back to demo data if nothing usable is returned
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional


def _strip_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    return match.group(1).strip() if match else text.strip()


def _slice_object(text: str) -> Optional[str]:
    """Return the first balanced {...} block (or the unfinished tail if truncated)."""
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _repair(text: str) -> str:
    """Best-effort repair of common LLM JSON mistakes."""
    fixed = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    fixed = re.sub(r"\bTrue\b", "true", fixed)
    fixed = re.sub(r"\bFalse\b", "false", fixed)
    fixed = re.sub(r"\bNone\b", "null", fixed)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)  # trailing commas

    # Close anything left open (truncated responses).
    stack: List[str] = []
    in_str, escaped = False, False
    for ch in fixed:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    if in_str:
        fixed += '"'
    fixed = re.sub(r",\s*$", "", fixed.rstrip())
    return fixed + "".join(reversed(stack))


def extract_json(text: Any) -> Optional[Dict[str, Any]]:
    """Return a dict parsed from model text, or None if impossible. Never raises."""
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = _strip_fences(text)
    candidates = [cleaned]
    sliced = _slice_object(cleaned)
    if sliced:
        candidates.append(sliced)
        candidates.append(_repair(sliced))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# ----------------------------- field validators -----------------------------
def clamp_number(value: Any, low: float, high: float, default: float) -> float:
    """Convert to float and clamp into [low, high]; fall back to default."""
    try:
        if isinstance(value, str):
            value = re.sub(r"[^\d.\-]", "", value)
        number = float(value)
        if number != number:  # NaN
            return default
        return max(low, min(high, number))
    except (TypeError, ValueError):
        return default


def choice(value: Any, options: Iterable[str], default: str) -> str:
    """Case-insensitive match against allowed options."""
    if isinstance(value, str):
        wanted = value.strip().lower().replace("_", " ")
        for option in options:
            if option.lower() == wanted:
                return option
    return default


def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    result = str(value).strip()
    return result or default


def str_list(value: Any, limit: int = 12) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}
