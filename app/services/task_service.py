from typing import Protocol

from app.models import AgentTask


class TaskService(Protocol):
    async def create_task(self, task: AgentTask) -> AgentTask:
        """Create a new task for execution."""

    async def get_task(self, task_id: str) -> AgentTask | None:
        """Retrieve a task by ID."""

    async def approve_task(self, task_id: str, approver_id: str) -> AgentTask:
        """Approve a task waiting for manual validation."""
