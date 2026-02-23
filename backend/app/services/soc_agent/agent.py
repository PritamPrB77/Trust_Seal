from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ...core.config import settings
from ...schemas.soc_agent import SocAssistRequest
from .prompts import SOC_SYSTEM_PROMPT, build_agent_prompt
from .tools import SocToolFactory

class SocAgentConfigurationError(Exception):
    pass


try:
    from langchain_openai import ChatOpenAI
except Exception as exc:  # pragma: no cover - import guarded for runtime setup
    ChatOpenAI = None  # type: ignore[assignment]
    _chat_openai_import_error: Optional[Exception] = exc
else:
    _chat_openai_import_error = None

try:
    from langchain.agents import create_agent as _create_modern_agent
except Exception:
    _create_modern_agent = None

try:
    from langchain.agents import AgentExecutor as _LegacyAgentExecutor
    from langchain.agents import create_tool_calling_agent as _create_legacy_tool_agent
except Exception:
    _LegacyAgentExecutor = None
    _create_legacy_tool_agent = None


def _build_openrouter_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if settings.OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
    if settings.OPENROUTER_APP_NAME:
        headers["X-Title"] = settings.OPENROUTER_APP_NAME
    return headers


def _build_chat_model(streaming: bool = False) -> Any:
    if ChatOpenAI is None:
        raise SocAgentConfigurationError(
            "langchain-openai is not installed. Install dependencies from backend/requirements.txt."
        ) from _chat_openai_import_error

    if not settings.OPENROUTER_API_KEY:
        raise SocAgentConfigurationError("OPENROUTER_API_KEY is required for SOC agent execution.")

    kwargs: Dict[str, Any] = {
        "model": settings.SOC_AGENT_MODEL,
        "temperature": 1.0,
        "timeout": settings.SOC_AGENT_TIMEOUT_SECONDS,
        "max_tokens": settings.OPENROUTER_MAX_TOKENS,
        "streaming": streaming,
    }

    headers = _build_openrouter_headers()
    if headers:
        kwargs["default_headers"] = headers

    # Prefer the new parameter names while keeping fallback aliases for compatibility.
    try:
        return ChatOpenAI(
            **kwargs,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL.rstrip("/"),
        )
    except TypeError:
        return ChatOpenAI(
            **kwargs,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base=settings.OPENROUTER_BASE_URL.rstrip("/"),
        )


def build_soc_agent_runnable(
    db: Session,
    request: SocAssistRequest,
    streaming: bool = False,
) -> tuple[Any, str]:
    tools = SocToolFactory(
        db=db,
        top_k=request.top_k or settings.SOC_AGENT_TOP_K,
        logs=request.logs,
        device_uid=request.device_uid,
        shipment_id=request.shipment_id,
    ).build()
    llm = _build_chat_model(streaming=streaming)

    if _create_modern_agent is not None:
        runnable = _create_modern_agent(
            model=llm,
            tools=tools,
            system_prompt=SOC_SYSTEM_PROMPT,
        )
        return runnable, "modern"

    if _LegacyAgentExecutor is not None and _create_legacy_tool_agent is not None:
        prompt = build_agent_prompt()
        agent = _create_legacy_tool_agent(llm=llm, tools=tools, prompt=prompt)
        runnable = _LegacyAgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=settings.SOC_AGENT_MAX_ITERATIONS,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            verbose=False,
        )
        return runnable, "legacy"

    raise SocAgentConfigurationError(
        "No supported LangChain agent API found. "
        "Install langchain>=0.2,<2 and langchain-openai."
    )
