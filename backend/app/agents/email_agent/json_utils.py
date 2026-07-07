"""Shared helpers for parsing model JSON responses."""

from __future__ import annotations

import json
import re


def parse_json_response(text: str) -> dict:
    """Parse JSON from a model response, tolerating markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Some models wrap JSON with leading commentary — grab the outer object.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    return json.loads(cleaned)
