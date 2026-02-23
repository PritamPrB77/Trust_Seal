"""
Seed data for TrustSeal IoT application.
This script creates initial dummy data for testing purposes.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from .core.security import get_password_hash
from .database import SessionLocal, engine
from .models import CustodyCheckpoint, Device, SensorLog, Shipment, ShipmentLeg, User
from .models.enums import DeviceStatus, LegStatus, ShipmentStatus, UserRole


def _shipment_profile_for_index(index: int) -> dict[str, object]:
    if index % 2 == 0:
        return {
            "status": ShipmentStatus.IN_TRANSIT,
            "description": "Electronics components shipment",
            "origin": "Factory A, Shenzhen, China",
            "destination": "Warehouse B, New York, USA",
            "temperature_range": (15.0, 36.0),
            "humidity_range": (30.0, 72.0),
            "shock_range": (0.0, 2.5),
            "tilt_range": (0.0, 48.0),
            "log_count": 24,
        }
    return {
        "status": ShipmentStatus.DOCKING,
        "description": "Pharmaceutical cold-chain shipment",
        "origin": "Biotech Plant C, Singapore",
        "destination": "Medical Hub D, Los Angeles, USA",
        "temperature_range": (2.0, 9.0),
        "humidity_range": (35.0, 62.0),
        "shock_range": (0.0, 3.0),
        "tilt_range": (0.0, 40.0),
        "log_count": 28,
    }


def seed_database() -> None:
    """Seed the database with initial dummy data."""
    from .database import Base

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Clear existing data in child -> parent order.
        db.query(CustodyCheckpoint).delete()
        db.query(SensorLog).delete()
        db.query(ShipmentLeg).delete()
        db.query(Shipment).delete()
        db.query(Device).delete()
        db.query(User).delete()
        db.commit()

        print("Creating users...")
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
            ),
        ]
        db.add_all(users)
        db.commit()
        for user in users:
            db.refresh(user)

        print("Creating devices, shipments, legs, sensor logs, and checkpoints...")
        now = datetime.now(timezone.utc)
        rng = random.Random()

        devices = [
            Device(
                device_uid="DEV-2024-001",
                model="TrustSeal-T1000",
                firmware_version="1.2.3",
                battery_capacity_mAh=5000,
                status=DeviceStatus.ACTIVE,
            ),
            Device(
                device_uid="DEV-2024-002",
                model="TrustSeal-X2000",
                firmware_version="2.0.1",
                battery_capacity_mAh=6200,
                status=DeviceStatus.ACTIVE,
            ),
        ]
        db.add_all(devices)
        db.commit()
        for device in devices:
            db.refresh(device)

        shipments: list[Shipment] = []
        all_legs: list[ShipmentLeg] = []
        all_checkpoints: list[CustodyCheckpoint] = []
        total_sensor_logs = 0

        for idx, device in enumerate(devices, start=1):
            profile = _shipment_profile_for_index(idx)
            shipment = Shipment(
                shipment_code=f"SHP-2024-00{idx}",
                description=str(profile["description"]),
                origin=str(profile["origin"]),
                destination=str(profile["destination"]),
                status=profile["status"],  # type: ignore[arg-type]
                device_id=device.id,
            )
            db.add(shipment)
            db.commit()
            db.refresh(shipment)
            shipments.append(shipment)

            legs = [
                ShipmentLeg(
                    shipment_id=shipment.id,
                    leg_number=1,
                    from_location=str(profile["origin"]),
                    to_location="Port staging area",
                    status=LegStatus.SETTLED,
                    started_at=now - timedelta(days=6 + idx),
                    completed_at=now - timedelta(days=5 + idx),
                ),
                ShipmentLeg(
                    shipment_id=shipment.id,
                    leg_number=2,
                    from_location="Port staging area",
                    to_location="International transit corridor",
                    status=LegStatus.SETTLED if idx % 2 == 0 else LegStatus.IN_PROGRESS,
                    started_at=now - timedelta(days=4 + idx),
                    completed_at=(now - timedelta(days=3 + idx)) if idx % 2 == 0 else None,
                ),
                ShipmentLeg(
                    shipment_id=shipment.id,
                    leg_number=3,
                    from_location="International transit corridor",
                    to_location=str(profile["destination"]),
                    status=LegStatus.PENDING if idx % 2 == 0 else LegStatus.IN_PROGRESS,
                    started_at=(now - timedelta(days=1 + idx)) if idx % 2 != 0 else None,
                ),
            ]
            db.add_all(legs)
            db.commit()
            for leg in legs:
                db.refresh(leg)
                all_legs.append(leg)

            log_count = int(profile["log_count"])
            base_time = now - timedelta(hours=(log_count * 2))
            temp_low, temp_high = profile["temperature_range"]  # type: ignore[misc]
            humidity_low, humidity_high = profile["humidity_range"]  # type: ignore[misc]
            shock_low, shock_high = profile["shock_range"]  # type: ignore[misc]
            tilt_low, tilt_high = profile["tilt_range"]  # type: ignore[misc]

            for i in range(log_count):
                # Inject occasional spikes for richer anomaly examples.
                shock = rng.uniform(shock_low, shock_high)
                if i % 11 == 0:
                    shock += rng.uniform(1.0, 2.0)
                temperature = rng.uniform(temp_low, temp_high)
                if idx % 2 == 0 and i % 9 == 0:
                    temperature -= rng.uniform(1.0, 2.5)

                db.add(
                    SensorLog(
                        shipment_id=shipment.id,
                        temperature=round(temperature, 2),
                        humidity=round(rng.uniform(humidity_low, humidity_high), 2),
                        shock=round(shock, 3),
                        light_exposure=(i % (6 + idx) == 0),
                        tilt_angle=round(rng.uniform(tilt_low, tilt_high), 2),
                        recorded_at=base_time + timedelta(hours=i * 2),
                        hash_value=f"hash_{shipment.shipment_code}_{i}_{uuid.uuid4().hex[:8]}",
                    )
                )
                total_sensor_logs += 1
            db.commit()

            checkpoints = [
                CustodyCheckpoint(
                    shipment_id=shipment.id,
                    leg_id=legs[0].id,
                    verified_by=users[0].id,
                    biometric_verified=True,
                    timestamp=now - timedelta(days=6 + idx),
                    blockchain_tx_hash=f"0x{uuid.uuid4().hex}",
                    merkle_root_hash=f"merkle_{uuid.uuid4().hex}",
                ),
                CustodyCheckpoint(
                    shipment_id=shipment.id,
                    leg_id=legs[1].id,
                    verified_by=users[1].id,
                    biometric_verified=(idx % 2 == 0),
                    timestamp=now - timedelta(days=4 + idx),
                    blockchain_tx_hash=f"0x{uuid.uuid4().hex}",
                    merkle_root_hash=f"merkle_{uuid.uuid4().hex}",
                ),
            ]
            db.add_all(checkpoints)
            db.commit()
            all_checkpoints.extend(checkpoints)

        print("\nDatabase seeded successfully!")
        print(f"Created {len(users)} users")
        print(f"Created {len(devices)} devices")
        print(f"Created {len(shipments)} shipments")
        print(f"Created {len(all_legs)} shipment legs")
        print(f"Created {total_sensor_logs} sensor logs")
        print(f"Created {len(all_checkpoints)} custody checkpoints")

        print("\nLogin credentials:")
        print("Factory Manager: factory@trustseal.io / pass123")
        print("Warehouse Manager: warehouse@trustseal.io / pass123")
        print("Customer: customer@trustseal.io / pass123")
        print("Administrator: admin@trustseal.io / pass123")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
