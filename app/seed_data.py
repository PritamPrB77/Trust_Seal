"""
Seed data for TrustSeal IoT application
This script creates initial dummy data for testing purposes
"""

import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from .models import User, Device, Shipment, ShipmentLeg, SensorLog, CustodyCheckpoint
from .models.enums import UserRole, DeviceStatus, ShipmentStatus, LegStatus
from .core.security import get_password_hash

def seed_database():
    """Seed the database with initial dummy data"""
    # Create all tables
    from .database import Base
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Clear existing data
        db.query(CustodyCheckpoint).delete()
        db.query(SensorLog).delete()
        db.query(ShipmentLeg).delete()
        db.query(Shipment).delete()
        db.query(Device).delete()
        db.query(User).delete()
        db.commit()
        
        print("Creating users...")
        # Create users
        users = [
            User(
                name="Administrator",
                email="admin@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.ADMIN,
                is_verified=True,
            ),
            User(
                name="Factory Manager",
                email="factory@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.FACTORY,
                is_verified=True,
            ),
            User(
                name="Warehouse Manager",
                email="warehouse@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.WAREHOUSE,
                is_verified=True,
            ),
            User(
                name="Customer",
                email="customer@trustseal.io",
                password_hash=get_password_hash("pass123"),
                role=UserRole.CUSTOMER,
                is_verified=True,
            )
        ]
        
        for user in users:
            db.add(user)
        db.commit()
        
        # Refresh to get IDs
        for user in users:
            db.refresh(user)
        
        print("Creating device...")
        # Create device
        device = Device(
            device_uid="DEV-2024-001",
            model="TrustSeal-T1000",
            firmware_version="1.2.3",
            battery_capacity_mAh=5000,
            status=DeviceStatus.ACTIVE
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        
        print("Creating shipment...")
        # Create shipment
        shipment = Shipment(
            shipment_code="SHP-2024-001",
            description="Electronics components shipment",
            origin="Factory A, Shenzhen, China",
            destination="Warehouse B, New York, USA",
            status=ShipmentStatus.IN_TRANSIT,
            device_id=str(device.id)
        )
        db.add(shipment)
        db.commit()
        db.refresh(shipment)
        
        print("Creating shipment legs...")
        # Create shipment legs
        legs = [
            ShipmentLeg(
                shipment_id=str(shipment.id),
                leg_number=1,
                from_location="Factory A, Shenzhen, China",
                to_location="Port of Shanghai, China",
                status=LegStatus.SETTLED,
                started_at=datetime.utcnow() - timedelta(days=5),
                completed_at=datetime.utcnow() - timedelta(days=4)
            ),
            ShipmentLeg(
                shipment_id=str(shipment.id),
                leg_number=2,
                from_location="Port of Shanghai, China",
                to_location="Port of New York, USA",
                status=LegStatus.IN_PROGRESS,
                started_at=datetime.utcnow() - timedelta(days=3)
            )
        ]
        
        for leg in legs:
            db.add(leg)
        db.commit()
        
        # Refresh to get IDs
        for leg in legs:
            db.refresh(leg)
        
        print("Creating sensor logs...")
        # Create sensor logs
        base_time = datetime.utcnow() - timedelta(hours=48)
        for i in range(20):
            log_time = base_time + timedelta(hours=i * 2.4)
            
            # Simulate realistic sensor data
            temperature = round(20 + random.uniform(-5, 15), 2)  # 15-35°C
            humidity = round(40 + random.uniform(-10, 30), 2)    # 30-70%
            shock = round(random.uniform(0, 2), 3)               # 0-2g
            light_exposure = random.choice([True, False])
            tilt_angle = round(random.uniform(0, 45), 2)         # 0-45 degrees
            
            # Create a simple hash
            hash_value = f"hash_{i}_{uuid.uuid4().hex[:8]}"
            
            sensor_log = SensorLog(
                shipment_id=str(shipment.id),
                temperature=temperature,
                humidity=humidity,
                shock=shock,
                light_exposure=light_exposure,
                tilt_angle=tilt_angle,
                recorded_at=log_time,
                hash_value=hash_value
            )
            db.add(sensor_log)
        
        db.commit()
        
        print("Creating custody checkpoints...")
        # Create custody checkpoints
        checkpoints = [
            CustodyCheckpoint(
                shipment_id=str(shipment.id),
                leg_id=str(legs[0].id),
                verified_by=str(users[0].id),  # Factory manager
                biometric_verified=True,
                timestamp=datetime.utcnow() - timedelta(days=5),
                blockchain_tx_hash=f"0x{uuid.uuid4().hex[:64]}",
                merkle_root_hash=f"merkle_{uuid.uuid4().hex[:32]}"
            ),
            CustodyCheckpoint(
                shipment_id=str(shipment.id),
                leg_id=str(legs[0].id),
                verified_by=str(users[1].id),  # Warehouse manager
                biometric_verified=True,
                timestamp=datetime.utcnow() - timedelta(days=4),
                blockchain_tx_hash=f"0x{uuid.uuid4().hex[:64]}",
                merkle_root_hash=f"merkle_{uuid.uuid4().hex[:32]}"
            )
        ]
        
        for checkpoint in checkpoints:
            db.add(checkpoint)
        
        db.commit()
        
        print("\n✅ Database seeded successfully!")
        print(f"Created {len(users)} users")
        print(f"Created 1 device")
        print(f"Created 1 shipment")
        print(f"Created {len(legs)} shipment legs")
        print(f"Created 20 sensor logs")
        print(f"Created {len(checkpoints)} custody checkpoints")
        
        print("\n📝 Login credentials:")
        print("Factory Manager: factory@trustseal.io / pass123")
        print("Warehouse Manager: warehouse@trustseal.io / pass123")
        print("Customer: customer@trustseal.io / pass123")
        print("Administrator: admin@trustseal.io / pass123")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
