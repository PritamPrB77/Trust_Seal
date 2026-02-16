from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..models.user import User
from ..models.shipment import Shipment, ShipmentLeg
from ..models.sensor_log import SensorLog
from ..schemas.shipment import Shipment as ShipmentSchema, ShipmentCreate, ShipmentUpdate, ShipmentWithDetails
from ..schemas.sensor_log import SensorLogCreate
from ..database import get_db
from ..dependencies import get_current_active_user

router = APIRouter()

@router.get("/", response_model=List[ShipmentSchema])
def get_shipments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all shipments with optional filtering"""
    query = db.query(Shipment)
    
    if status:
        query = query.filter(Shipment.status == status)
    
    shipments = query.offset(skip).limit(limit).all()
    return shipments

@router.post("/", response_model=ShipmentSchema)
def create_shipment(
    shipment: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new shipment"""
    # Check if shipment_code already exists
    existing_shipment = db.query(Shipment).filter(Shipment.shipment_code == shipment.shipment_code).first()
    if existing_shipment:
        raise HTTPException(status_code=400, detail="Shipment code already exists")
    
    db_shipment = Shipment(**shipment.dict())
    db.add(db_shipment)
    db.commit()
    db.refresh(db_shipment)
    return db_shipment

@router.get("/{shipment_id}", response_model=ShipmentWithDetails)
def get_shipment(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific shipment with full details"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment

@router.put("/{shipment_id}", response_model=ShipmentSchema)
def update_shipment(
    shipment_id: str,
    shipment_update: ShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a shipment"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    update_data = shipment_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shipment, field, value)
    
    db.commit()
    db.refresh(shipment)
    return shipment

@router.post("/{shipment_id}/logs", response_model=List[SensorLogCreate])
def add_sensor_logs(
    shipment_id: str,
    logs: List[SensorLogCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add sensor logs to a shipment"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Create sensor logs
    db_logs = []
    for log_data in logs:
        log_data.shipment_id = shipment_id
        db_log = SensorLog(**log_data.dict())
        db.add(db_log)
        db_logs.append(db_log)
    
    db.commit()
    for db_log in db_logs:
        db.refresh(db_log)
    
    return db_logs

@router.get("/{shipment_id}/logs", response_model=List[SensorLogCreate])
def get_sensor_logs(
    shipment_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get sensor logs for a specific shipment"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    logs = db.query(SensorLog).filter(SensorLog.shipment_id == shipment_id).offset(skip).limit(limit).all()
    return logs

@router.post("/{shipment_id}/settle")
def settle_shipment(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Settle a shipment (mark as completed)"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Update shipment status to completed
    from ..models.enums import ShipmentStatus
    shipment.status = ShipmentStatus.COMPLETED
    
    # Complete all pending legs
    pending_legs = db.query(ShipmentLeg).filter(
        ShipmentLeg.shipment_id == shipment_id,
        ShipmentLeg.status != "settled"
    ).all()
    
    from ..models.enums import LegStatus
    for leg in pending_legs:
        leg.status = LegStatus.SETTLED
        leg.completed_at = datetime.utcnow()
    
    db.commit()
    return {"message": "Shipment settled successfully"}
