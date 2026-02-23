from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from .core.config import settings

database_url = settings.DATABASE_URL
engine_kwargs = {}
connect_args = {}

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # Keep DB connections healthy and fail quickly when remote DB is unreachable.
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT_SECONDS
    engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE_SECONDS

    try:
        parsed = make_url(database_url)
        has_connect_timeout = "connect_timeout" in (parsed.query or {})
    except Exception:
        has_connect_timeout = False

    if not has_connect_timeout:
        connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT_SECONDS

if connect_args:
    engine_kwargs["connect_args"] = connect_args

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
