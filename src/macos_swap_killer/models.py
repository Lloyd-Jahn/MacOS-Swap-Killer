from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DecisionAction(str, Enum):
    TERMINATE = "TERMINATE"
    ASK_CONFIRM = "ASK_CONFIRM"
    IGNORE = "IGNORE"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SwapInfo(BaseModel):
    used_gib: float | None = None
    total_gib: float | None = None
    free_gib: float | None = None
    source: str
    raw: str = ""
    memory_free_percent: int | None = None


class TrendInfo(BaseModel):
    window_sec: int
    sample_count: int = 0
    first_used_gib: float | None = None
    latest_used_gib: float | None = None
    growth_gib: float = 0.0
    triggered: bool = False
    reason: str = ""


class ProcessInfo(BaseModel):
    pid: int
    ppid: int | None = None
    user: str | None = None
    name: str
    exe: str | None = None
    cmdline: list[str] = Field(default_factory=list)
    rss_bytes: int = 0
    memory_percent: float = 0.0
    create_time: float | None = None
    status: str | None = None
    parent_name: str | None = None
    is_gui_main: bool = False
    executable_category: str = "unknown"

    @property
    def rss_mb(self) -> float:
        return self.rss_bytes / 1024 / 1024


class ProcessSummary(BaseModel):
    pid: int
    ppid: int | None
    user: str | None
    name: str
    parent_name: str | None
    rss_mb: float
    memory_percent: float
    executable_category: str
    is_gui_main: bool
    app_family: str | None = None
    playbook_role: str | None = None
    playbook_recommendation: str | None = None
    playbook_reason: str | None = None
    redacted_cmdline: list[str]


class LLMDecision(BaseModel):
    pid: int
    process_name: str
    action: DecisionAction
    risk: RiskLevel
    reason: str
    expected_memory_mb: float | None = None


class LLMResponse(BaseModel):
    overall_risk: RiskLevel
    decisions: list[LLMDecision] = Field(default_factory=list)


class ActionResult(BaseModel):
    pid: int
    process_name: str
    action: str
    status: str
    reason: str
    dry_run: bool


class IncidentResult(BaseModel):
    triggered: bool
    swap: SwapInfo
    dry_run: bool
    message: str
    trigger_reason: str = ""
    trend: TrendInfo | None = None
    decisions: list[LLMDecision] = Field(default_factory=list)
    actions: list[ActionResult] = Field(default_factory=list)
    vetoes: list[dict[str, Any]] = Field(default_factory=list)
