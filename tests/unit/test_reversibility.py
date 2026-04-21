import pytest
from src.guardrail.models import ActionPlan, ActionTarget, ActionRequester, ActionType, DryRunPreview
from src.guardrail.reversibility import ReversibilityChecker

_REQUESTER = ActionRequester(user_id="U1", org_role="admin", task_source="cli")


def _plan(action_type: ActionType, command: str = "") -> ActionPlan:
    return ActionPlan(
        task_id="00000000-0000-0000-0000-000000000001",
        action_type=action_type,
        parameters={"command": command} if command else {},
        requested_by=_REQUESTER,
    )


def _preview(estimated_reversible: bool) -> DryRunPreview:
    return DryRunPreview(
        action_plan_id="abc",
        agent="test",
        would_affect=[],
        estimated_reversible=estimated_reversible,
        raw_preview="",
    )


def test_vault_write_is_always_irreversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.VAULT_WRITE)
    assert checker.is_reversible(plan, _preview(True)) is False


def test_ad_deprovision_is_always_irreversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.AD_DEPROVISION)
    assert checker.is_reversible(plan, _preview(True)) is False


def test_ssh_with_rm_command_is_irreversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.SSH_EXEC, command="rm -rf /var/logs/old")
    assert checker.is_reversible(plan, _preview(True)) is False


def test_ssh_with_destructive_dd_is_irreversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.SSH_EXEC, command="dd if=/dev/zero of=/dev/sdb")
    assert checker.is_reversible(plan, _preview(True)) is False


def test_ssh_restart_with_reversible_preview_is_reversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.SSH_EXEC, command="systemctl restart nginx")
    assert checker.is_reversible(plan, _preview(True)) is True


def test_ssh_restart_with_irreversible_preview_is_irreversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.SSH_EXEC, command="systemctl restart nginx")
    assert checker.is_reversible(plan, _preview(False)) is False


def test_vault_read_is_reversible():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.VAULT_READ)
    assert checker.is_reversible(plan, _preview(True)) is True


def test_backup_trigger_respects_preview():
    checker = ReversibilityChecker()
    plan = _plan(ActionType.BACKUP_TRIGGER)
    assert checker.is_reversible(plan, _preview(True)) is True
    assert checker.is_reversible(plan, _preview(False)) is False
