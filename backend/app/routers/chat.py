from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_roles
from ..models.enums import UserRole
from ..models.user import User
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.chat_service import (
    ChatConfigurationError,
    ChatProviderError,
    chat_service,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def admin_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> ChatResponse:
    try:
        return chat_service.answer_question(payload.message, db, shipment_id=payload.shipment_id)
    except ChatConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ChatProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
