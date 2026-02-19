from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from ..models.user import User
from ..models.sensor_log import SensorLog
from ..models.shipment import Shipment
from ..models.enums import UserRole
from ..schemas.sensor_log import SensorLog as SensorLogSchema, SensorLogCreate
from ..database import get_db
from ..dependencies import get_current_active_user, require_roles
from ..services.realtime import build_realtime_event, shipment_event_dispatcher

router = APIRouter()


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}")

@router.get("", response_model=List[SensorLogSchema], include_in_schema=False)
@router.get("/", response_model=List[SensorLogSchema])
def get_sensor_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shipment_id: Optional[uuid.UUID] = Query(None),
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
    shipment_uuid = _parse_uuid(log.shipment_id, "shipment_id")

    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_uuid).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    payload = log.dict()
    payload["shipment_id"] = shipment_uuid
    db_log = SensorLog(**payload)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    log_payload = SensorLogSchema.model_validate(db_log).model_dump(mode="json")
    shipment_event_dispatcher.publish(
        str(shipment_uuid),
        build_realtime_event(
            event="sensor_log.created",
            shipment_id=str(shipment_uuid),
            data={"log": log_payload},
        ),
    )

    return db_log

@router.get("/{log_id}", response_model=SensorLogSchema)
def get_sensor_log(
    log_id: uuid.UUID,
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
    log_id: uuid.UUID,
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
