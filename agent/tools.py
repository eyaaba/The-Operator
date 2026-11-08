"""
The 7 tools the agent can call (Task 1 - owner: Khalil).

Each tool:
  1. validates its input with the schema from agent/schemas.py
  2. talks only to the sandbox SQLite DB (never a real mailbox)
  3. returns ToolResult (never raises a stack trace to the model)
  4. is logged (tool, args, result, latency) by the logger in Task 1.6
Writes also check the idempotency key first (agent/idempotency.py).

Subtasks (see Bloomi):
  list_emails, read_email ............. 1.3
  apply_label, archive_email,
  draft_reply, send_reply ............. 1.4
  finish .............................. 2.1 (it is the done-rule)
"""

from agent.schemas import ToolResult  # noqa: F401  (used by every tool once implemented)


def list_emails(folder: str = "inbox", unread_only: bool = False, limit: int = 10):
    raise NotImplementedError("Task 1.3")


def read_email(email_id: str):
    raise NotImplementedError("Task 1.3")


def apply_label(email_id: str, label: str):
    raise NotImplementedError("Task 1.4")


def archive_email(email_id: str):
    raise NotImplementedError("Task 1.4")


def draft_reply(email_id: str, body: str):
    raise NotImplementedError("Task 1.4")


def send_reply(draft_id: str):
    raise NotImplementedError("Task 1.4")


def finish(summary: str):
    raise NotImplementedError("Task 2.1")
