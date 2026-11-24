
from types import SimpleNamespace

from agent.cli import get_human_decisions


def make_interrupt(tool):
    return SimpleNamespace(
        value={
            "action_requests": [
                {
                    "name": tool,
                    "args": {"email_id": "em_001"},
                }
            ]
        }
    )


def test_cli_approve(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "a")

    decisions = get_human_decisions([
        make_interrupt("archive_email")
    ])

    assert decisions == [{"type": "approve"}]


def test_cli_reject(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "r")

    decisions = get_human_decisions([
        make_interrupt("archive_email")
    ])

    assert decisions[0]["type"] == "reject"


def test_cli_rejects_unsupported_edit(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "e")

    decisions = get_human_decisions([
        make_interrupt("archive_email")
    ])

    assert decisions[0]["type"] == "reject"


def test_cli_rejects_invalid_json(monkeypatch):
    inputs = iter(["e", "{invalid"])

    monkeypatch.setattr(
        "builtins.input",
        lambda _: next(inputs)
    )

    decisions = get_human_decisions([
        make_interrupt("draft_reply")
    ])

    assert decisions[0]["type"] == "reject"


def test_cli_accepts_valid_edit(monkeypatch):
    inputs = iter([
        "e",
        '{"email_id": "em_001", "body": "Updated reply"}'
    ])

    monkeypatch.setattr(
        "builtins.input",
        lambda _: next(inputs)
    )

    decisions = get_human_decisions([
        make_interrupt("draft_reply")
    ])

    assert decisions[0]["type"] == "edit"
    assert decisions[0]["edited_action"]["args"]["body"] == "Updated reply"
