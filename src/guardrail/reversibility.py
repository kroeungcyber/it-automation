from __future__ import annotations

from src.guardrail._patterns import DESTRUCTIVE_CMD_RE as _DESTRUCTIVE_CMD_FRAGMENTS
from src.guardrail.models import ActionPlan, ActionType, DryRunPreview

# These action types are structurally irreversible — agent preview is ignored
_ALWAYS_IRREVERSIBLE = {ActionType.VAULT_WRITE, ActionType.AD_DEPROVISION}


class ReversibilityChecker:
    def is_reversible(self, plan: ActionPlan, preview: DryRunPreview) -> bool:
        if plan.action_type in _ALWAYS_IRREVERSIBLE:
            return False
        if plan.action_type == ActionType.SSH_EXEC:
            command = plan.parameters.get("command", "")
            if _DESTRUCTIVE_CMD_FRAGMENTS.search(command):
                return False
        return preview.estimated_reversible
