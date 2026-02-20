from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dependencies import get_current_user
from ..database import get_db
from ..schemas.user import User as UserSchema

router = APIRouter()


@router.get("/whoami", response_model=UserSchema)
def whoami(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Dev helper: return the current authenticated user (whoami).

    Use this to verify that the Authorization header reaches the backend
    and that the token decodes to a valid user.
    """
    return current_user
