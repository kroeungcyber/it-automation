from __future__ import annotations

from abc import ABC, abstractmethod

from src.guardrail.models import ActionPlan, DryRunPreview


class ExecutionAgent(ABC):
    """Interface all execution agents must implement. Safety logic lives in the pipeline, not here."""

    @property
    @abstractmethod
    def agent_type(self) -> str: ...

    @abstractmethod
    def dry_run(self, plan: ActionPlan) -> DryRunPreview: ...

    @abstractmethod
    def execute(self, plan: ActionPlan) -> dict: ...

    @abstractmethod
    def rollback(self, action_plan_id: str) -> bool:
        """Return True if rollback succeeded, False if it failed."""
        ...


class DryRunExecutor:
    def __init__(self, agents: dict[str, ExecutionAgent]) -> None:
        self._agents = agents  # keyed by ActionType.value

    def run(self, plan: ActionPlan) -> DryRunPreview:
        agent = self._agents.get(plan.action_type.value)
        if agent is None:
            return DryRunPreview(
                action_plan_id=str(plan.id),
                agent="unknown",
                would_affect=[f"Unknown action type: {plan.action_type.value}"],
                estimated_reversible=False,
                raw_preview=f"No agent registered for action type '{plan.action_type.value}' — treating as irreversible",
            )
        return agent.dry_run(plan)
