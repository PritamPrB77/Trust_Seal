from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings

# Create FastAPI app
app = FastAPI(title=settings.PROJECT_NAME)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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
from .routers import auth, devices, shipments, sensor_logs, custody, legs

app.include_router(auth.router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(devices.router, prefix=settings.API_V1_STR + "/devices", tags=["devices"])
app.include_router(shipments.router, prefix=settings.API_V1_STR + "/shipments", tags=["shipments"])
app.include_router(sensor_logs.router, prefix=settings.API_V1_STR + "/sensor-logs", tags=["sensor-logs"])
app.include_router(custody.router, prefix=settings.API_V1_STR + "/custody", tags=["custody"])
app.include_router(legs.router, prefix=settings.API_V1_STR + "/legs", tags=["legs"])
from .routers import debug
app.include_router(debug.router, prefix=settings.API_V1_STR + "/debug", tags=["debug"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
