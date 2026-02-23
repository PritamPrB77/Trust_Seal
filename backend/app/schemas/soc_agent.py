from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high", "critical"]
RootCauseLabel = Literal[
    "environmental_noise",
    "firmware_issue",
    "possible_intrusion",
    "misconfiguration",
    "hardware_degradation",
]


class DeviceLogEntry(BaseModel):
    timestamp: Optional[datetime] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    shock: Optional[float] = None
    light_exposure: Optional[bool] = None
    tilt_angle: Optional[float] = None


class SocAssistRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(min_length=1, max_length=128)
    device_uid: Optional[str] = Field(default=None, max_length=128)
    shipment_id: Optional[str] = Field(default=None, max_length=128)
    logs: List[DeviceLogEntry] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=30)


class RootCauseHypothesis(BaseModel):
    cause: RootCauseLabel
    probability: float = Field(ge=0.0, le=1.0)
    rationale: str


class HistoricalIncident(BaseModel):
    incident_id: str
    summary: str
    root_cause: str
    resolution: str
    risk_level: RiskLevel
    created_at: Optional[datetime] = None


class HistoricalMemoryMatch(BaseModel):
    memory_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    summary: str
    root_cause: str
    resolution: str
    risk_level: RiskLevel
    created_at: Optional[datetime] = None


class SocInvestigationResponse(BaseModel):
    investigation_id: str
    issue_summary: str
    investigation_steps_taken: List[str] = Field(default_factory=list)
    context_retrieved: List[str] = Field(default_factory=list)
    historical_memory_matches: List[HistoricalMemoryMatch] = Field(default_factory=list)
    root_cause_analysis: List[RootCauseHypothesis] = Field(default_factory=list)
    risk_level: RiskLevel = "medium"
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_action: List[str] = Field(default_factory=list)
    tool_trace: List[str] = Field(default_factory=list)
    raw_output: Optional[str] = None


class VectorRetrieverToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=30)


class LiveDeviceLogAnalyzerToolInput(BaseModel):
    focus: str = Field(
        default="Analyze live telemetry against baseline and return anomalies with deviation score.",
        max_length=500,
    )
    logs: List[DeviceLogEntry] = Field(default_factory=list)


class HistoricalIncidentSearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class LongTermMemorySearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RootCauseAnalyzerToolInput(BaseModel):
    findings: str = Field(min_length=1, max_length=8000)


class RiskScoringToolInput(BaseModel):
    findings: str = Field(min_length=1, max_length=8000)
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ParsedSocOutput(BaseModel):
    issue_summary: str = ""
    investigation_steps_taken: List[str] = Field(default_factory=list)
    context_retrieved: List[str] = Field(default_factory=list)
    historical_memory_matches: List[HistoricalMemoryMatch] = Field(default_factory=list)
    root_cause_analysis: List[RootCauseHypothesis] = Field(default_factory=list)
    risk_level: RiskLevel = "medium"
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_action: List[str] = Field(default_factory=list)


class ToolPayload(BaseModel):
    ok: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class InvestigationAuditRecord(BaseModel):
    investigation_id: str
    session_id: str
    device_id: Optional[str] = None
    anomaly_type: str
    tools_used: List[str] = Field(default_factory=list)
    reasoning_steps: List[str] = Field(default_factory=list)
    root_cause_conclusion: str
    risk_level: RiskLevel
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime


class InvestigationAuditListResponse(BaseModel):
    records: List[InvestigationAuditRecord] = Field(default_factory=list)
