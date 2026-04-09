from typing import Protocol

from app.models import AgentDefinition


class AgentService(Protocol):
    async def create_agent(self, definition: AgentDefinition) -> AgentDefinition:
        """Create or update an agent definition."""

    async def get_agent(self, agent_id: str) -> AgentDefinition | None:
        """Fetch an agent definition by ID."""
