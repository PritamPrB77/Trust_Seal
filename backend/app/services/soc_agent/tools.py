from __future__ import annotations

import json
import logging
import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.device import Device
from ...models.sensor_log import SensorLog
from ...models.shipment import Shipment
from ...schemas.soc_agent import (
    DeviceLogEntry,
    HistoricalIncidentSearchToolInput,
    LiveDeviceLogAnalyzerToolInput,
    LongTermMemorySearchToolInput,
    RiskScoringToolInput,
    RootCauseAnalyzerToolInput,
    VectorRetrieverToolInput,
)
from ..chat_service import chat_service
from .memory import SocMemoryStore, soc_memory_store

logger = logging.getLogger(__name__)

ROOT_CAUSES: Sequence[str] = (
    "environmental_noise",
    "firmware_issue",
    "possible_intrusion",
    "misconfiguration",
    "hardware_degradation",
)


def _tool_payload(data: Dict[str, Any], ok: bool = True, error: Optional[str] = None) -> str:
    return json.dumps({"ok": ok, "data": data, "error": error}, ensure_ascii=True)


def _mean_std(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0}
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
    return {"mean": mean, "std": math.sqrt(variance)}


def _parse_uuid(value: Optional[str]) -> Optional[UUID]:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _detect_db_dialect(db: Session) -> str:
    bind = db.get_bind()
    return str(bind.dialect.name) if bind else ""


def _ensure_incident_table(db: Session) -> None:
    dialect = _detect_db_dialect(db)
    if dialect == "postgresql":
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS incident_records (
                    id BIGSERIAL PRIMARY KEY,
                    device_uid TEXT NULL,
                    shipment_id TEXT NULL,
                    summary TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        db.execute(
            text(
                "CREATE INDEX IF NOT EXISTS incident_records_created_idx "
                "ON incident_records (created_at DESC)"
            )
        )
    else:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS incident_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_uid TEXT NULL,
                    shipment_id TEXT NULL,
                    summary TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.execute(
            text(
                "CREATE INDEX IF NOT EXISTS incident_records_created_idx "
                "ON incident_records (created_at DESC)"
            )
        )
    db.commit()


def _extract_probabilities_from_text(findings: str) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    lowered = findings.lower()

    for cause in ROOT_CAUSES:
        pattern = re.compile(
            rf"{re.escape(cause)}(?:[^0-9]{{0,80}})(0(?:\.\d+)?|1(?:\.0+)?)"
        )
        match = pattern.search(lowered)
        if not match:
            continue
        try:
            scores[cause] = max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            continue

    return scores


class SocToolFactory:
    def __init__(
        self,
        db: Session,
        top_k: int,
        logs: Sequence[DeviceLogEntry],
        device_uid: Optional[str],
        shipment_id: Optional[str],
        memory_store: Optional[SocMemoryStore] = None,
    ) -> None:
        self.db = db
        self.top_k = max(1, min(top_k, 30))
        self.logs = list(logs)
        self.device_uid = device_uid
        self.shipment_id = shipment_id
        self.memory_store = memory_store or soc_memory_store

    def _fetch_baseline_logs(self) -> List[SensorLog]:
        query = self.db.query(SensorLog)
        shipment_uuid = _parse_uuid(self.shipment_id)

        if shipment_uuid:
            query = query.filter(SensorLog.shipment_id == shipment_uuid)
        elif self.device_uid:
            query = (
                query.join(Shipment, Shipment.id == SensorLog.shipment_id)
                .join(Device, Device.id == Shipment.device_id)
                .filter(Device.device_uid == self.device_uid)
            )

        return (
            query.order_by(SensorLog.recorded_at.desc())
            .limit(settings.SOC_AGENT_BASELINE_WINDOW)
            .all()
        )

    def build(self) -> List[BaseTool]:
        @tool(
            "vector_knowledge_retriever",
            args_schema=VectorRetrieverToolInput,
            return_direct=False,
        )
        def vector_knowledge_retriever(query: str, top_k: int = 8) -> str:
            """
            Retrieve top-k semantically similar records from the pgvector-backed RAG store.
            Returns source content, similarity score, and metadata.
            """

            try:
                k = max(1, min(top_k or self.top_k, 30))
                chat_service.refresh_index(self.db)
                chunks = chat_service._search_similar_chunks(self.db, query, k)  # noqa: SLF001
                results = [
                    {
                        "doc_id": chunk.doc_id,
                        "source_type": chunk.source_type,
                        "source_id": chunk.source_id,
                        "score": round(chunk.score, 4),
                        "content": chunk.content,
                        "metadata": chunk.metadata,
                    }
                    for chunk in chunks
                ]
                return _tool_payload(
                    {"query": query, "top_k": k, "match_count": len(results), "matches": results}
                )
            except Exception as exc:
                logger.exception("vector_knowledge_retriever failed")
                return _tool_payload({}, ok=False, error=f"Vector retrieval failed: {exc}")

        @tool(
            "live_device_log_analyzer",
            args_schema=LiveDeviceLogAnalyzerToolInput,
            return_direct=False,
        )
        def live_device_log_analyzer(
            focus: str = "Analyze live telemetry against baseline and return anomalies with deviation score.",
            logs: Optional[List[DeviceLogEntry]] = None,
        ) -> str:
            """
            Analyze incoming live telemetry for anomalies and quantify deviation against historical baseline.
            """

            _ = focus
            active_logs = logs or self.logs
            if not active_logs:
                return _tool_payload(
                    {
                        "summary": "No live logs were provided for anomaly analysis.",
                        "anomaly_count": 0,
                        "deviation_score": 0.0,
                        "baseline_window_size": 0,
                        "anomalies": [],
                    }
                )

            try:
                baseline = self._fetch_baseline_logs()
                baseline_metrics: Dict[str, List[float]] = defaultdict(list)
                baseline_light_values: List[float] = []

                for entry in baseline:
                    for metric in ("temperature", "humidity", "shock", "tilt_angle"):
                        raw = getattr(entry, metric, None)
                        value = _safe_float(raw)
                        if value is not None:
                            baseline_metrics[metric].append(value)
                    if entry.light_exposure is not None:
                        baseline_light_values.append(1.0 if entry.light_exposure else 0.0)

                stats = {metric: _mean_std(values) for metric, values in baseline_metrics.items()}
                light_baseline = (
                    sum(baseline_light_values) / len(baseline_light_values)
                    if baseline_light_values
                    else 0.0
                )

                anomalies: List[Dict[str, Any]] = []
                z_scores: List[float] = []
                measured_points = 0

                for idx, log_entry in enumerate(active_logs):
                    payload = (
                        log_entry.model_dump(mode="json")
                        if isinstance(log_entry, DeviceLogEntry)
                        else dict(log_entry)
                    )

                    for metric in ("temperature", "humidity", "shock", "tilt_angle"):
                        value = _safe_float(payload.get(metric))
                        if value is None:
                            continue

                        measured_points += 1
                        metric_stats = stats.get(metric) or {"mean": value, "std": 0.0}
                        mean = metric_stats["mean"]
                        std = metric_stats["std"]

                        if std > 1e-6:
                            z_score = abs(value - mean) / std
                        else:
                            z_score = abs(value - mean) / (abs(mean) + 1e-6)

                        z_scores.append(z_score)
                        if z_score >= 2.5:
                            anomalies.append(
                                {
                                    "log_index": idx,
                                    "timestamp": payload.get("timestamp"),
                                    "metric": metric,
                                    "value": value,
                                    "baseline_mean": round(mean, 3),
                                    "baseline_std": round(std, 3),
                                    "z_score": round(z_score, 3),
                                }
                            )

                    light_value = payload.get("light_exposure")
                    if light_value is True and light_baseline < 0.2:
                        anomalies.append(
                            {
                                "log_index": idx,
                                "timestamp": payload.get("timestamp"),
                                "metric": "light_exposure",
                                "value": True,
                                "baseline_true_ratio": round(light_baseline, 3),
                                "z_score": 3.0,
                            }
                        )
                        measured_points += 1
                        z_scores.append(3.0)

                anomaly_count = len(anomalies)
                anomaly_ratio = anomaly_count / max(measured_points, 1)
                avg_z = sum(z_scores) / max(len(z_scores), 1)
                deviation_score = min(1.0, (avg_z / 5.0) + (0.6 * anomaly_ratio))

                summary = (
                    "Significant anomaly behavior detected."
                    if deviation_score >= 0.6
                    else "Moderate telemetry drift detected."
                    if deviation_score >= 0.3
                    else "Telemetry appears within normal variance."
                )

                return _tool_payload(
                    {
                        "summary": summary,
                        "device_uid": self.device_uid,
                        "shipment_id": self.shipment_id,
                        "baseline_window_size": len(baseline),
                        "anomaly_count": anomaly_count,
                        "anomaly_ratio": round(anomaly_ratio, 4),
                        "deviation_score": round(deviation_score, 4),
                        "anomalies": anomalies[:100],
                    }
                )
            except Exception as exc:
                logger.exception("live_device_log_analyzer failed")
                return _tool_payload({}, ok=False, error=f"Live log analysis failed: {exc}")

        @tool(
            "historical_incident_search",
            args_schema=HistoricalIncidentSearchToolInput,
            return_direct=False,
        )
        def historical_incident_search(
            query: str,
            limit: int = settings.SOC_AGENT_INCIDENT_SEARCH_LIMIT,
        ) -> str:
            """
            Search historical incident records and return root cause and resolution patterns.
            """

            try:
                _ensure_incident_table(self.db)
                search_limit = max(1, min(limit, 20))
                dialect = _detect_db_dialect(self.db)
                like_value = f"%{query}%"

                if dialect == "postgresql":
                    rows = self.db.execute(
                        text(
                            """
                            SELECT id, summary, root_cause, resolution, risk_level, created_at
                            FROM incident_records
                            WHERE summary ILIKE :q
                               OR root_cause ILIKE :q
                               OR resolution ILIKE :q
                            ORDER BY created_at DESC
                            LIMIT :k
                            """
                        ),
                        {"q": like_value, "k": search_limit},
                    ).mappings()
                else:
                    rows = self.db.execute(
                        text(
                            """
                            SELECT id, summary, root_cause, resolution, risk_level, created_at
                            FROM incident_records
                            WHERE LOWER(summary) LIKE LOWER(:q)
                               OR LOWER(root_cause) LIKE LOWER(:q)
                               OR LOWER(resolution) LIKE LOWER(:q)
                            ORDER BY created_at DESC
                            LIMIT :k
                            """
                        ),
                        {"q": like_value, "k": search_limit},
                    ).mappings()

                incidents = [
                    {
                        "incident_id": str(row.get("id")),
                        "summary": str(row.get("summary") or ""),
                        "root_cause": str(row.get("root_cause") or ""),
                        "resolution": str(row.get("resolution") or ""),
                        "risk_level": str(row.get("risk_level") or "medium").lower(),
                        "created_at": (
                            row.get("created_at").isoformat()
                            if hasattr(row.get("created_at"), "isoformat")
                            else str(row.get("created_at") or "")
                        ),
                    }
                    for row in rows
                ]
                return _tool_payload(
                    {
                        "query": query,
                        "incident_count": len(incidents),
                        "incidents": incidents,
                    }
                )
            except Exception as exc:
                logger.exception("historical_incident_search failed")
                return _tool_payload({}, ok=False, error=f"Historical incident search failed: {exc}")

        @tool(
            "long_term_incident_memory_search",
            args_schema=LongTermMemorySearchToolInput,
            return_direct=False,
        )
        def long_term_incident_memory_search(query: str, top_k: int = 5) -> str:
            """
            Search long-term self-learning incident memory for similar anomalies.
            Returns prior incident patterns with similarity scores.
            """

            try:
                matches = self.memory_store.search_long_term_memory(
                    db=self.db,
                    query=query,
                    top_k=top_k,
                )
                return _tool_payload(
                    {
                        "query": query,
                        "match_count": len(matches),
                        "matches": [item.model_dump(mode="json") for item in matches],
                    }
                )
            except Exception as exc:
                logger.exception("long_term_incident_memory_search failed")
                return _tool_payload({}, ok=False, error=f"Long-term memory search failed: {exc}")

        @tool(
            "root_cause_analyzer",
            args_schema=RootCauseAnalyzerToolInput,
            return_direct=False,
        )
        def root_cause_analyzer(findings: str) -> str:
            """
            Estimate root-cause probabilities for environmental noise, firmware issue,
            possible intrusion, misconfiguration, and hardware degradation.
            """

            text_blob = findings.lower()
            scores: Dict[str, float] = {cause: 1.0 for cause in ROOT_CAUSES}
            rationale: Dict[str, List[str]] = defaultdict(list)

            keyword_map: Dict[str, Sequence[str]] = {
                "environmental_noise": ("weather", "noise", "transient", "spike", "brief"),
                "firmware_issue": ("firmware", "patch", "rollback", "version", "crc", "bootloop"),
                "possible_intrusion": (
                    "intrusion",
                    "unauthorized",
                    "tamper",
                    "biometric false",
                    "credential",
                    "compromised",
                ),
                "misconfiguration": ("config", "threshold", "calibration", "setpoint", "policy"),
                "hardware_degradation": ("degradation", "wear", "sensor drift", "fault", "battery", "aging"),
            }

            for cause, keywords in keyword_map.items():
                for token in keywords:
                    if token in text_blob:
                        scores[cause] += 0.9
                        rationale[cause].append(f"Matched indicator: '{token}'.")

            deviation_match = re.search(r"deviation_score[^0-9]*([0-9]*\.?[0-9]+)", text_blob)
            if deviation_match:
                try:
                    deviation = float(deviation_match.group(1))
                except ValueError:
                    deviation = 0.0
                if deviation >= 0.7:
                    scores["possible_intrusion"] += 1.0
                    scores["hardware_degradation"] += 0.8
                    rationale["possible_intrusion"].append("High deviation score suggests hostile or abnormal behavior.")
                    rationale["hardware_degradation"].append("Persistent high deviation can indicate sensor wear.")
                elif deviation >= 0.4:
                    scores["misconfiguration"] += 0.7
                    rationale["misconfiguration"].append("Moderate sustained drift aligns with configuration drift.")
                else:
                    scores["environmental_noise"] += 0.5
                    rationale["environmental_noise"].append("Low deviation aligns with transient environmental variance.")

            anomaly_match = re.search(r"anomaly_count[^0-9]*([0-9]+)", text_blob)
            if anomaly_match:
                anomalies = int(anomaly_match.group(1))
                if anomalies >= 8:
                    scores["possible_intrusion"] += 1.0
                    scores["firmware_issue"] += 0.6
                elif anomalies >= 3:
                    scores["misconfiguration"] += 0.5
                    scores["hardware_degradation"] += 0.4

            total = sum(scores.values())
            normalized = {
                cause: (score / total if total > 0 else 1.0 / len(ROOT_CAUSES))
                for cause, score in scores.items()
            }

            ranked = sorted(normalized.items(), key=lambda item: item[1], reverse=True)
            root_causes = [
                {
                    "cause": cause,
                    "probability": round(probability, 4),
                    "rationale": " ".join(rationale[cause]) or "No strong direct evidence; assigned baseline probability.",
                }
                for cause, probability in ranked
            ]

            return _tool_payload({"root_causes": root_causes})

        @tool(
            "risk_scoring_engine",
            args_schema=RiskScoringToolInput,
            return_direct=False,
        )
        def risk_scoring_engine(findings: str, anomaly_score: float = 0.0) -> str:
            """
            Assign a consolidated SOC risk level: low, medium, high, or critical.
            """

            try:
                clue = findings.lower()
                extracted = _extract_probabilities_from_text(findings)
                intrusion_prob = extracted.get("possible_intrusion", 0.0)
                firmware_prob = extracted.get("firmware_issue", 0.0)
                hardware_prob = extracted.get("hardware_degradation", 0.0)
                misconfig_prob = extracted.get("misconfiguration", 0.0)

                incident_count = 0
                incident_match = re.search(r"incident_count[^0-9]*([0-9]+)", clue)
                if incident_match:
                    incident_count = int(incident_match.group(1))

                score = 0.0
                score += max(0.0, min(1.0, anomaly_score)) * 45.0
                score += intrusion_prob * 30.0
                score += firmware_prob * 12.0
                score += hardware_prob * 8.0
                score += misconfig_prob * 5.0
                score += min(incident_count, 10) * 1.5

                if "compromised" in clue or "unauthorized" in clue or "tamper" in clue:
                    score += 12.0
                if "biometric false" in clue:
                    score += 8.0

                score = max(0.0, min(100.0, score))
                if score >= 80:
                    risk_level = "critical"
                elif score >= 60:
                    risk_level = "high"
                elif score >= 35:
                    risk_level = "medium"
                else:
                    risk_level = "low"

                return _tool_payload(
                    {
                        "risk_level": risk_level,
                        "risk_score": round(score, 2),
                        "inputs": {
                            "anomaly_score": round(float(anomaly_score), 4),
                            "intrusion_probability": round(intrusion_prob, 4),
                            "firmware_probability": round(firmware_prob, 4),
                            "hardware_probability": round(hardware_prob, 4),
                            "misconfiguration_probability": round(misconfig_prob, 4),
                            "incident_count": incident_count,
                        },
                    }
                )
            except Exception as exc:
                logger.exception("risk_scoring_engine failed")
                return _tool_payload({}, ok=False, error=f"Risk scoring failed: {exc}")

        return [
            vector_knowledge_retriever,
            live_device_log_analyzer,
            historical_incident_search,
            long_term_incident_memory_search,
            root_cause_analyzer,
            risk_scoring_engine,
        ]
