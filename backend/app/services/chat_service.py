from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.custody_checkpoint import CustodyCheckpoint
from ..models.device import Device
from ..models.enums import DeviceStatus, ShipmentStatus
from ..models.sensor_log import SensorLog
from ..models.shipment import Shipment
from ..schemas.chat import ChatResponse

logger = logging.getLogger(__name__)

NO_DATA_MESSAGE = "No relevant data found in the system."

SYSTEM_PROMPT = (
    "You are TrustSeal AI, an operational assistant for supply chain monitoring. "
    "Only answer using provided database context. If answer is not in context, say: "
    "'No relevant data found in the system.' "
    "Return valid JSON with keys: answer, sources, confidence. "
    "Use confidence as one of: high, medium, low."
)

Confidence = Literal["high", "medium", "low"]


class ChatServiceError(Exception):
    pass


class ChatConfigurationError(ChatServiceError):
    pass


class ChatProviderError(ChatServiceError):
    pass


@dataclass(frozen=True, slots=True)
class RetrievalBundle:
    intent: str
    context: Dict[str, Any]
    sources: List[str]
    has_data: bool
    confidence: Confidence


class ChatService:
    def answer_question(self, question: str, db: Session) -> ChatResponse:
        question = question.strip()
        if not question:
            return ChatResponse(answer=NO_DATA_MESSAGE, sources=[], confidence="low")

        retrieval = self._retrieve_context(question, db)
        logger.info(
            "Chat retrieval intent=%s records=%s sources=%s",
            retrieval.intent,
            retrieval.context.get("record_count", 0),
            len(retrieval.sources),
        )

        if not retrieval.has_data:
            return ChatResponse(answer=NO_DATA_MESSAGE, sources=[], confidence="low")

        llm_response = self._call_openrouter(question=question, retrieval=retrieval)
        answer, sources, confidence = self._normalize_llm_response(llm_response, retrieval)
        return ChatResponse(answer=answer, sources=sources, confidence=confidence)

    def _detect_intent(self, question: str) -> str:
        q = question.lower()
        if any(keyword in q for keyword in ("device", "firmware", "battery", "ts-")):
            return "device"
        if any(keyword in q for keyword in ("custody", "checkpoint", "biometric", "verified")):
            return "custody"
        if any(
            keyword in q
            for keyword in ("sensor", "temperature", "humidity", "shock", "tamper", "tilt", "log")
        ):
            return "logs"
        return "shipment"

    def _retrieve_context(self, question: str, db: Session) -> RetrievalBundle:
        intent = self._detect_intent(question)
        if intent == "shipment":
            return self._retrieve_shipment_context(question, db)
        if intent == "device":
            return self._retrieve_device_context(question, db)
        if intent == "logs":
            return self._retrieve_log_context(question, db)
        return self._retrieve_custody_context(question, db)

    def _retrieve_shipment_context(self, question: str, db: Session) -> RetrievalBundle:
        q = question.lower()
        query = db.query(Shipment)
        filters: Dict[str, Any] = {}

        if "compromised" in q:
            query = query.filter(Shipment.status == ShipmentStatus.COMPROMISED)
            filters["status"] = ShipmentStatus.COMPROMISED.value
        elif "in transit" in q:
            query = query.filter(Shipment.status == ShipmentStatus.IN_TRANSIT)
            filters["status"] = ShipmentStatus.IN_TRANSIT.value
        elif "completed" in q or "settled" in q:
            query = query.filter(Shipment.status == ShipmentStatus.COMPLETED)
            filters["status"] = ShipmentStatus.COMPLETED.value

        shipment_code = self._extract_shipment_code(question)
        if shipment_code:
            query = query.filter(Shipment.shipment_code.ilike(f"%{shipment_code}%"))
            filters["shipment_code"] = shipment_code

        shipments = query.order_by(Shipment.created_at.desc()).limit(30).all()
        items = [
            {
                "id": str(s.id),
                "shipment_code": s.shipment_code,
                "status": s.status.value,
                "origin": s.origin,
                "destination": s.destination,
                "device_id": str(s.device_id),
                "created_at": self._to_iso(s.created_at),
            }
            for s in shipments
        ]

        sources = self._unique_ordered(
            [item["id"] for item in items] + [item["device_id"] for item in items if item["device_id"]]
        )
        context = {
            "intent": "shipment",
            "filters": filters,
            "record_count": len(items),
            "shipments": items,
            "generated_at_utc": self._to_iso(datetime.utcnow()),
        }
        confidence: Confidence = "high" if len(items) > 0 and filters else ("medium" if items else "low")
        return RetrievalBundle(
            intent="shipment",
            context=context,
            sources=sources,
            has_data=bool(items),
            confidence=confidence,
        )

    def _retrieve_device_context(self, question: str, db: Session) -> RetrievalBundle:
        q = question.lower()
        query = db.query(Device)
        filters: Dict[str, Any] = {}

        if "active" in q and "inactive" not in q:
            query = query.filter(Device.status == DeviceStatus.ACTIVE)
            filters["status"] = DeviceStatus.ACTIVE.value
        elif "inactive" in q:
            query = query.filter(Device.status == DeviceStatus.INACTIVE)
            filters["status"] = DeviceStatus.INACTIVE.value

        device_uid = self._extract_device_uid(question)
        if device_uid:
            query = query.filter(Device.device_uid.ilike(device_uid))
            filters["device_uid"] = device_uid

        devices = query.order_by(Device.created_at.desc()).limit(30).all()
        items = [
            {
                "id": str(d.id),
                "device_uid": d.device_uid,
                "model": d.model,
                "firmware_version": d.firmware_version,
                "status": d.status.value,
                "battery_capacity_mAh": d.battery_capacity_mAh,
                "created_at": self._to_iso(d.created_at),
            }
            for d in devices
        ]

        sources = self._unique_ordered([item["id"] for item in items])
        context = {
            "intent": "device",
            "filters": filters,
            "record_count": len(items),
            "devices": items,
            "generated_at_utc": self._to_iso(datetime.utcnow()),
        }
        confidence: Confidence = "high" if len(items) == 1 and filters else ("medium" if items else "low")
        return RetrievalBundle(
            intent="device",
            context=context,
            sources=sources,
            has_data=bool(items),
            confidence=confidence,
        )

    def _retrieve_log_context(self, question: str, db: Session) -> RetrievalBundle:
        q = question.lower()
        query = db.query(SensorLog)
        filters: Dict[str, Any] = {}

        shipment_code = self._extract_shipment_code(question)
        if shipment_code:
            shipment_ids = [
                row[0]
                for row in db.query(Shipment.id)
                .filter(Shipment.shipment_code.ilike(f"%{shipment_code}%"))
                .all()
            ]
            if shipment_ids:
                query = query.filter(SensorLog.shipment_id.in_(shipment_ids))
                filters["shipment_code"] = shipment_code

        temperature_threshold, operator = self._extract_temperature_filter(q)
        if temperature_threshold is not None and operator:
            query = query.filter(SensorLog.temperature.isnot(None))
            filters["temperature"] = {"operator": operator, "value": temperature_threshold}
            if operator == "above":
                query = query.filter(SensorLog.temperature > temperature_threshold)
            else:
                query = query.filter(SensorLog.temperature < temperature_threshold)

        if "shock" in q:
            query = query.filter(SensorLog.shock.isnot(None))
            filters["shock_present"] = True

        if "tamper" in q:
            query = query.filter(
                or_(
                    SensorLog.light_exposure.is_(True),
                    SensorLog.shock.isnot(None),
                    SensorLog.tilt_angle.isnot(None),
                )
            )
            filters["tamper_like_signals"] = True

        if "yesterday" in q:
            window_start, window_end = self._yesterday_window_utc_naive()
            query = query.filter(
                SensorLog.recorded_at >= window_start,
                SensorLog.recorded_at < window_end,
            )
            filters["time_window_utc"] = {
                "start": self._to_iso(window_start),
                "end": self._to_iso(window_end),
            }

        logs = query.order_by(SensorLog.recorded_at.desc()).limit(80).all()
        shipment_map = self._shipment_code_map(db, [log.shipment_id for log in logs])
        items = [
            {
                "id": str(log.id),
                "shipment_id": str(log.shipment_id),
                "shipment_code": shipment_map.get(log.shipment_id),
                "temperature": log.temperature,
                "humidity": log.humidity,
                "shock": log.shock,
                "light_exposure": log.light_exposure,
                "tilt_angle": log.tilt_angle,
                "recorded_at": self._to_iso(log.recorded_at),
            }
            for log in logs
        ]

        sources = self._unique_ordered([item["shipment_id"] for item in items])
        context = {
            "intent": "logs",
            "filters": filters,
            "record_count": len(items),
            "sensor_logs": items,
            "generated_at_utc": self._to_iso(datetime.utcnow()),
        }
        confidence: Confidence = "high" if len(items) > 0 and filters else ("medium" if items else "low")
        return RetrievalBundle(
            intent="logs",
            context=context,
            sources=sources,
            has_data=bool(items),
            confidence=confidence,
        )

    def _retrieve_custody_context(self, question: str, db: Session) -> RetrievalBundle:
        q = question.lower()
        query = db.query(CustodyCheckpoint)
        filters: Dict[str, Any] = {}

        shipment_code = self._extract_shipment_code(question)
        if shipment_code:
            shipment_ids = [
                row[0]
                for row in db.query(Shipment.id)
                .filter(Shipment.shipment_code.ilike(f"%{shipment_code}%"))
                .all()
            ]
            if shipment_ids:
                query = query.filter(CustodyCheckpoint.shipment_id.in_(shipment_ids))
                filters["shipment_code"] = shipment_code

        if "yesterday" in q:
            window_start, window_end = self._yesterday_window_utc_naive()
            query = query.filter(
                CustodyCheckpoint.timestamp >= window_start,
                CustodyCheckpoint.timestamp < window_end,
            )
            filters["time_window_utc"] = {
                "start": self._to_iso(window_start),
                "end": self._to_iso(window_end),
            }

        checkpoints = query.order_by(CustodyCheckpoint.timestamp.desc()).limit(80).all()
        items = [
            {
                "id": str(cp.id),
                "shipment_id": str(cp.shipment_id),
                "leg_id": str(cp.leg_id) if cp.leg_id else None,
                "verified_by": str(cp.verified_by) if cp.verified_by else None,
                "biometric_verified": cp.biometric_verified,
                "timestamp": self._to_iso(cp.timestamp),
                "blockchain_tx_hash": cp.blockchain_tx_hash,
                "merkle_root_hash": cp.merkle_root_hash,
            }
            for cp in checkpoints
        ]

        sources = self._unique_ordered([item["shipment_id"] for item in items if item["shipment_id"]])
        context = {
            "intent": "custody",
            "filters": filters,
            "record_count": len(items),
            "custody_checkpoints": items,
            "generated_at_utc": self._to_iso(datetime.utcnow()),
        }
        confidence: Confidence = "high" if len(items) > 0 and filters else ("medium" if items else "low")
        return RetrievalBundle(
            intent="custody",
            context=context,
            sources=sources,
            has_data=bool(items),
            confidence=confidence,
        )

    def _call_openrouter(self, question: str, retrieval: RetrievalBundle) -> Dict[str, Any]:
        if not settings.OPENROUTER_API_KEY:
            raise ChatConfigurationError("OpenRouter is not configured on the server.")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "User question:\n"
                    f"{question}\n\n"
                    "Database context (JSON):\n"
                    f"{json.dumps(retrieval.context, ensure_ascii=True)}"
                ),
            },
        ]

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_APP_NAME:
            headers["X-Title"] = settings.OPENROUTER_APP_NAME

        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": settings.OPENROUTER_MAX_TOKENS,
        }

        logger.info(
            "OpenRouter request model=%s intent=%s context_records=%s",
            settings.OPENROUTER_MODEL,
            retrieval.intent,
            retrieval.context.get("record_count", 0),
        )

        url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
        try:
            with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ChatProviderError("OpenRouter request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            provider_message = ""
            try:
                error_payload = exc.response.json()
                provider_message = str(error_payload.get("error", {}).get("message", "")).strip()
            except ValueError:
                provider_message = ""
            logger.error(
                "OpenRouter HTTP error status=%s body=%s",
                status_code,
                exc.response.text[:500],
            )
            if provider_message:
                raise ChatProviderError(
                    f"OpenRouter request failed ({status_code}): {provider_message}"
                ) from exc
            raise ChatProviderError(f"OpenRouter request failed ({status_code}).") from exc
        except httpx.HTTPError as exc:
            raise ChatProviderError("Unable to reach OpenRouter.") from exc
        except ValueError as exc:
            raise ChatProviderError("Invalid OpenRouter response format.") from exc

        choices = body.get("choices", [])
        if not choices:
            raise ChatProviderError("OpenRouter returned no choices.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if content is None:
            raise ChatProviderError("OpenRouter returned an empty response.")
        return {"content": content}

    def _normalize_llm_response(
        self,
        llm_response: Dict[str, Any],
        retrieval: RetrievalBundle,
    ) -> Tuple[str, List[str], Confidence]:
        raw_content = llm_response.get("content", "")
        text_content = self._content_to_text(raw_content)
        parsed = self._extract_json_object(text_content)

        answer = NO_DATA_MESSAGE
        sources = retrieval.sources
        confidence: Confidence = retrieval.confidence

        if isinstance(parsed, dict):
            candidate_answer = parsed.get("answer")
            if isinstance(candidate_answer, str) and candidate_answer.strip():
                answer = candidate_answer.strip()

            candidate_sources = parsed.get("sources")
            if isinstance(candidate_sources, list):
                allowed_sources = set(retrieval.sources)
                filtered = [str(s) for s in candidate_sources if isinstance(s, (str, int, float))]
                filtered = [s for s in filtered if s in allowed_sources]
                if filtered:
                    sources = self._unique_ordered(filtered)

            candidate_confidence = parsed.get("confidence")
            if isinstance(candidate_confidence, str):
                candidate = candidate_confidence.lower().strip()
                if candidate in ("high", "medium", "low"):
                    confidence = candidate  # type: ignore[assignment]
        elif text_content.strip():
            answer = text_content.strip()

        if answer == NO_DATA_MESSAGE:
            return answer, [], "low"
        return answer, sources, confidence

    def _extract_shipment_code(self, text: str) -> Optional[str]:
        match = re.search(r"\b(?:ship|shp)[-_]?\d{2,6}(?:[-_]\d{2,6})*\b", text, flags=re.IGNORECASE)
        return match.group(0).upper().replace("_", "-") if match else None

    def _extract_device_uid(self, text: str) -> Optional[str]:
        match = re.search(r"\b[A-Z]{2,6}-\d{2,6}(?:-\d{2,6})+\b", text, flags=re.IGNORECASE)
        return match.group(0).upper() if match else None

    def _extract_temperature_filter(self, lowered_question: str) -> Tuple[Optional[float], Optional[str]]:
        pattern = (
            r"(?:temperature|temp)[^0-9\-]{0,40}"
            r"(above|over|greater than|below|under|less than)\s*(-?\d+(?:\.\d+)?)"
        )
        match = re.search(pattern, lowered_question)
        if not match:
            return None, None

        direction, raw_value = match.group(1), match.group(2)
        try:
            value = float(raw_value)
        except ValueError:
            return None, None

        if direction in ("above", "over", "greater than"):
            return value, "above"
        return value, "below"

    def _yesterday_window_utc_naive(self) -> Tuple[datetime, datetime]:
        today = datetime.utcnow().date()
        start = datetime.combine(today - timedelta(days=1), datetime.min.time())
        end = datetime.combine(today, datetime.min.time())
        return start, end

    def _shipment_code_map(self, db: Session, shipment_ids: List[Any]) -> Dict[Any, str]:
        unique_ids = self._unique_ordered([sid for sid in shipment_ids if sid is not None])
        if not unique_ids:
            return {}
        shipments = db.query(Shipment).filter(Shipment.id.in_(unique_ids)).all()
        return {shipment.id: shipment.shipment_code for shipment in shipments}

    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            pieces = []
            for part in content:
                if isinstance(part, dict):
                    pieces.append(str(part.get("text") or part.get("content") or ""))
                else:
                    pieces.append(str(part))
            return "".join(pieces)
        return str(content)

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def _to_iso(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

    def _unique_ordered(self, values: List[Any]) -> List[Any]:
        seen = set()
        output = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output


chat_service = ChatService()
