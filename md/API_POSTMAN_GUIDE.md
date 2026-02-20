# TrustSeal API Endpoints for Postman

## Base URLs
- HTTP: `http://localhost:8000`
- API prefix: `http://localhost:8000/api/v1`
- WebSocket: `ws://localhost:8000/api/v1/ws`

## Auth Setup in Postman
1. Call `POST http://localhost:8000/api/v1/auth/login`.
2. Copy `access_token` from response.
3. For protected endpoints, add header:
   - `Authorization: Bearer <access_token>`

## Enum Values
- `UserRole`: `factory`, `port`, `warehouse`, `customer`, `admin`
- `DeviceStatus`: `active`, `inactive`, `maintenance`
- `ShipmentStatus`: `created`, `in_transit`, `docking`, `completed`, `compromised`
- `LegStatus`: `pending`, `in_progress`, `settled`

## Common Schemas

### User
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "customer",
  "created_at": "2026-02-20T18:30:00Z",
  "is_active": true,
  "is_verified": false
}
```

### Token
```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "role": "admin",
  "user_id": "uuid-string"
}
```

### Device
```json
{
  "id": "uuid-string",
  "device_uid": "TS-DEV-0001",
  "model": "Tracker X1",
  "firmware_version": "1.0.0",
  "battery_capacity_mAh": 5000,
  "status": "active",
  "created_at": "2026-02-20T18:30:00Z"
}
```

### Shipment
```json
{
  "id": "uuid-string",
  "shipment_code": "SHIP-1001",
  "description": "Cold-chain medicine",
  "origin": "Mumbai",
  "destination": "Berlin",
  "device_id": "uuid-string",
  "status": "created",
  "created_at": "2026-02-20T18:30:00Z"
}
```

### SensorLog
```json
{
  "id": "uuid-string",
  "shipment_id": "uuid-string",
  "temperature": 5.7,
  "humidity": 52.3,
  "shock": 0.2,
  "light_exposure": false,
  "tilt_angle": 2.1,
  "hash_value": "0xabc123",
  "recorded_at": "2026-02-20T18:40:00Z"
}
```

### ShipmentLeg
```json
{
  "id": "uuid-string",
  "shipment_id": "uuid-string",
  "leg_number": 1,
  "from_location": "Mumbai Port",
  "to_location": "Hamburg Port",
  "status": "pending",
  "started_at": null,
  "completed_at": null
}
```

### CustodyCheckpoint
```json
{
  "id": "uuid-string",
  "shipment_id": "uuid-string",
  "leg_id": "uuid-string",
  "verified_by": "uuid-string",
  "biometric_verified": true,
  "blockchain_tx_hash": "0xtxhash",
  "merkle_root_hash": "0xmerkle",
  "timestamp": "2026-02-20T18:50:00Z"
}
```

### Chat
Request:
```json
{
  "message": "How many active shipments are currently at risk?"
}
```
Response:
```json
{
  "answer": "There are 2 shipments currently at risk.",
  "sources": ["shipments", "sensor_logs"],
  "confidence": "high"
}
```

---

## Public Endpoints

### GET `http://localhost:8000/`
- Auth: No
- Body: None
- Returns:
```json
{
  "message": "Welcome to TrustSeal IoT API"
}
```

### GET `http://localhost:8000/health`
- Auth: No
- Body: None
- Returns:
```json
{
  "status": "ok"
}
```

---

## Auth Endpoints (`/api/v1/auth`)

### POST `http://localhost:8000/api/v1/auth/register`
- Auth: No
- Content-Type: `application/json`
- Request body schema:
```json
{
  "email": "string(email)",
  "name": "string",
  "role": "factory|port|warehouse|customer|admin",
  "password": "string"
}
```
- Example request body:
```json
{
  "email": "admin@trustseal.io",
  "name": "System Admin",
  "role": "admin",
  "password": "pass123"
}
```
- Success response (201):
```json
{
  "user": {
    "id": "uuid-string",
    "email": "admin@trustseal.io",
    "name": "System Admin",
    "role": "admin",
    "created_at": "2026-02-20T18:30:00Z",
    "is_active": true,
    "is_verified": false
  },
  "access_token": "jwt-token",
  "token_type": "bearer",
  "verification_token": "plain-verification-token",
  "verification_token_expires_at": "2026-02-20T19:30:00Z"
}
```

### POST `http://localhost:8000/api/v1/auth/login`
- Auth: No
- Content-Type: `application/x-www-form-urlencoded`
- Form fields:
  - `username` (email)
  - `password`
- Example form values:
```text
username=admin@trustseal.io
password=pass123
```
- Success response (200):
```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "role": "admin",
  "user_id": "uuid-string"
}
```

### POST `http://localhost:8000/api/v1/auth/verify`
- Auth: No
- Content-Type: `application/json`
- Request body schema:
```json
{
  "email": "string(email)",
  "verification_token": "string"
}
```
- Example request:
```json
{
  "email": "admin@trustseal.io",
  "verification_token": "plain-verification-token"
}
```
- Success response:
```json
{
  "message": "User verified successfully",
  "verified": true
}
```

### GET `http://localhost:8000/api/v1/auth/me`
- Auth: Yes (`Bearer token`)
- Body: None
- Success response: `User` schema

---

## Device Endpoints (`/api/v1/devices`)

### GET `http://localhost:8000/api/v1/devices/`
- Auth: Yes (active user)
- Query params:
  - `skip` (int, default `0`)
  - `limit` (int, default `100`, max `1000`)
  - `status` (`active|inactive|maintenance`, optional)
- Example:
  - `http://localhost:8000/api/v1/devices/?skip=0&limit=50&status=active`
- Success response:
```json
[
  {
    "id": "uuid-string",
    "device_uid": "TS-DEV-0001",
    "model": "Tracker X1",
    "firmware_version": "1.0.0",
    "battery_capacity_mAh": 5000,
    "status": "active",
    "created_at": "2026-02-20T18:30:00Z"
  }
]
```

### POST `http://localhost:8000/api/v1/devices/`
- Auth: Yes (roles: `admin`, `factory`)
- Content-Type: `application/json`
- Request body schema:
```json
{
  "device_uid": "string",
  "model": "string",
  "firmware_version": "string",
  "battery_capacity_mAh": 0,
  "status": "active|inactive|maintenance"
}
```
- Example request:
```json
{
  "device_uid": "TS-DEV-0009",
  "model": "Tracker X2",
  "firmware_version": "2.1.0",
  "battery_capacity_mAh": 6200,
  "status": "active"
}
```
- Success response: `Device` schema

### GET `http://localhost:8000/api/v1/devices/{device_id}`
- Auth: Yes (active user)
- Path param: `device_id` (UUID)
- Success response: `Device` schema

### PUT `http://localhost:8000/api/v1/devices/{device_id}`
- Auth: Yes (roles: `admin`, `factory`)
- Path param: `device_id` (UUID)
- Content-Type: `application/json`
- Request body schema (all optional):
```json
{
  "model": "string",
  "firmware_version": "string",
  "battery_capacity_mAh": 0,
  "status": "active|inactive|maintenance"
}
```
- Example request:
```json
{
  "firmware_version": "2.2.0",
  "status": "maintenance"
}
```
- Success response: `Device` schema

### DELETE `http://localhost:8000/api/v1/devices/{device_id}`
- Auth: Yes (roles: `admin`, `factory`)
- Path param: `device_id` (UUID)
- Success response:
```json
{
  "message": "Device deleted successfully"
}
```

---

## Shipment Endpoints (`/api/v1/shipments`)

### GET `http://localhost:8000/api/v1/shipments/`
- Auth: Yes (active user)
- Query params:
  - `skip` (int, default `0`)
  - `limit` (int, default `100`, max `1000`)
  - `status` (`created|in_transit|docking|completed|compromised`, optional)
  - `device_id` (UUID, optional)
- Example:
  - `http://localhost:8000/api/v1/shipments/?status=in_transit&device_id=<device_uuid>`
- Success response: list of `Shipment`

### POST `http://localhost:8000/api/v1/shipments/`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Content-Type: `application/json`
- Request body schema:
```json
{
  "shipment_code": "string",
  "description": "string|null",
  "origin": "string",
  "destination": "string",
  "device_id": "uuid-string"
}
```
- Example request:
```json
{
  "shipment_code": "SHIP-1009",
  "description": "Vaccines container",
  "origin": "Delhi",
  "destination": "Singapore",
  "device_id": "11111111-2222-3333-4444-555555555555"
}
```
- Success response: `Shipment` schema

### GET `http://localhost:8000/api/v1/shipments/{shipment_id}`
- Auth: Yes (active user)
- Path param: `shipment_id` (UUID)
- Success response (`ShipmentWithDetails`) example:
```json
{
  "id": "uuid-string",
  "shipment_code": "SHIP-1001",
  "description": "Cold-chain medicine",
  "origin": "Mumbai",
  "destination": "Berlin",
  "device_id": "uuid-string",
  "status": "in_transit",
  "created_at": "2026-02-20T18:30:00Z",
  "device": {
    "id": "uuid-string",
    "device_uid": "TS-DEV-0001",
    "model": "Tracker X1",
    "firmware_version": "1.0.0",
    "battery_capacity_mAh": 5000,
    "status": "active",
    "created_at": "2026-02-20T18:00:00Z"
  },
  "legs": [],
  "sensor_logs": [],
  "custody_checkpoints": []
}
```

### PUT `http://localhost:8000/api/v1/shipments/{shipment_id}`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `shipment_id` (UUID)
- Content-Type: `application/json`
- Request body schema (all optional):
```json
{
  "description": "string",
  "origin": "string",
  "destination": "string",
  "status": "created|in_transit|docking|completed|compromised",
  "device_id": "uuid-string"
}
```
- Example request:
```json
{
  "status": "in_transit",
  "destination": "Rotterdam"
}
```
- Success response: `Shipment` schema

### POST `http://localhost:8000/api/v1/shipments/{shipment_id}/logs`
- Auth: Yes (active user)
- Path param: `shipment_id` (UUID)
- Content-Type: `application/json`
- Request body schema: array of `SensorLogCreate`
```json
[
  {
    "shipment_id": "uuid-string",
    "temperature": 0,
    "humidity": 0,
    "shock": 0,
    "light_exposure": false,
    "tilt_angle": 0,
    "hash_value": "string"
  }
]
```
- Example request:
```json
[
  {
    "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "temperature": 4.8,
    "humidity": 54.1,
    "shock": 0.1,
    "light_exposure": false,
    "tilt_angle": 1.3,
    "hash_value": "0xloghash001"
  }
]
```
- Success response: array of `SensorLog`

### GET `http://localhost:8000/api/v1/shipments/{shipment_id}/logs`
- Auth: Yes (active user)
- Path param: `shipment_id` (UUID)
- Query params: `skip`, `limit`
- Success response: array of `SensorLog`

### POST `http://localhost:8000/api/v1/shipments/{shipment_id}/settle`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `shipment_id` (UUID)
- Body: None
- Success response:
```json
{
  "message": "Shipment settled successfully"
}
```

---

## Sensor Log Endpoints (`/api/v1/sensor-logs`)

### GET `http://localhost:8000/api/v1/sensor-logs/`
- Auth: Yes (active user)
- Query params:
  - `skip` (int)
  - `limit` (int)
  - `shipment_id` (UUID, optional)
- Success response: array of `SensorLog`

### POST `http://localhost:8000/api/v1/sensor-logs/`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Content-Type: `application/json`
- Request body schema:
```json
{
  "shipment_id": "uuid-string",
  "temperature": 0,
  "humidity": 0,
  "shock": 0,
  "light_exposure": false,
  "tilt_angle": 0,
  "hash_value": "string"
}
```
- Example request:
```json
{
  "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "temperature": 5.1,
  "humidity": 49.9,
  "shock": 0.3,
  "light_exposure": false,
  "tilt_angle": 2.5,
  "hash_value": "0xloghash002"
}
```
- Success response: `SensorLog` schema

### GET `http://localhost:8000/api/v1/sensor-logs/{log_id}`
- Auth: Yes (active user)
- Path param: `log_id` (UUID)
- Success response: `SensorLog` schema

### DELETE `http://localhost:8000/api/v1/sensor-logs/{log_id}`
- Auth: Yes (role: `admin`)
- Path param: `log_id` (UUID)
- Success response:
```json
{
  "message": "Sensor log deleted successfully"
}
```

---

## Shipment Leg Endpoints (`/api/v1/legs`)

### GET `http://localhost:8000/api/v1/legs/`
- Auth: Yes (active user)
- Query params:
  - `skip` (int)
  - `limit` (int)
  - `shipment_id` (UUID, optional)
- Success response: array of `ShipmentLeg`

### POST `http://localhost:8000/api/v1/legs/`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Content-Type: `application/json`
- Request body schema:
```json
{
  "shipment_id": "uuid-string",
  "leg_number": 1,
  "from_location": "string",
  "to_location": "string"
}
```
- Example request:
```json
{
  "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "leg_number": 1,
  "from_location": "Mumbai Port",
  "to_location": "Hamburg Port"
}
```
- Success response: `ShipmentLeg` schema

### GET `http://localhost:8000/api/v1/legs/{leg_id}`
- Auth: Yes (active user)
- Path param: `leg_id` (UUID)
- Success response: `ShipmentLeg` schema

### PUT `http://localhost:8000/api/v1/legs/{leg_id}`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `leg_id` (UUID)
- Content-Type: `application/json`
- Request body schema (all optional):
```json
{
  "from_location": "string",
  "to_location": "string",
  "status": "pending|in_progress|settled",
  "started_at": "datetime",
  "completed_at": "datetime"
}
```
- Example request:
```json
{
  "status": "in_progress",
  "started_at": "2026-02-20T19:00:00Z"
}
```
- Success response: `ShipmentLeg` schema

### POST `http://localhost:8000/api/v1/legs/{leg_id}/start`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `leg_id` (UUID)
- Body: None
- Success response:
```json
{
  "message": "Shipment leg started successfully"
}
```

### POST `http://localhost:8000/api/v1/legs/{leg_id}/complete`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `leg_id` (UUID)
- Body: None
- Success response:
```json
{
  "message": "Shipment leg completed successfully"
}
```

### DELETE `http://localhost:8000/api/v1/legs/{leg_id}`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `leg_id` (UUID)
- Success response:
```json
{
  "message": "Shipment leg deleted successfully"
}
```

---

## Custody Endpoints (`/api/v1/custody`)

### GET `http://localhost:8000/api/v1/custody/`
- Auth: Yes (active user)
- Query params:
  - `skip` (int)
  - `limit` (int)
  - `shipment_id` (UUID, optional)
- Success response: array of `CustodyCheckpoint`

### POST `http://localhost:8000/api/v1/custody/`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Content-Type: `application/json`
- Request body schema:
```json
{
  "shipment_id": "uuid-string",
  "leg_id": "uuid-string|null",
  "verified_by": "uuid-string|null",
  "biometric_verified": false,
  "blockchain_tx_hash": "string|null",
  "merkle_root_hash": "string|null"
}
```
- Example request:
```json
{
  "shipment_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "leg_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
  "verified_by": "cccccccc-dddd-eeee-ffff-111111111111",
  "biometric_verified": true,
  "blockchain_tx_hash": "0xtx123",
  "merkle_root_hash": "0xmerkle123"
}
```
- Success response: `CustodyCheckpoint` schema

### GET `http://localhost:8000/api/v1/custody/{checkpoint_id}`
- Auth: Yes (active user)
- Path param: `checkpoint_id` (UUID)
- Success response: `CustodyCheckpoint` schema

### PUT `http://localhost:8000/api/v1/custody/{checkpoint_id}`
- Auth: Yes (roles: `admin`, `factory`, `port`, `warehouse`)
- Path param: `checkpoint_id` (UUID)
- Content-Type: `application/json`
- Request body schema (all optional):
```json
{
  "leg_id": "uuid-string",
  "verified_by": "uuid-string",
  "biometric_verified": true,
  "blockchain_tx_hash": "string",
  "merkle_root_hash": "string"
}
```
- Example request:
```json
{
  "biometric_verified": true,
  "blockchain_tx_hash": "0xtx999"
}
```
- Success response: `CustodyCheckpoint` schema

### DELETE `http://localhost:8000/api/v1/custody/{checkpoint_id}`
- Auth: Yes (role: `admin`)
- Path param: `checkpoint_id` (UUID)
- Success response:
```json
{
  "message": "Custody checkpoint deleted successfully"
}
```

---

## Chat Endpoint

### POST `http://localhost:8000/api/v1/chat`
- Auth: Yes (role: `admin`)
- Content-Type: `application/json`
- Request body schema:
```json
{
  "message": "string (1 to 4000 chars)"
}
```
- Example request:
```json
{
  "message": "List shipments that are compromised."
}
```
- Success response schema:
```json
{
  "answer": "string",
  "sources": ["string"],
  "confidence": "high|medium|low"
}
```

---

## Debug Endpoint

### GET `http://localhost:8000/api/v1/debug/whoami`
- Auth: Yes (`Bearer token`)
- Body: None
- Success response: `User` schema

---

## WebSocket Endpoint

### WS `ws://localhost:8000/api/v1/ws/shipments/{shipment_id}`
- Auth:
  - Optional by config (`WS_REQUIRE_AUTH`)
  - If enabled, pass JWT as query `?token=<jwt>` or header `Authorization: Bearer <jwt>`
- On connect, server sends:
```json
{
  "event": "ws.connected",
  "shipment_id": "uuid-string",
  "authenticated": true
}
```
- Ping/Pong test:
  - Send text: `ping`
  - Receive:
```json
{
  "event": "ws.pong",
  "shipment_id": "uuid-string"
}
```

---

## Standard Error Examples

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "Insufficient permissions for this operation"
}
```

### 404 Not Found
```json
{
  "detail": "Shipment not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```
