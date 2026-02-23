from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_KEY_SCOPES = [
    "search:read",
    "chat:write",
    "embeddings:write",
    "memory:read",
    "memory:write",
    "agents:run",
    "usage:read",
    "cron:read",
    "cron:write",
    "webhooks:write",
    "webhooks:read",
    "pages:write",
    "studio:write",
]


class GatewayErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class GatewayErrorResponse(BaseModel):
    error: GatewayErrorDetail


class GatewayAPIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: List[str] = Field(default_factory=lambda: DEFAULT_KEY_SCOPES.copy())
    rpm_limit: int = Field(default=120, ge=1, le=10_000)
    burst_limit: int = Field(default=60, ge=1, le=10_000)


class GatewayAPIKeyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    scopes: Optional[List[str]] = None
    rpm_limit: Optional[int] = Field(default=None, ge=1, le=10_000)
    burst_limit: Optional[int] = Field(default=None, ge=1, le=10_000)
    status: Optional[Literal["active", "revoked"]] = None


class GatewayAPIKeyOut(BaseModel):
    key_id: str
    name: str
    scopes: List[str]
    rpm_limit: int
    burst_limit: int
    status: Literal["active", "revoked"]
    secret_prefix: str
    created_at: str
    updated_at: str


class GatewayAPIKeyCreateResponse(BaseModel):
    api_key: str
    key: GatewayAPIKeyOut


class GatewaySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class GatewaySearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    content: str
    rank: int


class GatewaySearchResponse(BaseModel):
    status: Literal["success"] = "success"
    query: str
    results: List[GatewaySearchResult]
    citations: List[str]


class GatewayChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class GatewayChatCompletionsRequest(BaseModel):
    model: Optional[str] = None
    messages: List[GatewayChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: bool = False


class GatewayChatChoiceMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class GatewayChatChoice(BaseModel):
    index: int
    message: GatewayChatChoiceMessage
    finish_reason: Literal["stop"] = "stop"


class GatewayUsageStats(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GatewayChatCompletionsResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[GatewayChatChoice]
    usage: GatewayUsageStats


class GatewayEmbeddingsRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = None


class GatewayEmbeddingData(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: List[float]


class GatewayEmbeddingsResponse(BaseModel):
    object: Literal["list"] = "list"
    model: str
    data: List[GatewayEmbeddingData]
    usage: Dict[str, int]


class GatewayMemoryWriteRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = Field(default="api_v1", min_length=1)
    category: str = Field(default="general", min_length=1)


class GatewayMemoryReadRequest(BaseModel):
    category: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)


class GatewayMemorySearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class GatewayMemoryItem(BaseModel):
    id: str
    text: str
    category: Optional[str] = None
    source: Optional[str] = None
    score: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GatewayMemoryResponse(BaseModel):
    status: str
    count: int
    memories: List[GatewayMemoryItem]


class GatewayAgentRunRequest(BaseModel):
    query: str = Field(min_length=1)
    wait_for_completion: bool = True


class GatewayAgentRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "completed", "failed"]
    query: str
    result: Optional[Dict[str, Any]] = None


class GatewayCronJobCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    cron: str = Field(min_length=5, max_length=100)
    agent_type: str = Field(default="PlannerAgent", min_length=1)
    query: str = Field(min_length=1)


class GatewayCronJobOut(BaseModel):
    id: str
    name: str
    cron_expression: str
    agent_type: str
    query: str
    enabled: bool
    status: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_output: Optional[str] = None


class GatewayWebhookSubscriptionCreateRequest(BaseModel):
    target_url: str = Field(min_length=1)
    event_types: List[str] = Field(min_length=1)
    secret: Optional[str] = None
    active: bool = True


class GatewayWebhookSubscriptionOut(BaseModel):
    id: str
    target_url: str
    event_types: List[str]
    active: bool
    secret_prefix: str
    created_at: str


class GatewayWebhookTriggerRequest(BaseModel):
    event_type: str = Field(min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


class GatewayWebhookTriggerResponse(BaseModel):
    status: Literal["queued"] = "queued"
    queued_deliveries: int


class GatewayWebhookInboundRequest(BaseModel):
    event_type: str = Field(min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


class GatewayWebhookInboundResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    source: str
    trace_id: str
    queued_deliveries: int


class GatewayWebhookDispatchRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    max_attempts: int = Field(default=3, ge=1, le=20)
    base_backoff_seconds: int = Field(default=5, ge=1, le=3600)


class GatewayWebhookDispatchResponse(BaseModel):
    status: Literal["completed"] = "completed"
    trace_id: str
    scanned: int
    delivered: int
    retried: int
    dead_lettered: int


class GatewayWebhookDeliveryOut(BaseModel):
    delivery_id: str
    subscription_id: str
    target_url: str
    event_type: str
    status: Literal["queued", "retry_pending", "delivered", "dead_letter"]
    attempt: int
    timestamp: str
    updated_at: str
    last_error: Optional[str] = None
    next_attempt_at: Optional[str] = None


class GatewayWebhookReplayResponse(BaseModel):
    status: Literal["requeued"] = "requeued"
    trace_id: str
    delivery_id: str


class GatewayPageGenerateRequest(BaseModel):
    query: str = Field(min_length=1)
    template: Optional[str] = None
    oracle_limit: int = Field(default=5, ge=1, le=20)


class GatewayPageGenerateResponse(BaseModel):
    status: Literal["success"] = "success"
    trace_id: str
    page_id: str
    query: str
    template: Optional[str]
    title: str
    summary: str
    citations: List[str]
    artifact: Dict[str, Any]


class GatewayStudioGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    template: Optional[str] = None
    oracle_limit: int = Field(default=5, ge=1, le=20)


class GatewayStudioGenerateResponse(BaseModel):
    status: Literal["success"] = "success"
    trace_id: str
    artifact_id: str
    artifact_type: Literal["slides", "document", "sheet"]
    title: str
    outline: Dict[str, Any]
    citations: List[str]


class GatewayUsageResponse(BaseModel):
    month: str
    key_id: str
    requests: int
    latency_ms_total: float
    latency_ms_avg: float
    status_counts: Dict[str, int]
    endpoints: Dict[str, int]
    units: int


class GatewayUsageAllResponse(BaseModel):
    month: str
    by_key: Dict[str, GatewayUsageResponse]


class GatewayEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")
