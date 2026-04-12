# src/router/rules.py
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class RuleMatch(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class RuleEngine:
    def __init__(
        self,
        local_patterns: list[re.Pattern],
        cloud_patterns: list[re.Pattern],
    ) -> None:
        self._local = local_patterns
        self._cloud = cloud_patterns

    @classmethod
    def from_yaml(cls, path: str) -> "RuleEngine":
        data = yaml.safe_load(Path(path).read_text())
        local_patterns = [
            re.compile(rule["pattern"], re.IGNORECASE)
            for rule in data.get("local", [])
        ]
        cloud_patterns = [
            re.compile(rule["pattern"], re.IGNORECASE)
            for rule in data.get("cloud", [])
        ]
        return cls(local_patterns, cloud_patterns)

    def classify(self, text: str) -> Optional[RuleMatch]:
        """Return LOCAL, CLOUD, or None (ambiguous — caller applies fail-safe)."""
        for pattern in self._local:
            if pattern.search(text):
                return RuleMatch.LOCAL
        for pattern in self._cloud:
            if pattern.search(text):
                return RuleMatch.CLOUD
        return None
