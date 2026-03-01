from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .services.realtime import shipment_event_dispatcher

# Create FastAPI app
app = FastAPI(title=settings.PROJECT_NAME)


@app.on_event("startup")
def ensure_local_sqlite_schema() -> None:
    # For local dev fallback, create schema automatically when using SQLite.
    if settings.DATABASE_URL.startswith("sqlite"):
        from . import models  # noqa: F401
        from .database import Base, engine

        Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def start_realtime_dispatcher() -> None:
    shipment_event_dispatcher.start()


@app.on_event("shutdown")
async def stop_realtime_dispatcher() -> None:
    await shipment_event_dispatcher.stop()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to TrustSeal IoT API"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Import and include routers
from .routers import auth, devices, shipments, sensor_logs, custody, legs, ws, chat

app.include_router(auth.router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(devices.router, prefix=settings.API_V1_STR + "/devices", tags=["devices"])
app.include_router(shipments.router, prefix=settings.API_V1_STR + "/shipments", tags=["shipments"])
app.include_router(sensor_logs.router, prefix=settings.API_V1_STR + "/sensor-logs", tags=["sensor-logs"])
app.include_router(custody.router, prefix=settings.API_V1_STR + "/custody", tags=["custody"])
app.include_router(legs.router, prefix=settings.API_V1_STR + "/legs", tags=["legs"])
app.include_router(ws.router, prefix=settings.API_V1_STR + "/ws", tags=["ws"])
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["chat"])
from .routers import debug
app.include_router(debug.router, prefix=settings.API_V1_STR + "/debug", tags=["debug"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
