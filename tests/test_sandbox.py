"""The sandbox must reset to exactly the same state every time."""

from agent.idempotency import idempotency_key
from sandbox.db import connect
from sandbox.reset import reset


def _snapshot(path):
    conn = connect(path)
    try:
        rows = conn.execute("SELECT id, folder, is_read FROM emails ORDER BY id").fetchall()
        return [tuple(r) for r in rows]
    finally:
        conn.close()


def test_reset_loads_default_inbox(tmp_path):
    db = tmp_path / "mailbox.db"
    assert reset(path=db) == 8
    snap = _snapshot(db)
    assert len(snap) == 8
    assert all(folder == "inbox" and is_read == 0 for _, folder, is_read in snap)


def test_reset_is_repeatable_after_changes(tmp_path):
    db = tmp_path / "mailbox.db"
    reset(path=db)
    first = _snapshot(db)

    conn = connect(db)
    conn.execute("UPDATE emails SET folder='archive', is_read=1")
    conn.commit()
    conn.close()

    reset(path=db)
    assert _snapshot(db) == first


def test_idempotency_key_ignores_argument_order():
    a = idempotency_key("apply_label", {"email_id": "em_001", "label": "urgent"})
    b = idempotency_key("apply_label", {"label": "urgent", "email_id": "em_001"})
    c = idempotency_key("apply_label", {"email_id": "em_001", "label": "work"})
    assert a == b
    assert a != c
