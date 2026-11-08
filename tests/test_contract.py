"""
Contract tests: if anyone changes agent/schemas.py by accident, these fail.
They also prove "the model cannot pass bad arguments" (brief, slide 7).
"""

import pytest
from pydantic import ValidationError

from agent.schemas import (
    ALL_TOOLS,
    WRITE_TOOLS,
    ApplyLabelInput,
    ErrorCode,
    ListEmailsInput,
    ReadEmailInput,
    SendReplyInput,
    ToolResult,
)


def test_tool_names_are_frozen():
    assert set(ALL_TOOLS) == {
        "list_emails", "read_email",
        "apply_label", "archive_email", "draft_reply", "send_reply",
        "finish",
    }


def test_at_least_one_write_tool():
    assert len(WRITE_TOOLS) >= 1


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ReadEmailInput(email_id="em_001", delete_everything=True)


@pytest.mark.parametrize("bad_id", ["1", "em_1", "EM_001", "em_001; DROP TABLE emails", ""])
def test_bad_email_ids_are_rejected(bad_id):
    with pytest.raises(ValidationError):
        ReadEmailInput(email_id=bad_id)


def test_label_must_be_from_allowed_list():
    with pytest.raises(ValidationError):
        ApplyLabelInput(email_id="em_001", label="delete_me")


@pytest.mark.parametrize("limit", [0, 51, -1])
def test_list_limit_bounds(limit):
    with pytest.raises(ValidationError):
        ListEmailsInput(limit=limit)


def test_send_reply_has_no_recipient_field():
    # Main injection defence: the model cannot choose who receives the email.
    assert "to" not in SendReplyInput.model_fields
    assert set(SendReplyInput.model_fields) == {"draft_id"}


def test_tool_result_shapes():
    ok = ToolResult.success("Archived em_003.", {"email_id": "em_003"})
    assert ok.ok and ok.error_code is None

    err = ToolResult.failure(ErrorCode.NOT_FOUND, "No email em_999.", hint="Call list_emails first.")
    dumped = err.model_dump(mode="json")
    assert dumped["ok"] is False
    assert dumped["error_code"] == "NOT_FOUND"
    assert dumped["hint"]
