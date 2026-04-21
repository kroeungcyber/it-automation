from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from src.guardrail.models import ActionPlan, ActionType, RiskTier


@dataclass
class ClassificationResult:
    tier: RiskTier
    method: str  # "rules" | "heuristics" | "default"
    reason: str


from src.guardrail._patterns import DESTRUCTIVE_CMD_RE as _DESTRUCTIVE_CMD_RE


def _escalate(tier: RiskTier) -> RiskTier:
    if tier == RiskTier.LOW:
        return RiskTier.MEDIUM
    return RiskTier.HIGH


class RiskClassifier:
    def __init__(self, rules: dict) -> None:
        self._rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "RiskClassifier":
        data = yaml.safe_load(Path(path).read_text())
        return cls(data or {})

    def classify(self, plan: ActionPlan) -> ClassificationResult:
        result = self._apply_yaml_rules(plan)
        if result is not None:
            return result
        return self._apply_heuristics(plan)

    def _apply_yaml_rules(self, plan: ActionPlan) -> Optional[ClassificationResult]:
        for tier_name in ("high", "medium", "low"):
            for rule in self._rules.get(tier_name, []):
                if self._rule_matches(rule, plan):
                    return ClassificationResult(
                        tier=RiskTier(tier_name),
                        method="rules",
                        reason=rule.get("description", tier_name),
                    )
        return None

    def _rule_matches(self, rule: dict, plan: ActionPlan) -> bool:
        if "action_type" in rule and rule["action_type"] != plan.action_type.value:
            return False
        if "scope" in rule and rule["scope"] != plan.target.scope:
            return False
        if "target_pattern" in rule:
            if not re.search(rule["target_pattern"], plan.target.host, re.IGNORECASE):
                return False
        if "command_pattern" in rule:
            command = plan.parameters.get("command", "")
            if not re.search(rule["command_pattern"], command, re.IGNORECASE):
                return False
        return True

    def _apply_heuristics(self, plan: ActionPlan) -> ClassificationResult:
        tier = RiskTier.LOW
        reasons: list[str] = []

        if plan.target.scope == "bulk":
            tier = _escalate(tier)
            reasons.append("bulk scope")

        if plan.target.count > 10:
            tier = _escalate(tier)
            reasons.append(f"count={plan.target.count}")

        if re.search(r"prod", plan.target.host, re.IGNORECASE):
            if tier == RiskTier.LOW:
                tier = RiskTier.MEDIUM
                reasons.append("prod host")

        command = plan.parameters.get("command", "")
        if command and _DESTRUCTIVE_CMD_RE.search(command):
            tier = RiskTier.HIGH
            reasons.append("destructive command pattern")

        reason = ", ".join(reasons) if reasons else "no specific risk indicators"
        return ClassificationResult(tier=tier, method="heuristics", reason=reason)
