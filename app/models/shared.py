from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class McpServer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server_id: str
    name: str
    transport: str
    endpoint: str
    status: str


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_iterations: int = Field(ge=1)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_cost_usd: float = Field(ge=0)
    max_duration_sec: int = Field(ge=1)


class ApprovalRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_human_for: list[str] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    version: str
    description: str | None = None
    system_prompt: str
    tools: list[str]
    allowed_mcp_servers: list[McpServer] = Field(default_factory=list)
    policy_profile: str
    limits: Limits
    approval_rules: ApprovalRules | None = None


class AuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["api_key", "oauth", "auto"]
    user_id: str | None = None
    tenant_id: str | None = None


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    goal: str
    repo_path: str
    constraints: list[str] = Field(default_factory=list)
    auth_context: AuthContext | None = None


class TaskStep(BaseModel):
    model_config = ConfigDict(extra="allow")


class ToolExecution(BaseModel):
    model_config = ConfigDict(extra="allow")


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class Artifact(BaseModel):
    model_config = ConfigDict(extra="allow")


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    trace_id: str
    agent_id: str
    goal: str
    repo_path: str
    constraints: list[str] = Field(default_factory=list)
    auth_context: AuthContext | None = None
    status: str
    steps: list[TaskStep] = Field(default_factory=list)
    tool_executions: list[ToolExecution] = Field(default_factory=list)
    approval_requests: list[ApprovalRequest] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    result_summary: str | None = None


class OAuthCallbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    state: str
    code_verifier: str


class OAuthCallbackResponse(BaseModel):
    status: str
    message: str


class ApproveTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    approved_by: str
    comment: str | None = None


class ApprovalResponse(BaseModel):
    approval_id: str
    task_id: str
    status: str
    approved_by: str
    comment: str | None = None


class JsonObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()
