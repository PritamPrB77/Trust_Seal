from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import httpx
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.custody_checkpoint import CustodyCheckpoint
from ..models.device import Device
from ..models.sensor_log import SensorLog
from ..models.shipment import Shipment, ShipmentLeg
from ..schemas.chat import ChatResponse

logger = logging.getLogger(__name__)

NO_DATA_MESSAGE = "No relevant data found in the system."

SYSTEM_PROMPT = (
    "You are TrustSeal AI, a supply-chain analyst. Use only retrieved context. "
    "If missing, answer exactly: 'No relevant data found in the system.' "
    "Write the answer as a short factual story (timeline style), not bullet points. "
    "Return valid JSON with keys: answer, sources, confidence. "
    "confidence must be one of: high, medium, low."
)

Confidence = Literal["high", "medium", "low"]


class ChatServiceError(Exception):
    pass


class ChatConfigurationError(ChatServiceError):
    pass


class ChatProviderError(ChatServiceError):
    pass


@dataclass(frozen=True, slots=True)
class RAGDocument:
    doc_id: str
    source_type: str
    source_id: str
    content: str
    metadata: Dict[str, Any]
    content_hash: str


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    doc_id: str
    source_type: str
    source_id: str
    content: str
    metadata: Dict[str, Any]
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalBundle:
    context: Dict[str, Any]
    sources: List[str]
    has_data: bool
    confidence: Confidence


class ChatService:
    def answer_question(
        self,
        question: str,
        db: Session,
        shipment_id: Optional[str] = None,
    ) -> ChatResponse:
        question = question.strip()
        if not question:
            return ChatResponse(answer=NO_DATA_MESSAGE, sources=[], confidence="low")

        exact_average_answer = self._maybe_answer_exact_average_temperature(
            question=question,
            db=db,
            shipment_id=shipment_id,
        )
        if exact_average_answer is not None:
            return exact_average_answer

        retrieval = self._retrieve_context(question, db)
        if not retrieval.has_data:
            return ChatResponse(answer=NO_DATA_MESSAGE, sources=[], confidence="low")

        llm_response = self._call_openrouter(question=question, retrieval=retrieval)
        answer, sources, confidence = self._normalize_llm_response(llm_response, retrieval)
        return ChatResponse(answer=answer, sources=sources, confidence=confidence)

    def refresh_index(self, db: Session) -> None:
        self._sync_vector_index(db)

    def _is_average_temperature_question(self, question: str) -> bool:
        lowered = question.lower()
        has_temperature = "temperature" in lowered or "temp" in lowered
        has_average = "average" in lowered or "avg" in lowered or "mean" in lowered
        return has_temperature and has_average

    def _parse_uuid(self, value: Optional[str]) -> Optional[uuid.UUID]:
        if not value:
            return None
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return None

    def _extract_shipment_code(self, question: str) -> Optional[str]:
        match = re.search(r"\bSHP-\d{4}-\d+\b", question, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(0).upper()

    def _extract_shipment_id_from_question(self, question: str) -> Optional[uuid.UUID]:
        match = re.search(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
            question,
        )
        if not match:
            return None
        return self._parse_uuid(match.group(0))

    def _resolve_shipment_for_temperature_query(
        self,
        db: Session,
        question: str,
        shipment_id: Optional[str],
    ) -> Optional[Shipment]:
        # 1) Prefer explicit shipment_id context from frontend route.
        shipment_uuid = self._parse_uuid(shipment_id)
        if shipment_uuid is not None:
            shipment = db.query(Shipment).filter(Shipment.id == shipment_uuid).first()
            if shipment is not None:
                return shipment

        # 2) Allow UUID present directly in question text.
        question_uuid = self._extract_shipment_id_from_question(question)
        if question_uuid is not None:
            shipment = db.query(Shipment).filter(Shipment.id == question_uuid).first()
            if shipment is not None:
                return shipment

        # 3) Allow shipment code references (e.g., SHP-2024-001).
        shipment_code = self._extract_shipment_code(question)
        if shipment_code:
            return (
                db.query(Shipment)
                .filter(Shipment.shipment_code.ilike(shipment_code))
                .first()
            )

        return None

    def _graph_window_temperature_average(
        self,
        db: Session,
        shipment_id: uuid.UUID,
    ) -> Tuple[Optional[float], int]:
        # Keep this aligned with the graph API route defaults:
        # GET /api/v1/shipments/{shipment_id}/logs?skip=0&limit=100
        logs = (
            db.query(SensorLog)
            .filter(SensorLog.shipment_id == shipment_id)
            .offset(0)
            .limit(100)
            .all()
        )
        values = [
            float(entry.temperature)
            for entry in logs
            if isinstance(entry.temperature, (int, float))
        ]
        if not values:
            return None, 0
        return sum(values) / len(values), len(values)

    def _maybe_answer_exact_average_temperature(
        self,
        question: str,
        db: Session,
        shipment_id: Optional[str],
    ) -> Optional[ChatResponse]:
        if not self._is_average_temperature_question(question):
            return None

        shipment = self._resolve_shipment_for_temperature_query(
            db=db,
            question=question,
            shipment_id=shipment_id,
        )
        if shipment is None:
            return None

        average, sample_size = self._graph_window_temperature_average(db, shipment.id)
        if average is None:
            return ChatResponse(
                answer=(
                    f"No temperature values found for shipment {shipment.shipment_code} "
                    "in the current graph window."
                ),
                sources=[shipment.shipment_code, str(shipment.id)],
                confidence="low",
            )

        return ChatResponse(
            answer=(
                f"For shipment {shipment.shipment_code}, average temperature is "
                f"{average:.2f} C based on {sample_size} sensor log points "
                "(same dataset used by the shipment graph)."
            ),
            sources=[shipment.shipment_code, str(shipment.id)],
            confidence="high",
        )

    def _retrieve_context(self, question: str, db: Session) -> RetrievalBundle:
        self._sync_vector_index(db)
        chunks = self._search_similar_chunks(db, question, settings.RAG_TOP_K)
        if not chunks:
            return RetrievalBundle(
                context={"retrieval_mode": "vector", "record_count": 0, "matches": []},
                sources=[],
                has_data=False,
                confidence="low",
            )

        top_score = chunks[0].score
        confidence: Confidence = "high" if top_score >= 0.8 else ("medium" if top_score >= 0.6 else "low")
        context = {
            "retrieval_mode": "vector",
            "record_count": len(chunks),
            "matches": [
                {
                    "doc_id": c.doc_id,
                    "source_type": c.source_type,
                    "source_id": c.source_id,
                    "score": round(c.score, 4),
                    "content": c.content,
                    "metadata": c.metadata,
                }
                for c in chunks
            ],
            "generated_at_utc": self._to_iso(datetime.utcnow()),
        }
        sources = self._unique_ordered([c.source_id for c in chunks if c.source_id])
        return RetrievalBundle(context=context, sources=sources, has_data=True, confidence=confidence)

    def _sync_vector_index(self, db: Session) -> None:
        mode = self._ensure_store(db)
        docs = self._build_documents(db)
        docs_by_id = {doc.doc_id: doc for doc in docs}
        existing = self._existing_hashes(db)

        stale = [doc_id for doc_id in existing if doc_id not in docs_by_id]
        changed = [doc for doc in docs if existing.get(doc.doc_id) != doc.content_hash]

        if changed:
            vectors = self._embed_texts([doc.content for doc in changed])
            if mode == "pgvector":
                self._upsert_pgvector(db, changed, vectors)
            else:
                self._upsert_json(db, changed, vectors)

        if stale:
            stmt = text("DELETE FROM rag_documents WHERE doc_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            )
            db.execute(stmt, {"ids": stale})

        if changed or stale:
            db.commit()

    def _search_similar_chunks(self, db: Session, question: str, top_k: int) -> List[RetrievedChunk]:
        query_vec = self._embed_texts([question])[0]
        mode = self._detect_mode(db)

        if mode == "pgvector":
            rows = db.execute(
                text(
                    """
                    SELECT doc_id, source_type, source_id, content, metadata,
                           1 - (embedding <=> CAST(:q AS vector)) AS score
                    FROM rag_documents
                    ORDER BY embedding <=> CAST(:q AS vector)
                    LIMIT :k
                    """
                ),
                {"q": self._vector_literal(query_vec), "k": top_k},
            ).mappings()
            output: List[RetrievedChunk] = []
            for row in rows:
                meta = row.get("metadata")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
                output.append(
                    RetrievedChunk(
                        doc_id=str(row["doc_id"]),
                        source_type=str(row["source_type"]),
                        source_id=str(row["source_id"]),
                        content=str(row["content"]),
                        metadata=meta if isinstance(meta, dict) else {},
                        score=float(row["score"] or 0.0),
                    )
                )
            return output

        rows = db.execute(
            text("SELECT doc_id, source_type, source_id, content, metadata, embedding_json FROM rag_documents")
        ).mappings()
        scored: List[RetrievedChunk] = []
        for row in rows:
            try:
                emb = json.loads(str(row["embedding_json"]))
            except Exception:
                continue
            if not isinstance(emb, list):
                continue
            meta = row.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            scored.append(
                RetrievedChunk(
                    doc_id=str(row["doc_id"]),
                    source_type=str(row["source_type"]),
                    source_id=str(row["source_id"]),
                    content=str(row["content"]),
                    metadata=meta if isinstance(meta, dict) else {},
                    score=self._cosine(query_vec, emb),
                )
            )
        scored.sort(key=lambda chunk: chunk.score, reverse=True)
        return scored[:top_k]

    def _ensure_store(self, db: Session) -> str:
        mode = self._detect_mode(db)
        if mode:
            return mode

        if self._is_postgres(db):
            try:
                db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                db.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS rag_documents (
                            doc_id TEXT PRIMARY KEY,
                            source_type TEXT NOT NULL,
                            source_id TEXT NOT NULL,
                            content TEXT NOT NULL,
                            content_hash TEXT NOT NULL,
                            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                            embedding vector({settings.RAG_EMBEDDING_DIM}) NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
                db.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS rag_documents_source_idx "
                        "ON rag_documents (source_type, source_id)"
                    )
                )
                db.commit()
                return "pgvector"
            except Exception as exc:
                db.rollback()
                if settings.RAG_REQUIRE_PGVECTOR:
                    raise ChatConfigurationError(
                        "pgvector is required for RAG but could not be initialized."
                    ) from exc
                logger.warning("pgvector unavailable, switching to JSON vectors: %s", exc)
        elif settings.RAG_REQUIRE_PGVECTOR:
            raise ChatConfigurationError(
                "RAG is configured to require pgvector, but the active database is not PostgreSQL."
            )

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    doc_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.commit()
        return "json"

    def _detect_mode(self, db: Session) -> Optional[str]:
        if self._is_postgres(db):
            rows = db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'rag_documents'
                    """
                )
            ).fetchall()
            cols = {str(row[0]) for row in rows}
        else:
            rows = db.execute(text("PRAGMA table_info(rag_documents)")).fetchall()
            cols = {str(row[1]) for row in rows}

        if not cols:
            return None
        if "embedding" in cols:
            return "pgvector"
        if "embedding_json" in cols:
            return "json"
        return None

    def _existing_hashes(self, db: Session) -> Dict[str, str]:
        rows = db.execute(text("SELECT doc_id, content_hash FROM rag_documents")).fetchall()
        return {str(row[0]): str(row[1]) for row in rows}

    def _upsert_pgvector(self, db: Session, docs: Sequence[RAGDocument], vectors: Sequence[List[float]]) -> None:
        stmt = text(
            """
            INSERT INTO rag_documents (doc_id, source_type, source_id, content, content_hash, metadata, embedding, updated_at)
            VALUES (:doc_id, :source_type, :source_id, :content, :content_hash, CAST(:metadata AS jsonb), CAST(:embedding AS vector), NOW())
            ON CONFLICT (doc_id) DO UPDATE SET
                source_type = EXCLUDED.source_type,
                source_id = EXCLUDED.source_id,
                content = EXCLUDED.content,
                content_hash = EXCLUDED.content_hash,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """
        )
        for doc, vector in zip(docs, vectors):
            db.execute(
                stmt,
                {
                    "doc_id": doc.doc_id,
                    "source_type": doc.source_type,
                    "source_id": doc.source_id,
                    "content": doc.content,
                    "content_hash": doc.content_hash,
                    "metadata": json.dumps(doc.metadata, ensure_ascii=True),
                    "embedding": self._vector_literal(vector),
                },
            )

    def _upsert_json(self, db: Session, docs: Sequence[RAGDocument], vectors: Sequence[List[float]]) -> None:
        stmt = text(
            """
            INSERT INTO rag_documents (doc_id, source_type, source_id, content, content_hash, metadata, embedding_json, updated_at)
            VALUES (:doc_id, :source_type, :source_id, :content, :content_hash, :metadata, :embedding_json, CURRENT_TIMESTAMP)
            ON CONFLICT(doc_id) DO UPDATE SET
                source_type = excluded.source_type,
                source_id = excluded.source_id,
                content = excluded.content,
                content_hash = excluded.content_hash,
                metadata = excluded.metadata,
                embedding_json = excluded.embedding_json,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        for doc, vector in zip(docs, vectors):
            db.execute(
                stmt,
                {
                    "doc_id": doc.doc_id,
                    "source_type": doc.source_type,
                    "source_id": doc.source_id,
                    "content": doc.content,
                    "content_hash": doc.content_hash,
                    "metadata": json.dumps(doc.metadata, ensure_ascii=True),
                    "embedding_json": json.dumps(vector),
                },
            )

    def _build_documents(self, db: Session) -> List[RAGDocument]:
        devices = db.query(Device).all()
        shipments = db.query(Shipment).all()
        legs = db.query(ShipmentLeg).all()
        logs = db.query(SensorLog).order_by(SensorLog.recorded_at.desc()).limit(settings.RAG_MAX_SENSOR_LOG_DOCS).all()
        checkpoints = (
            db.query(CustodyCheckpoint)
            .order_by(CustodyCheckpoint.timestamp.desc())
            .limit(settings.RAG_MAX_CUSTODY_DOCS)
            .all()
        )

        shipments_by_id = {str(shipment.id): shipment for shipment in shipments}
        devices_by_id = {str(device.id): device for device in devices}
        docs: List[RAGDocument] = []

        for device in devices:
            docs.append(
                self._doc(
                    f"device:{device.id}",
                    "device",
                    str(device.id),
                    f"Device {device.device_uid} model {device.model} firmware {device.firmware_version} status {device.status.value} battery {device.battery_capacity_mAh} mAh.",
                    {"device_uid": device.device_uid, "status": device.status.value},
                )
            )

        for shipment in shipments:
            tracker = devices_by_id.get(str(shipment.device_id))
            tracker_uid = tracker.device_uid if tracker else str(shipment.device_id)
            docs.append(
                self._doc(
                    f"shipment:{shipment.id}",
                    "shipment",
                    str(shipment.id),
                    f"Shipment {shipment.shipment_code} is {shipment.status.value} from {shipment.origin} to {shipment.destination} using tracker {tracker_uid}.",
                    {"shipment_code": shipment.shipment_code, "status": shipment.status.value},
                )
            )

        for leg in legs:
            shipment = shipments_by_id.get(str(leg.shipment_id))
            code = shipment.shipment_code if shipment else str(leg.shipment_id)
            docs.append(
                self._doc(
                    f"leg:{leg.id}",
                    "shipment_leg",
                    str(leg.id),
                    f"Leg {leg.leg_number} for shipment {code} moves from {leg.from_location} to {leg.to_location} and is {leg.status.value}.",
                    {"shipment_id": str(leg.shipment_id), "shipment_code": code},
                )
            )

        for log in logs:
            shipment = shipments_by_id.get(str(log.shipment_id))
            code = shipment.shipment_code if shipment else str(log.shipment_id)
            docs.append(
                self._doc(
                    f"log:{log.id}",
                    "sensor_log",
                    str(log.id),
                    f"Sensor log for shipment {code}: temperature {log.temperature}, humidity {log.humidity}, shock {log.shock}, light exposure {log.light_exposure}, tilt {log.tilt_angle} at {self._to_iso(log.recorded_at)}.",
                    {"shipment_id": str(log.shipment_id), "shipment_code": code},
                )
            )

        for checkpoint in checkpoints:
            shipment = shipments_by_id.get(str(checkpoint.shipment_id))
            code = shipment.shipment_code if shipment else str(checkpoint.shipment_id)
            docs.append(
                self._doc(
                    f"custody:{checkpoint.id}",
                    "custody_checkpoint",
                    str(checkpoint.id),
                    f"Custody checkpoint for shipment {code} at {self._to_iso(checkpoint.timestamp)} biometric verified {checkpoint.biometric_verified}.",
                    {"shipment_id": str(checkpoint.shipment_id), "shipment_code": code},
                )
            )

        return docs

    def _doc(self, doc_id: str, source_type: str, source_id: str, content: str, metadata: Dict[str, Any]) -> RAGDocument:
        return RAGDocument(
            doc_id=doc_id,
            source_type=source_type,
            source_id=source_id,
            content=content,
            metadata=metadata,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def _embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        if settings.RAG_USE_OPENROUTER_EMBEDDINGS and settings.OPENROUTER_API_KEY:
            try:
                return self._embed_openrouter(texts)
            except ChatProviderError as exc:
                logger.warning("Embedding endpoint failed; using hash vectors: %s", exc)
        return [self._hash_embed(value) for value in texts]

    def _embed_openrouter(self, texts: Sequence[str]) -> List[List[float]]:
        payload = {"model": settings.OPENROUTER_EMBEDDING_MODEL, "input": list(texts)}
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_APP_NAME:
            headers["X-Title"] = settings.OPENROUTER_APP_NAME

        url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/embeddings"
        try:
            with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ChatProviderError("Embeddings request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise ChatProviderError(f"Embeddings request failed ({exc.response.status_code}).") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ChatProviderError("Embeddings endpoint failed.") from exc

        data = body.get("data", [])
        if not isinstance(data, list) or not data:
            raise ChatProviderError("Embeddings response is empty.")
        data.sort(key=lambda item: item.get("index", 0))
        return [self._normalize_vector([float(v) for v in item.get("embedding", [])]) for item in data]

    def _hash_embed(self, value: str) -> List[float]:
        dim = settings.RAG_EMBEDDING_DIM
        vector = [0.0] * dim
        tokens = re.findall(r"[a-z0-9]+", value.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, 16, 2):
                idx = ((digest[i] << 8) | digest[i + 1]) % dim
                vector[idx] += 1.0 if digest[i + 1] & 1 else -1.0
        return self._l2(vector)

    def _normalize_vector(self, values: List[float]) -> List[float]:
        dim = settings.RAG_EMBEDDING_DIM
        if len(values) > dim:
            summed = [0.0] * dim
            counts = [0] * dim
            for i, value in enumerate(values):
                slot = i % dim
                summed[slot] += value
                counts[slot] += 1
            values = [summed[i] / counts[i] if counts[i] else 0.0 for i in range(dim)]
        elif len(values) < dim:
            values = values + [0.0] * (dim - len(values))
        return self._l2(values)

    def _l2(self, values: List[float]) -> List[float]:
        norm = math.sqrt(sum(value * value for value in values))
        return values if norm == 0 else [value / norm for value in values]

    def _cosine(self, left: Sequence[float], right: Sequence[float]) -> float:
        max_len = max(len(left), len(right))
        if len(left) < max_len:
            left = list(left) + [0.0] * (max_len - len(left))
        if len(right) < max_len:
            right = list(right) + [0.0] * (max_len - len(right))
        return float(sum(a * b for a, b in zip(left, right)))

    def _vector_literal(self, values: Sequence[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in values) + "]"

    def _call_openrouter(self, question: str, retrieval: RetrievalBundle) -> Dict[str, Any]:
        if not settings.OPENROUTER_API_KEY:
            raise ChatConfigurationError("OpenRouter is not configured on the server.")

        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "User question:\\n"
                        f"{question}\\n\\n"
                        "Retrieved context JSON:\\n"
                        f"{json.dumps(retrieval.context, ensure_ascii=True)}"
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": settings.OPENROUTER_MAX_TOKENS,
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_APP_NAME:
            headers["X-Title"] = settings.OPENROUTER_APP_NAME

        url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
        try:
            with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ChatProviderError("OpenRouter request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise ChatProviderError(f"OpenRouter request failed ({exc.response.status_code}).") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ChatProviderError("OpenRouter request failed.") from exc

        choices = body.get("choices", [])
        if not choices:
            raise ChatProviderError("OpenRouter returned no choices.")
        message = choices[0].get("message", {})
        if message.get("content") is None:
            raise ChatProviderError("OpenRouter returned an empty response.")
        return {"content": message.get("content")}

    def _normalize_llm_response(self, llm_response: Dict[str, Any], retrieval: RetrievalBundle) -> Tuple[str, List[str], Confidence]:
        text_value = self._to_text(llm_response.get("content", ""))
        parsed = self._extract_json(text_value)

        answer = NO_DATA_MESSAGE
        sources = retrieval.sources
        confidence: Confidence = retrieval.confidence

        if isinstance(parsed, dict):
            val = parsed.get("answer")
            if isinstance(val, str) and val.strip():
                answer = val.strip()

            src = parsed.get("sources")
            if isinstance(src, list):
                allowed = set(retrieval.sources)
                clean = [str(value) for value in src if isinstance(value, (str, int, float))]
                clean = [value for value in clean if value in allowed]
                if clean:
                    sources = self._unique_ordered(clean)

            conf = parsed.get("confidence")
            if isinstance(conf, str):
                conf = conf.lower().strip()
                if conf in ("high", "medium", "low"):
                    confidence = conf  # type: ignore[assignment]
        elif text_value.strip():
            answer = text_value.strip()

        if answer == NO_DATA_MESSAGE:
            return answer, [], "low"
        return answer, sources, confidence

    def _to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content)

    def _extract_json(self, value: str) -> Optional[Dict[str, Any]]:
        value = value.strip()
        if not value:
            return None
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
        start = value.find("{")
        end = value.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(value[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def _to_iso(self, value: Optional[datetime]) -> Optional[str]:
        return None if value is None else value.isoformat()

    def _unique_ordered(self, values: List[Any]) -> List[Any]:
        seen = set()
        output = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def _is_postgres(self, db: Session) -> bool:
        bind = db.get_bind()
        return bool(bind and bind.dialect.name == "postgresql")


chat_service = ChatService()
