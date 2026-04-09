from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class AgentTask:
    task_id: str
    agent_id: str
    goal: str
    status: str


class TaskService(Protocol):
    async def create_task(self, task: AgentTask) -> AgentTask:
        """Create a new task for execution."""

    async def get_task(self, task_id: str) -> AgentTask | None:
        """Retrieve a task by ID."""

    async def approve_task(self, task_id: str, approver_id: str) -> AgentTask:
        """Approve a task waiting for manual validation."""
