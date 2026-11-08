"""
Reset the sandbox mailbox to a known state.

    uv run python -m sandbox.reset                      # default inbox
    uv run python -m sandbox.reset --fixture my_inbox   # sandbox/fixtures/my_inbox.json

Deletes the SQLite file, recreates the tables from schema.sql and loads the
fixture. Running it twice gives exactly the same mailbox.
"""

import argparse
import json
from pathlib import Path

from sandbox.db import FIXTURES_DIR, SCHEMA_FILE, connect, db_path


def reset(fixture: str = "default_inbox", path: str | Path | None = None) -> int:
    target = db_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    data = json.loads((FIXTURES_DIR / f"{fixture}.json").read_text(encoding="utf-8"))

    conn = connect(target)
    try:
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        conn.executemany(
            """INSERT INTO emails (id, folder, sender, sender_name, subject, body, received_at, is_read)
               VALUES (:id, :folder, :sender, :sender_name, :subject, :body, :received_at, :is_read)""",
            [{"folder": "inbox", "is_read": 0, **e} for e in data["emails"]],
        )
        conn.commit()
    finally:
        conn.close()  # close explicitly so Windows can delete the file on the next reset
    return len(data["emails"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the sandbox mailbox.")
    parser.add_argument("--fixture", default="default_inbox", help="Fixture name in sandbox/fixtures/")
    args = parser.parse_args()
    count = reset(args.fixture)
    print(f"Sandbox reset: {count} emails loaded from '{args.fixture}' into {db_path()}")


if __name__ == "__main__":
    main()
