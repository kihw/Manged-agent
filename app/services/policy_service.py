from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyService(Protocol):
    async def evaluate_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        payload: dict[str, Any],
    ) -> PolicyDecision:
        """Validate whether a tool invocation is allowed."""

    async def evaluate_budget(self, task_id: str) -> PolicyDecision:
        """Validate task budget constraints before continuing execution."""
