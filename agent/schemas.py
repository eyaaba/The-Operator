"""
THE TOOL CONTRACT (frozen on day 1).

Every tool's input schema and the single result format live here.
Task 1 (tools), Task 2 (agent loop) and Task 3 (eval) all import from this
file, so they can be built in parallel without waiting on each other.

Rule: do NOT change a name or field here without telling the whole team.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

EMAIL_ID_PATTERN = r"^em_\d{3,}$"   # e.g. em_001
DRAFT_ID_PATTERN = r"^dr_\d{3,}$"   # e.g. dr_001

Label = Literal["urgent", "work", "personal", "newsletter", "spam", "needs_reply"]
Folder = Literal["inbox", "archive"]


class StrictInput(BaseModel):
    """Base for every tool input: unknown fields are rejected, strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

class ListEmailsInput(StrictInput):
    """List emails in a folder, newest first. Returns ids, senders and subjects only (no bodies)."""

    folder: Folder = Field("inbox", description="Which folder to list.")
    unread_only: bool = Field(False, description="If true, only unread emails.")
    limit: int = Field(10, ge=1, le=50, description="Max number of emails to return (1-50).")


class ReadEmailInput(StrictInput):
    """Read one email in full (sender, subject, body). Marks it as read."""

    email_id: str = Field(..., pattern=EMAIL_ID_PATTERN, description="Email id, e.g. em_001.")


# ---------------------------------------------------------------------------
# Write tools (every one of these goes through the human checkpoint)
# ---------------------------------------------------------------------------

class ApplyLabelInput(StrictInput):
    """Add one label to an email. Applying the same label twice changes nothing."""

    email_id: str = Field(..., pattern=EMAIL_ID_PATTERN)
    label: Label = Field(..., description="One of the allowed labels.")


class ArchiveEmailInput(StrictInput):
    """Move an email from inbox to archive. Archiving an archived email changes nothing."""

    email_id: str = Field(..., pattern=EMAIL_ID_PATTERN)


class DraftReplyInput(StrictInput):
    """Create a draft reply to an email. Nothing is sent. Same email + same body = same draft."""

    email_id: str = Field(..., pattern=EMAIL_ID_PATTERN)
    body: str = Field(..., min_length=1, max_length=2000, description="Plain-text reply body.")


class SendReplyInput(StrictInput):
    """
    Send an existing draft. There is deliberately NO recipient field:
    the reply always goes to the original sender of the email the draft answers.
    This is our main defence against injected "send this to attacker@..." text.
    """

    draft_id: str = Field(..., pattern=DRAFT_ID_PATTERN, description="Draft id, e.g. dr_001.")


# ---------------------------------------------------------------------------
# Done-rule tool
# ---------------------------------------------------------------------------

class FinishInput(StrictInput):
    """Call this exactly once when the task is complete (or cannot be completed). Ends the run."""

    summary: str = Field(..., min_length=1, max_length=1000, description="What was done and what was not.")


# ---------------------------------------------------------------------------
# The one result format every tool returns
# ---------------------------------------------------------------------------

class ErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"                  # email/draft id does not exist
    INVALID_ARGUMENT = "INVALID_ARGUMENT"    # schema validation failed
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"    # sandbox "down" (fault injection)
    TIMEOUT = "TIMEOUT"                      # tool took too long (fault injection)
    EMPTY_RESULT = "EMPTY_RESULT"            # valid call, nothing found
    NOT_ALLOWED = "NOT_ALLOWED"              # policy forbids it (e.g. write cap reached)
    REJECTED_BY_HUMAN = "REJECTED_BY_HUMAN"  # human said no at the checkpoint
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"      # step / token / cost limit hit


class ToolResult(BaseModel):
    """
    Success:  {"ok": true,  "data": {...}, "message": "Archived em_003."}
    Failure:  {"ok": false, "error_code": "NOT_FOUND", "message": "...", "hint": "Call list_emails first."}

    Never a stack trace. `hint` tells the model what to do next.
    `idempotent_replay` is true when a write was already done and nothing changed.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str
    data: dict[str, Any] | None = None
    error_code: ErrorCode | None = None
    hint: str | None = None
    idempotent_replay: bool = False

    @classmethod
    def success(cls, message: str, data: dict[str, Any] | None = None, replay: bool = False) -> "ToolResult":
        return cls(ok=True, message=message, data=data, idempotent_replay=replay)

    @classmethod
    def failure(cls, code: ErrorCode, message: str, hint: str | None = None) -> "ToolResult":
        return cls(ok=False, error_code=code, message=message, hint=hint)


# ---------------------------------------------------------------------------
# Registry: tool name -> input schema (used by the agent, the eval and the tests)
# ---------------------------------------------------------------------------

READ_TOOLS: dict[str, type[StrictInput]] = {
    "list_emails": ListEmailsInput,
    "read_email": ReadEmailInput,
}

WRITE_TOOLS: dict[str, type[StrictInput]] = {
    "apply_label": ApplyLabelInput,
    "archive_email": ArchiveEmailInput,
    "draft_reply": DraftReplyInput,
    "send_reply": SendReplyInput,
}

CONTROL_TOOLS: dict[str, type[StrictInput]] = {
    "finish": FinishInput,
}

ALL_TOOLS: dict[str, type[StrictInput]] = {**READ_TOOLS, **WRITE_TOOLS, **CONTROL_TOOLS}
