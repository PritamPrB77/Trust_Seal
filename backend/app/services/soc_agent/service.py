from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...core.config import settings
from ...schemas.soc_agent import (
    HistoricalMemoryMatch,
    ParsedSocOutput,
    RootCauseHypothesis,
    SocAssistRequest,
    SocInvestigationResponse,
)
from .agent import SocAgentConfigurationError, build_soc_agent_runnable
from .memory import soc_memory_store

logger = logging.getLogger(__name__)

ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
ALLOWED_ROOT_CAUSES = {
    "environmental_noise",
    "firmware_issue",
    "possible_intrusion",
    "misconfiguration",
    "hardware_degradation",
}


class SocAgentExecutionError(Exception):
    pass


class SocAgentService:
    def _build_agent_input(self, request: SocAssistRequest) -> str:
        payload = {
            "question": request.question,
            "session_id": request.session_id,
            "device_uid": request.device_uid,
            "shipment_id": request.shipment_id,
            "top_k": request.top_k or settings.SOC_AGENT_TOP_K,
            "live_logs_count": len(request.logs),
            "live_logs": [entry.model_dump(mode="json") for entry in request.logs[:150]],
        }
        return json.dumps(payload, ensure_ascii=True)

    def _build_runnable_input(self, request: SocAssistRequest, mode: str) -> Dict[str, Any]:
        user_payload = self._build_agent_input(request)
        if mode == "modern":
            return {"messages": [{"role": "user", "content": user_payload}]}
        return {"input": user_payload}

    def _with_history(self, runnable: Any, mode: str, db: Session) -> RunnableWithMessageHistory:
        input_key = "messages" if mode == "modern" else "input"
        output_key = "messages" if mode == "modern" else "output"
        return RunnableWithMessageHistory(
            runnable,
            get_session_history=lambda session_id: soc_memory_store.get_message_history(db, session_id),
            input_messages_key=input_key,
            output_messages_key=output_key,
        )

    def _to_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: List[str] = []
            for item in value:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(item))
            return "".join(parts)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=True)
        return str(value)

    def _extract_json(self, text_value: str) -> Optional[Dict[str, Any]]:
        raw = text_value.strip()
        if not raw:
            return None

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def _normalize_root_cause_analysis(self, value: Any) -> List[RootCauseHypothesis]:
        if not isinstance(value, list):
            value = []

        output: List[RootCauseHypothesis] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            cause = str(item.get("cause") or "").strip().lower()
            if cause not in ALLOWED_ROOT_CAUSES:
                continue
            try:
                probability = float(item.get("probability", 0.0))
            except (TypeError, ValueError):
                probability = 0.0
            probability = max(0.0, min(1.0, probability))
            rationale = str(item.get("rationale") or "No rationale provided.")
            output.append(
                RootCauseHypothesis(
                    cause=cause,  # type: ignore[arg-type]
                    probability=probability,
                    rationale=rationale,
                )
            )

        if not output:
            return [
                RootCauseHypothesis(
                    cause="environmental_noise",
                    probability=0.2,
                    rationale="Insufficient evidence returned by the agent.",
                ),
                RootCauseHypothesis(
                    cause="firmware_issue",
                    probability=0.2,
                    rationale="Insufficient evidence returned by the agent.",
                ),
                RootCauseHypothesis(
                    cause="possible_intrusion",
                    probability=0.2,
                    rationale="Insufficient evidence returned by the agent.",
                ),
                RootCauseHypothesis(
                    cause="misconfiguration",
                    probability=0.2,
                    rationale="Insufficient evidence returned by the agent.",
                ),
                RootCauseHypothesis(
                    cause="hardware_degradation",
                    probability=0.2,
                    rationale="Insufficient evidence returned by the agent.",
                ),
            ]

        total = sum(item.probability for item in output)
        if total > 0:
            output = [
                RootCauseHypothesis(
                    cause=item.cause,
                    probability=round(item.probability / total, 4),
                    rationale=item.rationale,
                )
                for item in output
            ]

        return output

    def _normalize_memory_matches(self, value: Any) -> List[HistoricalMemoryMatch]:
        if not isinstance(value, list):
            return []

        matches: List[HistoricalMemoryMatch] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            risk = str(item.get("risk_level", "medium")).lower().strip()
            if risk not in ALLOWED_RISK_LEVELS:
                risk = "medium"

            payload = {
                "memory_id": str(item.get("memory_id") or ""),
                "similarity": max(0.0, min(1.0, float(item.get("similarity", 0.0)))),
                "summary": str(item.get("summary") or ""),
                "root_cause": str(item.get("root_cause") or ""),
                "resolution": str(item.get("resolution") or ""),
                "risk_level": risk,
                "created_at": item.get("created_at"),
            }
            try:
                matches.append(HistoricalMemoryMatch.model_validate(payload))
            except (ValidationError, ValueError, TypeError):
                continue

        return matches

    def _parse_soc_output(self, raw_output: str) -> ParsedSocOutput:
        payload = self._extract_json(raw_output)
        if not payload:
            return ParsedSocOutput(
                issue_summary=raw_output.strip() or "Insufficient structured output from agent.",
                investigation_steps_taken=[
                    "Agent response could not be parsed as JSON. Review `raw_output` for details."
                ],
                context_retrieved=[],
                historical_memory_matches=[],
                root_cause_analysis=self._normalize_root_cause_analysis([]),
                risk_level="medium",
                confidence_score=0.5,
                recommended_action=[
                    "Re-run investigation with additional logs and explicit incident context.",
                ],
            )

        issue_summary = str(payload.get("issue_summary") or "").strip()
        if not issue_summary:
            issue_summary = "Insufficient data to provide a confident SOC issue summary."

        steps = payload.get("investigation_steps_taken")
        if not isinstance(steps, list):
            steps = []
        steps_text = [str(step).strip() for step in steps if str(step).strip()]

        context_retrieved = payload.get("context_retrieved")
        if not isinstance(context_retrieved, list):
            context_retrieved = []
        context_text = [str(item).strip() for item in context_retrieved if str(item).strip()]

        risk_level = str(payload.get("risk_level", "medium")).lower().strip()
        if risk_level not in ALLOWED_RISK_LEVELS:
            risk_level = "medium"

        try:
            confidence_score = float(payload.get("confidence_score", 0.5))
        except (TypeError, ValueError):
            confidence_score = 0.5
        confidence_score = max(0.0, min(1.0, confidence_score))

        actions = payload.get("recommended_action")
        if not isinstance(actions, list):
            actions = []
        action_text = [str(action).strip() for action in actions if str(action).strip()]

        return ParsedSocOutput(
            issue_summary=issue_summary,
            investigation_steps_taken=steps_text,
            context_retrieved=context_text,
            historical_memory_matches=self._normalize_memory_matches(
                payload.get("historical_memory_matches")
            ),
            root_cause_analysis=self._normalize_root_cause_analysis(payload.get("root_cause_analysis")),
            risk_level=risk_level,  # type: ignore[arg-type]
            confidence_score=confidence_score,
            recommended_action=action_text,
        )

    def _format_legacy_tool_trace(self, intermediate_steps: Any) -> List[str]:
        if not isinstance(intermediate_steps, list):
            return []

        trace: List[str] = []
        for item in intermediate_steps:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            action, observation = item
            tool_name = str(getattr(action, "tool", "unknown_tool"))
            tool_input = getattr(action, "tool_input", {})
            observation_text = self._to_text(observation)
            if len(observation_text) > settings.SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS:
                observation_text = (
                    observation_text[: settings.SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS] + "..."
                )
            trace.append(
                f"{tool_name} | input={self._to_text(tool_input)} | output={observation_text}"
            )
        return trace

    def _extract_message_type(self, message: Any) -> str:
        if hasattr(message, "type"):
            return str(getattr(message, "type"))
        if isinstance(message, dict):
            return str(message.get("type") or message.get("role") or "")
        return ""

    def _extract_message_content(self, message: Any) -> str:
        if hasattr(message, "content"):
            return self._to_text(getattr(message, "content"))
        if isinstance(message, dict):
            return self._to_text(message.get("content"))
        return self._to_text(message)

    def _extract_modern_tool_trace(self, raw: Any) -> List[str]:
        if not isinstance(raw, dict):
            return []
        messages = raw.get("messages")
        if not isinstance(messages, list):
            return []

        trace: List[str] = []
        for message in messages:
            if self._extract_message_type(message) != "tool":
                continue
            tool_name = str(getattr(message, "name", None) or (message.get("name") if isinstance(message, dict) else "tool"))  # type: ignore[union-attr]
            output = self._extract_message_content(message)
            if len(output) > settings.SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS:
                output = output[: settings.SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS] + "..."
            trace.append(f"{tool_name} | output={output}")
        return trace

    def _extract_raw_output(self, raw: Any, mode: str) -> str:
        if mode == "legacy":
            if isinstance(raw, dict):
                return self._to_text(raw.get("output", ""))
            return self._to_text(raw)

        if isinstance(raw, dict):
            messages = raw.get("messages")
            if isinstance(messages, list):
                for message in reversed(messages):
                    if self._extract_message_type(message) != "ai":
                        continue
                    text_value = self._extract_message_content(message)
                    if text_value.strip():
                        return text_value
            if "output" in raw:
                return self._to_text(raw.get("output"))
        return self._to_text(raw)

    def _extract_tool_trace(self, raw: Any, mode: str) -> List[str]:
        if mode == "legacy":
            if isinstance(raw, dict):
                return self._format_legacy_tool_trace(raw.get("intermediate_steps"))
            return []
        return self._extract_modern_tool_trace(raw)

    def _extract_tool_names(self, tool_trace: List[str]) -> List[str]:
        names: List[str] = []
        seen = set()
        for line in tool_trace:
            name = line.split("|", 1)[0].strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        return names

    def _event(self, event: str, payload: Dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"

    def _extract_stream_chunk_text(self, chunk: Any) -> str:
        if chunk is None:
            return ""
        content = getattr(chunk, "content", None)
        if content is None and isinstance(chunk, dict):
            content = chunk.get("content")
        return self._to_text(content)

    async def investigate(self, request: SocAssistRequest, db: Session) -> SocInvestigationResponse:
        try:
            soc_memory_store.ensure_tables(db)
            runnable, mode = build_soc_agent_runnable(db=db, request=request, streaming=False)
            runnable_with_history = self._with_history(runnable=runnable, mode=mode, db=db)
            raw = await runnable_with_history.ainvoke(
                self._build_runnable_input(request, mode),
                config={"configurable": {"session_id": request.session_id}},
            )
        except SocAgentConfigurationError:
            raise
        except Exception as exc:
            logger.exception("SOC agent execution failed")
            raise SocAgentExecutionError(f"SOC agent execution failed: {exc}") from exc

        raw_output = self._extract_raw_output(raw, mode)
        parsed = self._parse_soc_output(raw_output)
        tool_trace = self._extract_tool_trace(raw, mode)

        investigation_id = soc_memory_store.persist_investigation_memory(
            db=db,
            request=request,
            parsed=parsed,
            tools_used=self._extract_tool_names(tool_trace),
        )

        return SocInvestigationResponse(
            investigation_id=investigation_id,
            issue_summary=parsed.issue_summary,
            investigation_steps_taken=parsed.investigation_steps_taken,
            context_retrieved=parsed.context_retrieved,
            historical_memory_matches=parsed.historical_memory_matches,
            root_cause_analysis=parsed.root_cause_analysis,
            risk_level=parsed.risk_level,
            confidence_score=parsed.confidence_score,
            recommended_action=parsed.recommended_action,
            tool_trace=tool_trace,
            raw_output=raw_output,
        )

    async def stream_investigation(
        self, request: SocAssistRequest, db: Session
    ) -> AsyncIterator[str]:
        try:
            soc_memory_store.ensure_tables(db)
            runnable, mode = build_soc_agent_runnable(db=db, request=request, streaming=True)
            runnable_with_history = self._with_history(runnable=runnable, mode=mode, db=db)
        except SocAgentConfigurationError as exc:
            yield self._event("error", {"message": str(exc)})
            return

        yielded_tools: List[str] = []
        raw_output = ""

        yield self._event(
            "status",
            {
                "message": "SOC investigation started.",
                "session_id": request.session_id,
                "live_logs_count": len(request.logs),
            },
        )

        try:
            async for event in runnable_with_history.astream_events(
                self._build_runnable_input(request, mode),
                config={"configurable": {"session_id": request.session_id}},
                version="v1",
            ):
                event_name = str(event.get("event") or "")
                runnable_name = str(event.get("name") or "")
                data = event.get("data") or {}

                if event_name == "on_tool_start":
                    yield self._event(
                        "tool_start",
                        {"tool": runnable_name, "input": self._to_text(data.get("input"))},
                    )
                elif event_name == "on_tool_end":
                    output_text = self._to_text(data.get("output"))
                    if len(output_text) > settings.SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS:
                        output_text = (
                            output_text[: settings.SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS] + "..."
                        )
                    yielded_tools.append(runnable_name)
                    yield self._event(
                        "tool_end",
                        {"tool": runnable_name, "output": output_text},
                    )
                elif event_name == "on_chat_model_stream":
                    token_text = self._extract_stream_chunk_text(data.get("chunk"))
                    if token_text:
                        yield self._event("token", {"text": token_text})
                elif event_name == "on_chain_end":
                    candidate = self._extract_raw_output(data.get("output"), mode)
                    if candidate.strip():
                        raw_output = candidate

            if not raw_output:
                yield self._event(
                    "error",
                    {"message": "Streaming finished without a final model output payload."},
                )
                return

            parsed = self._parse_soc_output(raw_output)
            investigation_id = soc_memory_store.persist_investigation_memory(
                db=db,
                request=request,
                parsed=parsed,
                tools_used=yielded_tools,
            )

            yield self._event(
                "final",
                {
                    "investigation_id": investigation_id,
                    "issue_summary": parsed.issue_summary,
                    "investigation_steps_taken": parsed.investigation_steps_taken,
                    "context_retrieved": parsed.context_retrieved,
                    "historical_memory_matches": [
                        item.model_dump(mode="json") for item in parsed.historical_memory_matches
                    ],
                    "root_cause_analysis": [
                        item.model_dump(mode="json") for item in parsed.root_cause_analysis
                    ],
                    "risk_level": parsed.risk_level,
                    "confidence_score": parsed.confidence_score,
                    "recommended_action": parsed.recommended_action,
                    "raw_output": raw_output,
                },
            )
            yield self._event("done", {"message": "SOC investigation completed."})
        except Exception as exc:
            logger.exception("SOC streaming execution failed")
            yield self._event("error", {"message": f"SOC streaming execution failed: {exc}"})


soc_agent_service = SocAgentService()
