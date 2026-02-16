from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..models.user import User
from ..models.shipment import Shipment, ShipmentLeg
from ..schemas.leg import ShipmentLeg as ShipmentLegSchema, ShipmentLegCreate, ShipmentLegUpdate
from ..database import get_db
from ..dependencies import get_current_active_user

router = APIRouter()

@router.get("/", response_model=List[ShipmentLegSchema])
def get_shipment_legs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shipment_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all shipment legs with optional filtering"""
    query = db.query(ShipmentLeg)
    
    if shipment_id:
        # Verify shipment exists
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        query = query.filter(ShipmentLeg.shipment_id == shipment_id)
    
    legs = query.order_by(ShipmentLeg.leg_number).offset(skip).limit(limit).all()
    return legs

@router.post("/", response_model=ShipmentLegSchema)
def create_shipment_leg(
    leg: ShipmentLegCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new shipment leg"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == leg.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Check if leg number already exists for this shipment
    existing_leg = db.query(ShipmentLeg).filter(
        ShipmentLeg.shipment_id == leg.shipment_id,
        ShipmentLeg.leg_number == leg.leg_number
    ).first()
    if existing_leg:
        raise HTTPException(status_code=400, detail="Leg number already exists for this shipment")
    
    db_leg = ShipmentLeg(**leg.dict())
    db.add(db_leg)
    db.commit()
    db.refresh(db_leg)
    return db_leg

@router.get("/{leg_id}", response_model=ShipmentLegSchema)
def get_shipment_leg(
    leg_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific shipment leg by ID"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    return leg

@router.put("/{leg_id}", response_model=ShipmentLegSchema)
def update_shipment_leg(
    leg_id: str,
    leg_update: ShipmentLegUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    update_data = leg_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(leg, field, value)
    
    db.commit()
    db.refresh(leg)
    return leg

@router.post("/{leg_id}/start")
def start_shipment_leg(
    leg_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Start a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    from ..models.enums import LegStatus
    leg.status = LegStatus.IN_PROGRESS
    leg.started_at = datetime.utcnow()
    
    db.commit()
    return {"message": "Shipment leg started successfully"}

@router.post("/{leg_id}/complete")
def complete_shipment_leg(
    leg_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Complete a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    from ..models.enums import LegStatus
    leg.status = LegStatus.SETTLED
    leg.completed_at = datetime.utcnow()
    
    db.commit()
    return {"message": "Shipment leg completed successfully"}

@router.delete("/{leg_id}")
def delete_shipment_leg(
    leg_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    db.delete(leg)
    db.commit()
    return {"message": "Shipment leg deleted successfully"}
