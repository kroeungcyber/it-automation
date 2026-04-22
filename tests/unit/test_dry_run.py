import pytest
from src.guardrail.models import ActionPlan, ActionRequester, ActionType, DryRunPreview
from src.guardrail.dry_run import DryRunExecutor, ExecutionAgent

_REQUESTER = ActionRequester(user_id="U1", org_role="admin", task_source="cli")


def _plan(action_type: ActionType) -> ActionPlan:
    return ActionPlan(
        task_id="00000000-0000-0000-0000-000000000001",
        action_type=action_type,
        requested_by=_REQUESTER,
    )


class FakeSSHAgent(ExecutionAgent):
    @property
    def agent_type(self) -> str:
        return ActionType.SSH_EXEC.value

    def dry_run(self, plan: ActionPlan) -> DryRunPreview:
        return DryRunPreview(
            action_plan_id=str(plan.id),
            agent=self.agent_type,
            would_affect=["server-01: run command"],
            estimated_reversible=True,
            raw_preview="echo test",
        )

    def execute(self, plan: ActionPlan) -> dict:
        return {"exit_code": 0}

    def rollback(self, action_plan_id: str) -> bool:
        return True


def test_dry_run_dispatches_to_correct_agent():
    agent = FakeSSHAgent()
    executor = DryRunExecutor(agents={ActionType.SSH_EXEC.value: agent})
    plan = _plan(ActionType.SSH_EXEC)
    preview = executor.run(plan)
    assert preview.agent == ActionType.SSH_EXEC.value
    assert preview.action_plan_id == str(plan.id)


def test_dry_run_unknown_agent_returns_safe_fallback():
    executor = DryRunExecutor(agents={})
    plan = _plan(ActionType.VAULT_WRITE)
    preview = executor.run(plan)
    assert preview.agent == "unknown"
    assert preview.estimated_reversible is False
    assert "vault_write" in preview.raw_preview.lower() or "unknown" in preview.raw_preview.lower()


def test_execution_agent_interface_enforced():
    with pytest.raises(TypeError):
        class BadAgent(ExecutionAgent):
            pass
        BadAgent()


def test_dry_run_preview_would_affect_populated():
    agent = FakeSSHAgent()
    executor = DryRunExecutor(agents={ActionType.SSH_EXEC.value: agent})
    plan = _plan(ActionType.SSH_EXEC)
    preview = executor.run(plan)
    assert len(preview.would_affect) > 0
