from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class SensorLogBase(BaseModel):
    shipment_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    shock: Optional[float] = None
    light_exposure: Optional[bool] = False
    tilt_angle: Optional[float] = None
    hash_value: str

    @field_validator('shipment_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

class SensorLogCreate(SensorLogBase):
    pass

class SensorLog(SensorLogBase):
    id: str
    recorded_at: datetime

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if v else None

    class Config:
        from_attributes = True
