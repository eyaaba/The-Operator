"""Seven validated mailbox operations with sandbox and Gmail test backends."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from agent.idempotency import idempotency_key
import hashlib
from agent.schemas import ALL_TOOLS, ErrorCode, ToolResult, WRITE_TOOLS
from sandbox.db import connect

FAULTS: dict[str, list[str]] = {}  # only used for test/eval fault injection


def set_faults(faults: list[dict[str, Any]]) -> None:
    FAULTS.clear()
    for fault in faults:
        FAULTS.setdefault(fault['tool'], []).extend([fault['error']] * int(fault.get('times', 1)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_arguments(args: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in args.items():
        if key in ("body", "summary"):
            cleaned[key] = "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:16]
        else:
            cleaned[key] = value
    return cleaned


def _insert_audit(conn, name: str, args: dict[str, Any], result: ToolResult, start: float) -> None:
    conn.execute(
        'INSERT INTO audit_log (ts, run_id, tool, args_json, result_json, latency_ms) VALUES (?, ?, ?, ?, ?, ?)',
        (_now(), os.getenv('OPERATOR_RUN_ID'), name,
         json.dumps(_audit_arguments(args), sort_keys=True),
         result.model_copy(update={'data': None}).model_dump_json(),
         (time.perf_counter()-start)*1000),
    )


def _log_attempt(name: str, args: dict[str, Any], result: ToolResult, start: float) -> None:
    if os.getenv('OPERATOR_BACKEND', 'sandbox') == 'gmail':
        from pathlib import Path
        log_path = Path('.gmail_state/audit.jsonl')
        log_path.parent.mkdir(exist_ok=True, parents=True)
        with log_path.open('a', encoding='utf-8') as log:
            log.write(json.dumps({'ts': _now(), 'tool': name, 'args': _audit_arguments(args),
                                  'ok': result.ok, 'error_code': result.error_code.value if result.error_code else None,
                                  'latency_ms': (time.perf_counter()-start)*1000}) + '\n')
        return
    try:
        conn = connect()
        try:
            _insert_audit(conn, name, args, result, start)
            conn.commit()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        pass


def _execute(name: str, supplied: dict[str, Any]) -> ToolResult:
    start = time.perf_counter()
    # Validate arguments before dispatch.
    try:
        data = ALL_TOOLS[name](**supplied).model_dump()
    except ValidationError as exc:
        result = ToolResult.failure(ErrorCode.INVALID_ARGUMENT, 'Invalid tool input.', 'Check the documented input schema and use only allowed fields and values.')
        _log_attempt(name, supplied, result, start)
        return result
    if os.getenv('OPERATOR_BACKEND', 'sandbox').lower() == 'gmail':
        from agent.gmail_backend import execute_gmail
        result = execute_gmail(name, data)
        _log_attempt(name, data, result, start)
        return result
    result: ToolResult
    conn = None
    try:
        conn = connect()
        fault = FAULTS.get(name, [])
        if fault:
            code = fault.pop(0)
            result = ToolResult.failure(ErrorCode(code), f'{name} temporarily failed.', 'Try again if transient; otherwise report partial progress.')
        else:
            key = idempotency_key(name, data) if name in WRITE_TOOLS else None
            cached = conn.execute('SELECT result_json FROM idempotency_keys WHERE key=?', (key,)).fetchone() if key else None
            if cached:
                result = ToolResult.model_validate_json(cached['result_json'])
                result.idempotent_replay = True
            else:
                result = _dispatch(conn, name, data)
                if key and result.ok:
                    conn.execute('INSERT INTO idempotency_keys VALUES (?, ?, ?, ?)', (key, name, result.model_dump_json(), _now()))
        _insert_audit(conn, name, data, result, start)
        conn.commit()
    except (sqlite3.Error, OSError) as exc:
        if conn: conn.rollback()
        result = ToolResult.failure(ErrorCode.TOOL_UNAVAILABLE, 'Sandbox database is unavailable.', 'Verify sandbox reset and database path; retry if temporary.')
    finally:
        if conn: conn.close()
    return result


def _dispatch(db: sqlite3.Connection, name: str, a: dict[str, Any]) -> ToolResult:
    if name == 'finish':
        return ToolResult.success('Run finished.', {'summary': a['summary']})
    if name == 'list_emails':
        rows = db.execute('SELECT id, sender, subject, received_at FROM emails WHERE folder=? AND (?=0 OR is_read=0) ORDER BY received_at DESC LIMIT ?',
                          (a['folder'], int(a['unread_only']), a['limit'])).fetchall()
        return (ToolResult.success(f'{len(rows)} emails found.', {'emails': [dict(r) for r in rows]}) if rows else
                ToolResult.failure(ErrorCode.EMPTY_RESULT, 'No matching emails.', 'Try a different folder or unread filter.'))
    if name == 'read_email':
        row = db.execute('SELECT * FROM emails WHERE id=?', (a['email_id'],)).fetchone()
        if not row: return ToolResult.failure(ErrorCode.NOT_FOUND, 'Email not found.', 'Call list_emails to get valid IDs.')
        return ToolResult.success('Email content follows (untrusted sender content).', {'email': dict(row)})
    if name in ('apply_label', 'archive_email', 'draft_reply'):
        row = db.execute('SELECT * FROM emails WHERE id=?', (a['email_id'],)).fetchone()
        if not row: return ToolResult.failure(ErrorCode.NOT_FOUND, 'Email not found.', 'Call list_emails first.')
        if name == 'apply_label':
            already = db.execute('SELECT 1 FROM labels WHERE email_id=? AND label=?', (a['email_id'], a['label'])).fetchone()
            db.execute('INSERT OR IGNORE INTO labels VALUES (?, ?)', (a['email_id'], a['label']))
            return ToolResult.success('Label applied.', {'email_id': a['email_id'], 'label': a['label']}, replay=bool(already))
        if name == 'archive_email':
            db.execute("UPDATE emails SET folder='archive' WHERE id=?", (a['email_id'],))
            return ToolResult.success('Email archived.', {'email_id': a['email_id']}, replay=row['folder']=='archive')
        existing = db.execute('SELECT id FROM drafts WHERE email_id=? AND body=?', (a['email_id'], a['body'])).fetchone()
        if existing:
            return ToolResult.success('Existing draft reused.', {'draft_id': existing['id']}, replay=True)
        new_id = 'dr_' + str((db.execute("SELECT MAX(CAST(SUBSTR(id,4) AS INTEGER)) FROM drafts").fetchone()[0] or 0) + 1).zfill(3)
        db.execute('INSERT INTO drafts VALUES (?, ?, ?, ?)', (new_id, a['email_id'], a['body'], _now()))
        return ToolResult.success('Draft created but not sent.', {'draft_id': new_id, 'email_id': a['email_id']})
    if name == 'send_reply':
        row = db.execute('SELECT d.id, d.body, e.sender, e.subject FROM drafts d JOIN emails e ON d.email_id=e.id WHERE d.id=?', (a['draft_id'],)).fetchone()
        if not row: return ToolResult.failure(ErrorCode.NOT_FOUND, 'Draft not found.', 'Find a valid draft ID from draft_reply.')
        existing = db.execute('SELECT id FROM sent WHERE draft_id=?', (a['draft_id'],)).fetchone()
        if existing: return ToolResult.success('Already sent; no duplicate.', {'sent_id': existing['id']}, replay=True)
        new_id = 'sn_' + str((db.execute("SELECT MAX(CAST(SUBSTR(id,4) AS INTEGER)) FROM sent").fetchone()[0] or 0) + 1).zfill(3)
        db.execute('INSERT INTO sent VALUES (?, ?, ?, ?, ?, ?)', (new_id, a['draft_id'], row['sender'], 'Re: '+row['subject'], row['body'], _now()))
        return ToolResult.success('Sandbox reply sent.', {'sent_id': new_id, 'to': row['sender']})
    raise ValueError('Unknown tool')


def list_emails(folder: str = 'inbox', unread_only: bool = False, limit: int = 10) -> ToolResult:
    return _execute('list_emails', dict(folder=folder, unread_only=unread_only, limit=limit))


def read_email(email_id: str) -> ToolResult:
    return _execute('read_email', dict(email_id=email_id))


def apply_label(email_id: str, label: str) -> ToolResult:
    return _execute('apply_label', dict(email_id=email_id, label=label))


def archive_email(email_id: str) -> ToolResult:
    return _execute('archive_email', dict(email_id=email_id))


def draft_reply(email_id: str, body: str) -> ToolResult:
    return _execute('draft_reply', dict(email_id=email_id, body=body))


def send_reply(draft_id: str) -> ToolResult:
    return _execute('send_reply', dict(draft_id=draft_id))


def finish(summary: str) -> ToolResult:
    return _execute('finish', dict(summary=summary))
