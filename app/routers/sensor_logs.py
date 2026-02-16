from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ..models.user import User
from ..models.sensor_log import SensorLog
from ..models.shipment import Shipment
from ..models.enums import UserRole
from ..schemas.sensor_log import SensorLog as SensorLogSchema, SensorLogCreate
from ..database import get_db
from ..dependencies import get_current_active_user, require_roles

router = APIRouter()

@router.get("", response_model=List[SensorLogSchema], include_in_schema=False)
@router.get("/", response_model=List[SensorLogSchema])
def get_sensor_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shipment_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all sensor logs with optional filtering"""
    query = db.query(SensorLog)
    
    if shipment_id:
        # Verify shipment exists
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        query = query.filter(SensorLog.shipment_id == shipment_id)
    
    logs = query.offset(skip).limit(limit).all()
    return logs

@router.post("/", response_model=SensorLogSchema)
def create_sensor_log(
    log: SensorLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.FACTORY, UserRole.PORT, UserRole.WAREHOUSE)
    ),
):
    """Create a new sensor log"""
    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == log.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    db_log = SensorLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@router.get("/{log_id}", response_model=SensorLogSchema)
def get_sensor_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific sensor log by ID"""
    log = db.query(SensorLog).filter(SensorLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Sensor log not found")
    return log

@router.delete("/{log_id}")
def delete_sensor_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a sensor log"""
    log = db.query(SensorLog).filter(SensorLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Sensor log not found")
    
    db.delete(log)
    db.commit()
    return {"message": "Sensor log deleted successfully"}
