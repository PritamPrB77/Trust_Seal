from __future__ import annotations

from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_roles
from ..models.enums import UserRole
from ..models.user import User
from ..schemas.soc_agent import (
    InvestigationAuditListResponse,
    SocAssistRequest,
    SocInvestigationResponse,
)
from ..services.soc_agent import (
    SocAgentConfigurationError,
    SocAgentExecutionError,
    soc_agent_service,
)
from ..services.soc_agent.memory import soc_memory_store

router = APIRouter()


@router.post("/soc/assist", response_model=SocInvestigationResponse)
async def soc_assist(
    payload: SocAssistRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> SocInvestigationResponse:
    _ = current_user
    try:
        return await soc_agent_service.investigate(payload, db)
    except SocAgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SocAgentExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/soc/assist/stream")
async def soc_assist_stream(
    payload: SocAssistRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> StreamingResponse:
    _ = current_user

    async def stream() -> AsyncIterator[str]:
        async for chunk in soc_agent_service.stream_investigation(payload, db):
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/soc/investigations", response_model=InvestigationAuditListResponse)
async def list_soc_investigations(
    session_id: Optional[str] = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> InvestigationAuditListResponse:
    _ = current_user
    records = soc_memory_store.list_investigation_memory(
        db=db,
        session_id=session_id,
        limit=limit,
    )
    return InvestigationAuditListResponse(records=records)
