"""Small helpers to open the sandbox database. Every tool goes through `connect()`."""

import sqlite3
from pathlib import Path

from agent.config import SANDBOX_DB

SANDBOX_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = SANDBOX_DIR / "schema.sql"
FIXTURES_DIR = SANDBOX_DIR / "fixtures"


def db_path(path: str | Path | None = None) -> Path:
    return Path(path or SANDBOX_DB)


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
