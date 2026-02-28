# TrustSeal IoT

Full-stack supply chain IoT monitoring system.

- Backend: FastAPI + PostgreSQL + SQLAlchemy + JWT
- Frontend: React (Vite) + TypeScript + Tailwind + React Query + Axios + Recharts

## Architecture

- API base path: `/api/v1`
- Auth: JWT Bearer token in `Authorization` header
- Frontend API base URL comes from `VITE_API_BASE_URL`
- CORS origins come from `BACKEND_CORS_ORIGINS`

## Project Structure

```text
TrustSeal/
|- frontend/                # React frontend
|  |- src/
|  |- package.json
|  |- .env.example
|- backend/                 # FastAPI backend
|  |- app/
|  |- alembic/
|  |- requirements.txt
|  |- run.py
|  |- .env.example
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env`, and copy `frontend/.env.example` to `frontend/.env`.

Required for backend:

```env
# Optional: one full URL override (takes precedence over POSTGRES_*):
# DATABASE_URL=sqlite:///./trustseal.db
# DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require

BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=trustseal
POSTGRES_PORT=5432
POSTGRES_SSLMODE=prefer
SECRET_KEY=replace-with-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

If you are using Supabase and your network cannot resolve/connect to `db.<project>.supabase.co` (often IPv6/DNS issues), use Supabase pooler connection string in `DATABASE_URL` (IPv4-friendly) or switch to local SQLite for development.

Required for frontend:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Backend Setup

1. Create virtual environment and install dependencies.
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirement
```
2. Run migrations.
```bash
alembic upgrade head
```
3. Optional: seed data.
```bash
python -m app.seed_data
```
4. Start backend.
```bash
python run.py
```

Backend runs at `http://localhost:8000`.

## Frontend Setup

1. Install dependencies.
```bash
cd frontend
npm install
```
2. Start dev server.
```bash
npm run dev
```
3. Build for production.
```bash
npm run build
```

Frontend default dev URL is `http://localhost:5173`.

Quick frontend tips:

- Copy `frontend/.env.example` to `frontend/.env` to set `VITE_API_BASE_URL`.
- After backend is running at `http://localhost:8000`, start the frontend with `cd frontend` then `npm run dev`.

Admin login example
-------------------

The development seed now creates an administrator account so you can sign in and see all devices and shipments.

- Email: `admin@trustseal.io`
- Password: `pass123`

You can obtain a token via curl and use it for API calls (PowerShell example):

```powershell
# login and capture token
$token = (curl.exe -s -X POST -d "username=admin@trustseal.io" -d "password=pass123" "http://localhost:8000/api/v1/auth/login" | ConvertFrom-Json).access_token

# list devices
curl.exe -H "Authorization: Bearer $token" http://localhost:8000/api/v1/devices/

# list shipments for a device (replace DEVICE_UUID with device.id from previous call)
curl.exe -H "Authorization: Bearer $token" "http://localhost:8000/api/v1/shipments/?device_id=DEVICE_UUID"
```

Browser flow:

- Open the app at `http://localhost:5173` and sign in using the admin credentials.
- After sign-in the frontend stores the token in `localStorage` under key `trustseal_access_token`.
- If you still get `{"detail":"Not authenticated"}` when calling endpoints, copy the token from localStorage and test it with the curl commands above to confirm the backend accepts it.

## API Docs

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Frontend <-> Backend Sync Matrix

Authentication:

- `POST /api/v1/auth/register` (JSON body)
- `POST /api/v1/auth/login` (`application/x-www-form-urlencoded`)
- `GET /api/v1/auth/me` (Bearer token)

Dashboard:

- `GET /api/v1/devices/`
- `GET /api/v1/devices/{device_id}`

Device details:

- `GET /api/v1/shipments/?device_id={device_id}`

Shipment details:

- `GET /api/v1/shipments/{shipment_id}`
- `GET /api/v1/shipments/{shipment_id}/logs`
- `GET /api/v1/legs/?shipment_id={shipment_id}`
- `GET /api/v1/custody/?shipment_id={shipment_id}`

## CORS and Preflight

Backend CORS is configured in `backend/app/main.py` using `CORSMiddleware`:

- `allow_origins`: from `BACKEND_CORS_ORIGINS`
- `allow_methods`: `GET, POST, PUT, DELETE, OPTIONS`
- `allow_headers`: `Authorization, Content-Type, Accept, Origin`
- `allow_credentials`: `False` (JWT header auth, not cookie auth)

Preflight behavior:

- Requests with `Authorization` header trigger browser `OPTIONS` preflight.
- Preflight succeeds only when request origin is in `BACKEND_CORS_ORIGINS`.
- If frontend runs on a different host/port, add it to `BACKEND_CORS_ORIGINS`.

## Auth Flow

1. User registers on `/register`.
2. User logs in on `/login`.
3. Frontend stores `access_token` in `localStorage`.
4. Axios interceptor injects `Authorization: Bearer <token>`.
5. Expired/invalid token causes automatic logout and redirect.

## Common Troubleshooting

`401 Unauthorized`:

- Token expired or invalid.
- Confirm login succeeded and token is stored.

`CORS error` in browser:

- Current frontend origin is missing in `BACKEND_CORS_ORIGINS`.
- Restart backend after changing `.env`.

`AttributeError: module 'bcrypt' has no attribute '__about__'`:

- Caused by incompatible `bcrypt` with `passlib 1.7.4`.
- Use pinned dependency from `backend/requirements.txt` (`bcrypt>=4.0.1,<4.1`).
- Reinstall backend deps and restart server.

No data on device shipments:

- Ensure shipments exist with matching `device_id`.
- Check `GET /api/v1/shipments/?device_id=...` in Swagger.

## Security Notes

- Do not commit real secrets in `.env`.
- Use strong `SECRET_KEY` in production.
- Restrict `BACKEND_CORS_ORIGINS` to trusted domains in production.
