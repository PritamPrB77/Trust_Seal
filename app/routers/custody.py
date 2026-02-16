from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ..models.user import User
from ..models.custody_checkpoint import CustodyCheckpoint
from ..models.shipment import Shipment
from ..models.enums import UserRole
from ..schemas.custody import CustodyCheckpoint as CustodyCheckpointSchema, CustodyCheckpointCreate, CustodyCheckpointUpdate
from ..database import get_db
from ..dependencies import get_current_active_user, require_roles

router = APIRouter()

@router.get("", response_model=List[CustodyCheckpointSchema], include_in_schema=False)
@router.get("/", response_model=List[CustodyCheckpointSchema])
def get_custody_checkpoints(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shipment_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all custody checkpoints with optional filtering"""
    query = db.query(CustodyCheckpoint)
    
    if shipment_id:
        # Verify shipment exists
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        query = query.filter(CustodyCheckpoint.shipment_id == shipment_id)
    
    checkpoints = query.offset(skip).limit(limit).all()
    return checkpoints

@router.post("/", response_model=CustodyCheckpointSchema)
def create_custody_checkpoint(
    checkpoint: CustodyCheckpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FACTORY, UserRole.PORT, UserRole.WAREHOUSE)
    ),
):
    """Create a new custody checkpoint"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == checkpoint.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Set verified_by to current user if not provided
    if not checkpoint.verified_by:
        checkpoint.verified_by = str(current_user.id)
    
    db_checkpoint = CustodyCheckpoint(**checkpoint.dict())
    db.add(db_checkpoint)
    db.commit()
    db.refresh(db_checkpoint)
    return db_checkpoint

@router.get("/{checkpoint_id}", response_model=CustodyCheckpointSchema)
def get_custody_checkpoint(
    checkpoint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific custody checkpoint by ID"""
    checkpoint = db.query(CustodyCheckpoint).filter(CustodyCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Custody checkpoint not found")
    return checkpoint

@router.put("/{checkpoint_id}", response_model=CustodyCheckpointSchema)
def update_custody_checkpoint(
    checkpoint_id: str,
    checkpoint_update: CustodyCheckpointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FACTORY, UserRole.PORT, UserRole.WAREHOUSE)
    ),
):
    """Update a custody checkpoint"""
    checkpoint = db.query(CustodyCheckpoint).filter(CustodyCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Custody checkpoint not found")
    
    update_data = checkpoint_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(checkpoint, field, value)
    
    db.commit()
    db.refresh(checkpoint)
    return checkpoint

@router.delete("/{checkpoint_id}")
def delete_custody_checkpoint(
    checkpoint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a custody checkpoint"""
    checkpoint = db.query(CustodyCheckpoint).filter(CustodyCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Custody checkpoint not found")
    
    db.delete(checkpoint)
    db.commit()
    return {"message": "Custody checkpoint deleted successfully"}
