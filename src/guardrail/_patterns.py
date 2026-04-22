# src/guardrail/_patterns.py
import re

DESTRUCTIVE_CMD_RE = re.compile(
    r"\b(rm|drop|truncate|format|mkfs|dd)\b", re.IGNORECASE
)
