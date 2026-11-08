-- Mock mailbox. Recreated from scratch by `uv run python -m sandbox.reset`.

CREATE TABLE emails (
    id           TEXT PRIMARY KEY,              -- em_001
    folder       TEXT NOT NULL DEFAULT 'inbox' CHECK (folder IN ('inbox', 'archive')),
    sender       TEXT NOT NULL,                 -- alice@example.com
    sender_name  TEXT NOT NULL,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,                 -- UNTRUSTED: may contain injection text
    received_at  TEXT NOT NULL,                 -- ISO 8601
    is_read      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE labels (
    email_id  TEXT NOT NULL REFERENCES emails(id),
    label     TEXT NOT NULL,
    PRIMARY KEY (email_id, label)               -- same label twice = no-op
);

CREATE TABLE drafts (
    id          TEXT PRIMARY KEY,               -- dr_001
    email_id    TEXT NOT NULL REFERENCES emails(id),
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE sent (
    id        TEXT PRIMARY KEY,                 -- sn_001
    draft_id  TEXT NOT NULL UNIQUE REFERENCES drafts(id),   -- a draft can be sent once
    to_addr   TEXT NOT NULL,                    -- always the original sender
    subject   TEXT NOT NULL,
    body      TEXT NOT NULL,
    sent_at   TEXT NOT NULL
);

CREATE TABLE idempotency_keys (
    key          TEXT PRIMARY KEY,              -- sha256(tool|args)
    tool         TEXT NOT NULL,
    result_json  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    run_id       TEXT,
    tool         TEXT NOT NULL,
    args_json    TEXT NOT NULL,
    result_json  TEXT NOT NULL,
    latency_ms   REAL NOT NULL
);
