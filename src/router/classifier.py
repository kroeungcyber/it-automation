# src/router/classifier.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import structlog

from src.router.rules import RuleEngine, RuleMatch

log = structlog.get_logger()

_EXECUTION_VERBS = {"execute", "run", "restart", "stop", "start", "kill", "deploy", "install"}
# NOTE: "help" is deliberately absent. spaCy parses "help me with X" with root=help,
# and "Help me with onboarding" must fail-safe to LOCAL (security boundary).
# Do not add "help" here without updating the golden dataset in test_classifier.py.
_INFO_VERBS = {"find", "show", "get", "explain", "describe", "list", "know", "understand"}


@dataclass
class ClassificationResult:
    route: Literal["local", "cloud"]
    method: Literal["rules", "spacy", "failsafe", "scanner"]
    confidence: float = 1.0


class Classifier:
    def __init__(self, rule_engine: RuleEngine) -> None:
        self._rules = rule_engine
        self._nlp: object | None = None  # spacy.Language, lazy-loaded on first ambiguous request

    @classmethod
    def from_config(cls, rules_yaml_path: str) -> "Classifier":
        return cls(RuleEngine.from_yaml(rules_yaml_path))

    def classify(self, text: str) -> ClassificationResult:
        # Pass 1: keyword/regex rules — fast and deterministic
        rule_result = self._rules.classify(text)
        if rule_result == RuleMatch.LOCAL:
            log.debug("classifier.local", method="rules", input=text[:80])
            return ClassificationResult(route="local", method="rules", confidence=1.0)
        if rule_result == RuleMatch.CLOUD:
            log.debug("classifier.cloud", method="rules", input=text[:80])
            return ClassificationResult(route="cloud", method="rules", confidence=1.0)

        # Pass 2: spaCy heuristic — only for ambiguous cases
        spacy_route = self._spacy_classify(text)
        if spacy_route is not None:
            log.debug("classifier.spacy", route=spacy_route, input=text[:80])
            return ClassificationResult(route=spacy_route, method="spacy", confidence=0.7)

        # Fail-safe: ambiguous → LOCAL (security boundary — never route unknown to cloud)
        log.info("classifier.failsafe.local", input=text[:80])
        return ClassificationResult(route="local", method="failsafe", confidence=0.5)

    def _spacy_classify(self, text: str) -> Literal["local", "cloud"] | None:
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load("en_core_web_sm")
        doc = self._nlp(text.lower())
        root_lemmas = {token.lemma_ for token in doc if token.dep_ == "ROOT"}
        if root_lemmas & _EXECUTION_VERBS:
            return "local"
        if root_lemmas & _INFO_VERBS:
            return "cloud"
        return None
