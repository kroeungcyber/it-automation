# src/router/payload_scanner.py
from __future__ import annotations

import re
from enum import Enum


class ScanResult(str, Enum):
    CLEAN = "clean"
    SENSITIVE = "sensitive"


_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r'"password"\s*:\s*"[^"]+"', re.IGNORECASE),
    re.compile(r"api[_\-\s]?key\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=.]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"token\s*[=:]\s*[A-Za-z0-9\-_\.]{20,}", re.IGNORECASE),
]


class PayloadScanner:
    def scan(self, text: str) -> ScanResult:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                return ScanResult.SENSITIVE
        return ScanResult.CLEAN
