from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.config import settings
from ...schemas.soc_agent import (
    HistoricalMemoryMatch,
    InvestigationAuditRecord,
    ParsedSocOutput,
    SocAssistRequest,
)
from ..chat_service import chat_service

logger = logging.getLogger(__name__)


def _dialect(db: Session) -> str:
    bind = db.get_bind()
    return str(bind.dialect.name) if bind else ""


def _is_postgres(db: Session) -> bool:
    return _dialect(db) == "postgresql"


def _to_json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    candidate = _to_iso(value)
    if not candidate:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return datetime.utcnow()


class SQLChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, db: Session, session_id: str) -> None:
        self._db = db
        self._session_id = session_id

    @property
    def messages(self) -> List[BaseMessage]:
        rows = self._db.execute(
            text(
                """
                SELECT message
                FROM soc_conversation_memory
                WHERE session_id = :session_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"session_id": self._session_id},
        ).fetchall()

        payloads: List[Dict[str, Any]] = []
        for row in rows:
            raw = row[0]
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    continue
            if isinstance(raw, dict):
                payloads.append(raw)
        return messages_from_dict(payloads)

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        if not messages:
            return

        if _is_postgres(self._db):
            stmt = text(
                """
                INSERT INTO soc_conversation_memory (session_id, message, created_at)
                VALUES (:session_id, CAST(:message AS jsonb), NOW())
                """
            )
        else:
            stmt = text(
                """
                INSERT INTO soc_conversation_memory (session_id, message, created_at)
                VALUES (:session_id, :message, CURRENT_TIMESTAMP)
                """
            )

        for message in messages:
            self._db.execute(
                stmt,
                {
                    "session_id": self._session_id,
                    "message": _to_json_value(message_to_dict(message)),
                },
            )
        self._db.commit()

    def clear(self) -> None:
        self._db.execute(
            text("DELETE FROM soc_conversation_memory WHERE session_id = :session_id"),
            {"session_id": self._session_id},
        )
        self._db.commit()


class SocMemoryStore:
    def ensure_tables(self, db: Session) -> str:
        dialect = _dialect(db)
        if not dialect:
            raise RuntimeError("Database session is not bound.")

        if _is_postgres(db):
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS soc_conversation_memory (
                        id BIGSERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        message JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS soc_conversation_memory_session_idx "
                    "ON soc_conversation_memory (session_id, created_at)"
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS soc_investigation_memory (
                        investigation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        device_id TEXT NULL,
                        anomaly_type TEXT NOT NULL,
                        tools_used JSONB NOT NULL DEFAULT '[]'::jsonb,
                        reasoning_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
                        root_cause_conclusion TEXT NOT NULL,
                        risk_level TEXT NOT NULL,
                        confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS soc_investigation_memory_session_idx "
                    "ON soc_investigation_memory (session_id, created_at DESC)"
                )
            )
        else:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS soc_conversation_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS soc_conversation_memory_session_idx "
                    "ON soc_conversation_memory (session_id, created_at)"
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS soc_investigation_memory (
                        investigation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        device_id TEXT NULL,
                        anomaly_type TEXT NOT NULL,
                        tools_used TEXT NOT NULL,
                        reasoning_steps TEXT NOT NULL,
                        root_cause_conclusion TEXT NOT NULL,
                        risk_level TEXT NOT NULL,
                        confidence_score REAL NOT NULL DEFAULT 0.5,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS soc_investigation_memory_session_idx "
                    "ON soc_investigation_memory (session_id, created_at DESC)"
                )
            )

        db.commit()

        long_term_mode = self._ensure_long_term_table(db)
        db.commit()
        return long_term_mode

    def _ensure_long_term_table(self, db: Session) -> str:
        if _is_postgres(db):
            try:
                db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                db.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS soc_long_term_incident_memory (
                            memory_id TEXT PRIMARY KEY,
                            investigation_id TEXT NOT NULL,
                            session_id TEXT NOT NULL,
                            device_id TEXT NULL,
                            anomaly_type TEXT NOT NULL,
                            summary TEXT NOT NULL,
                            root_cause TEXT NOT NULL,
                            resolution TEXT NOT NULL,
                            risk_level TEXT NOT NULL,
                            confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                            embedding vector({settings.RAG_EMBEDDING_DIM}) NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
                db.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS soc_long_term_incident_created_idx "
                        "ON soc_long_term_incident_memory (created_at DESC)"
                    )
                )
                return "pgvector"
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "Could not initialize pgvector long-term memory table, falling back to JSON vectors: %s",
                    exc,
                )

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS soc_long_term_incident_memory (
                    memory_id TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    device_id TEXT NULL,
                    anomaly_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    confidence_score REAL NOT NULL DEFAULT 0.5,
                    metadata TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.execute(
            text(
                "CREATE INDEX IF NOT EXISTS soc_long_term_incident_created_idx "
                "ON soc_long_term_incident_memory (created_at DESC)"
            )
        )
        return "json"

    def _detect_long_term_mode(self, db: Session) -> str:
        if _is_postgres(db):
            rows = db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'soc_long_term_incident_memory'
                    """
                )
            ).fetchall()
            columns = {str(row[0]) for row in rows}
        else:
            rows = db.execute(text("PRAGMA table_info(soc_long_term_incident_memory)")).fetchall()
            columns = {str(row[1]) for row in rows}

        if "embedding" in columns:
            return "pgvector"
        return "json"

    def get_message_history(self, db: Session, session_id: str) -> SQLChatMessageHistory:
        self.ensure_tables(db)
        return SQLChatMessageHistory(db=db, session_id=session_id)

    def search_long_term_memory(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
    ) -> List[HistoricalMemoryMatch]:
        self.ensure_tables(db)
        mode = self._detect_long_term_mode(db)
        vector = chat_service._embed_texts([query])[0]  # noqa: SLF001
        limit = max(1, min(top_k, 20))

        if mode == "pgvector":
            rows = db.execute(
                text(
                    """
                    SELECT memory_id, summary, root_cause, resolution, risk_level, created_at,
                           1 - (embedding <=> CAST(:q AS vector)) AS similarity
                    FROM soc_long_term_incident_memory
                    ORDER BY embedding <=> CAST(:q AS vector)
                    LIMIT :k
                    """
                ),
                {"q": chat_service._vector_literal(vector), "k": limit},  # noqa: SLF001
            ).mappings()
            output = [
                HistoricalMemoryMatch(
                    memory_id=str(row.get("memory_id")),
                    summary=str(row.get("summary") or ""),
                    root_cause=str(row.get("root_cause") or ""),
                    resolution=str(row.get("resolution") or ""),
                    risk_level=str(row.get("risk_level") or "medium").lower(),  # type: ignore[arg-type]
                    created_at=row.get("created_at"),
                    similarity=max(0.0, min(1.0, float(row.get("similarity") or 0.0))),
                )
                for row in rows
            ]
            return output

        rows = db.execute(
            text(
                """
                SELECT memory_id, summary, root_cause, resolution, risk_level, created_at, embedding_json
                FROM soc_long_term_incident_memory
                """
            )
        ).mappings()

        scored: List[HistoricalMemoryMatch] = []
        for row in rows:
            try:
                embedding = json.loads(str(row.get("embedding_json") or "[]"))
            except json.JSONDecodeError:
                continue
            if not isinstance(embedding, list):
                continue

            score = chat_service._cosine(vector, embedding)  # noqa: SLF001
            scored.append(
                HistoricalMemoryMatch(
                    memory_id=str(row.get("memory_id")),
                    summary=str(row.get("summary") or ""),
                    root_cause=str(row.get("root_cause") or ""),
                    resolution=str(row.get("resolution") or ""),
                    risk_level=str(row.get("risk_level") or "medium").lower(),  # type: ignore[arg-type]
                    created_at=row.get("created_at"),
                    similarity=max(0.0, min(1.0, float(score))),
                )
            )

        scored.sort(key=lambda item: item.similarity, reverse=True)
        return scored[:limit]

    def _detect_anomaly_type(self, parsed: ParsedSocOutput) -> str:
        issue = parsed.issue_summary.lower()
        if "temperature" in issue:
            return "temperature_anomaly"
        if "humidity" in issue:
            return "humidity_anomaly"
        if "shock" in issue or "impact" in issue:
            return "shock_anomaly"
        if "light" in issue or "tamper" in issue:
            return "tamper_signal"
        return "multi_signal_anomaly"

    def _top_root_cause(self, parsed: ParsedSocOutput) -> str:
        if not parsed.root_cause_analysis:
            return "insufficient_data"
        ranked = sorted(parsed.root_cause_analysis, key=lambda item: item.probability, reverse=True)
        return ranked[0].cause

    def _build_long_term_summary(self, parsed: ParsedSocOutput) -> str:
        root_cause = self._top_root_cause(parsed)
        actions = "; ".join(parsed.recommended_action[:3]) if parsed.recommended_action else "none"
        context = "; ".join(parsed.context_retrieved[:3]) if parsed.context_retrieved else "none"
        return (
            f"Issue={parsed.issue_summary}\n"
            f"RootCause={root_cause}\n"
            f"RiskLevel={parsed.risk_level}\n"
            f"Confidence={parsed.confidence_score:.3f}\n"
            f"Context={context}\n"
            f"Actions={actions}"
        )

    def persist_investigation_memory(
        self,
        db: Session,
        request: SocAssistRequest,
        parsed: ParsedSocOutput,
        tools_used: Sequence[str],
        investigation_id: Optional[str] = None,
    ) -> str:
        self.ensure_tables(db)
        investigation_id = investigation_id or str(uuid.uuid4())
        anomaly_type = self._detect_anomaly_type(parsed)
        root_cause = self._top_root_cause(parsed)

        if _is_postgres(db):
            db.execute(
                text(
                    """
                    INSERT INTO soc_investigation_memory (
                        investigation_id, session_id, device_id, anomaly_type,
                        tools_used, reasoning_steps, root_cause_conclusion,
                        risk_level, confidence_score, created_at
                    ) VALUES (
                        :investigation_id, :session_id, :device_id, :anomaly_type,
                        CAST(:tools_used AS jsonb), CAST(:reasoning_steps AS jsonb), :root_cause_conclusion,
                        :risk_level, :confidence_score, NOW()
                    )
                    ON CONFLICT (investigation_id) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        device_id = EXCLUDED.device_id,
                        anomaly_type = EXCLUDED.anomaly_type,
                        tools_used = EXCLUDED.tools_used,
                        reasoning_steps = EXCLUDED.reasoning_steps,
                        root_cause_conclusion = EXCLUDED.root_cause_conclusion,
                        risk_level = EXCLUDED.risk_level,
                        confidence_score = EXCLUDED.confidence_score,
                        created_at = NOW()
                    """
                ),
                {
                    "investigation_id": investigation_id,
                    "session_id": request.session_id,
                    "device_id": request.device_uid,
                    "anomaly_type": anomaly_type,
                    "tools_used": _to_json_value(list(tools_used)),
                    "reasoning_steps": _to_json_value(parsed.investigation_steps_taken),
                    "root_cause_conclusion": root_cause,
                    "risk_level": parsed.risk_level,
                    "confidence_score": float(parsed.confidence_score),
                },
            )
        else:
            db.execute(
                text("DELETE FROM soc_investigation_memory WHERE investigation_id = :investigation_id"),
                {"investigation_id": investigation_id},
            )
            db.execute(
                text(
                    """
                    INSERT INTO soc_investigation_memory (
                        investigation_id, session_id, device_id, anomaly_type,
                        tools_used, reasoning_steps, root_cause_conclusion,
                        risk_level, confidence_score, created_at
                    ) VALUES (
                        :investigation_id, :session_id, :device_id, :anomaly_type,
                        :tools_used, :reasoning_steps, :root_cause_conclusion,
                        :risk_level, :confidence_score, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "investigation_id": investigation_id,
                    "session_id": request.session_id,
                    "device_id": request.device_uid,
                    "anomaly_type": anomaly_type,
                    "tools_used": _to_json_value(list(tools_used)),
                    "reasoning_steps": _to_json_value(parsed.investigation_steps_taken),
                    "root_cause_conclusion": root_cause,
                    "risk_level": parsed.risk_level,
                    "confidence_score": float(parsed.confidence_score),
                },
            )

        self._persist_long_term_memory(
            db=db,
            request=request,
            parsed=parsed,
            investigation_id=investigation_id,
            anomaly_type=anomaly_type,
            root_cause=root_cause,
        )
        db.commit()
        return investigation_id

    def _persist_long_term_memory(
        self,
        db: Session,
        request: SocAssistRequest,
        parsed: ParsedSocOutput,
        investigation_id: str,
        anomaly_type: str,
        root_cause: str,
    ) -> None:
        mode = self._detect_long_term_mode(db)
        summary = self._build_long_term_summary(parsed)
        resolution = "; ".join(parsed.recommended_action[:5]) or "No remediation provided."
        vector = chat_service._embed_texts([summary])[0]  # noqa: SLF001
        memory_id = str(uuid.uuid4())

        metadata = {
            "session_id": request.session_id,
            "question": request.question,
            "context_retrieved": parsed.context_retrieved,
            "historical_memory_matches": [item.model_dump(mode="json") for item in parsed.historical_memory_matches],
        }

        if mode == "pgvector":
            db.execute(
                text(
                    """
                    INSERT INTO soc_long_term_incident_memory (
                        memory_id, investigation_id, session_id, device_id, anomaly_type,
                        summary, root_cause, resolution, risk_level, confidence_score,
                        metadata, embedding, created_at
                    ) VALUES (
                        :memory_id, :investigation_id, :session_id, :device_id, :anomaly_type,
                        :summary, :root_cause, :resolution, :risk_level, :confidence_score,
                        CAST(:metadata AS jsonb), CAST(:embedding AS vector), NOW()
                    )
                    """
                ),
                {
                    "memory_id": memory_id,
                    "investigation_id": investigation_id,
                    "session_id": request.session_id,
                    "device_id": request.device_uid,
                    "anomaly_type": anomaly_type,
                    "summary": summary,
                    "root_cause": root_cause,
                    "resolution": resolution,
                    "risk_level": parsed.risk_level,
                    "confidence_score": float(parsed.confidence_score),
                    "metadata": _to_json_value(metadata),
                    "embedding": chat_service._vector_literal(vector),  # noqa: SLF001
                },
            )
            return

        db.execute(
            text(
                """
                INSERT INTO soc_long_term_incident_memory (
                    memory_id, investigation_id, session_id, device_id, anomaly_type,
                    summary, root_cause, resolution, risk_level, confidence_score,
                    metadata, embedding_json, created_at
                ) VALUES (
                    :memory_id, :investigation_id, :session_id, :device_id, :anomaly_type,
                    :summary, :root_cause, :resolution, :risk_level, :confidence_score,
                    :metadata, :embedding_json, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "memory_id": memory_id,
                "investigation_id": investigation_id,
                "session_id": request.session_id,
                "device_id": request.device_uid,
                "anomaly_type": anomaly_type,
                "summary": summary,
                "root_cause": root_cause,
                "resolution": resolution,
                "risk_level": parsed.risk_level,
                "confidence_score": float(parsed.confidence_score),
                "metadata": _to_json_value(metadata),
                "embedding_json": _to_json_value(vector),
            },
        )

    def list_investigation_memory(
        self,
        db: Session,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[InvestigationAuditRecord]:
        self.ensure_tables(db)
        safe_limit = max(1, min(limit, 200))

        if session_id:
            rows = db.execute(
                text(
                    """
                    SELECT investigation_id, session_id, device_id, anomaly_type, tools_used,
                           reasoning_steps, root_cause_conclusion, risk_level, confidence_score, created_at
                    FROM soc_investigation_memory
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC
                    LIMIT :k
                    """
                ),
                {"session_id": session_id, "k": safe_limit},
            ).mappings()
        else:
            rows = db.execute(
                text(
                    """
                    SELECT investigation_id, session_id, device_id, anomaly_type, tools_used,
                           reasoning_steps, root_cause_conclusion, risk_level, confidence_score, created_at
                    FROM soc_investigation_memory
                    ORDER BY created_at DESC
                    LIMIT :k
                    """
                ),
                {"k": safe_limit},
            ).mappings()

        records: List[InvestigationAuditRecord] = []
        for row in rows:
            tools_raw = row.get("tools_used")
            reasoning_raw = row.get("reasoning_steps")

            if isinstance(tools_raw, str):
                try:
                    tools_raw = json.loads(tools_raw)
                except json.JSONDecodeError:
                    tools_raw = []
            if isinstance(reasoning_raw, str):
                try:
                    reasoning_raw = json.loads(reasoning_raw)
                except json.JSONDecodeError:
                    reasoning_raw = []

            records.append(
                InvestigationAuditRecord(
                    investigation_id=str(row.get("investigation_id")),
                    session_id=str(row.get("session_id") or ""),
                    device_id=str(row.get("device_id")) if row.get("device_id") else None,
                    anomaly_type=str(row.get("anomaly_type") or "unknown"),
                    tools_used=[str(item) for item in (tools_raw or [])],
                    reasoning_steps=[str(item) for item in (reasoning_raw or [])],
                    root_cause_conclusion=str(row.get("root_cause_conclusion") or ""),
                    risk_level=str(row.get("risk_level") or "medium").lower(),  # type: ignore[arg-type]
                    confidence_score=float(row.get("confidence_score") or 0.5),
                    created_at=_parse_datetime(row.get("created_at")),
                )
            )

        return records


soc_memory_store = SocMemoryStore()
