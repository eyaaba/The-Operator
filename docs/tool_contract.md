# Tool contract (frozen 8 Nov 2026)

Source of truth: `agent/schemas.py`. Locked by `tests/test_contract.py`.
Change nothing here without telling the whole team.

| Tool | Type | Arguments | Human checkpoint | Idempotent how |
|---|---|---|---|---|
| `list_emails` | read | `folder` (inbox/archive), `unread_only` (bool), `limit` (1–50) | no | read-only |
| `read_email` | read | `email_id` (em_NNN) | no | read-only (marks as read) |
| `apply_label` | write | `email_id`, `label` (urgent/work/personal/newsletter/spam/needs_reply) | approve / reject | PK (email_id, label) |
| `archive_email` | write | `email_id` | approve / reject | already archived → no-op |
| `draft_reply` | write | `email_id`, `body` (1–2000 chars) | approve / edit / reject | key = hash(tool+args) |
| `send_reply` | write | `draft_id` (dr_NNN) — **no recipient field** | approve / edit / reject | `sent.draft_id` UNIQUE |
| `finish` | control | `summary` | no | ends the run |

## Result format (every tool)

```json
{"ok": true,  "message": "Archived em_003.", "data": {"email_id": "em_003"}, "idempotent_replay": false}
{"ok": false, "error_code": "NOT_FOUND", "message": "No email em_999.", "hint": "Call list_emails to see valid ids."}
```

Error codes: `NOT_FOUND`, `INVALID_ARGUMENT`, `TOOL_UNAVAILABLE`, `TIMEOUT`,
`EMPTY_RESULT`, `NOT_ALLOWED`, `REJECTED_BY_HUMAN`, `BUDGET_EXCEEDED`.

## Limits (agent/config.py)

| Limit | Value |
|---|---|
| Max model calls per run | 15 |
| Max tool calls per run | 25 |
| Max writes per run | 10 |
| Same call repeated | stop after 2 |
| Budget per run | $0.05 |
| Tool retries (transient errors only) | 2 |
