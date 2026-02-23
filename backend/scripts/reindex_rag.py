"""
Build/refresh the RAG vector index from current database records.

Usage:
    python scripts/reindex_rag.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import traceback

from dotenv import load_dotenv
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from app.database import SessionLocal  # noqa: E402
from app.services.chat_service import chat_service  # noqa: E402


def main() -> None:
    print("Starting RAG reindex...", flush=True)
    print(f"Using env file: {ROOT_DIR / '.env'}", flush=True)
    db = SessionLocal()
    try:
        print("Connected to DB session. Refreshing index...", flush=True)
        chat_service.refresh_index(db)
        count = db.execute(text("SELECT COUNT(*) FROM rag_documents")).scalar()
        print(f"RAG index refreshed. rag_documents={count}", flush=True)
    except Exception:
        print("RAG reindex failed with exception:", flush=True)
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
