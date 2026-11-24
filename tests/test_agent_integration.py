
"""Integration tests for the agent graph, human approval, and safety limits."""

from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from agent.graph import build_agent
from agent.stop_rule import StopRule
from sandbox.db import connect
from sandbox.reset import reset


class FakeToolCallingModel(FakeMessagesListChatModel):
    """Fake chat model that supports LangChain tool binding."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_write_requires_human_approval(tmp_path, monkeypatch):
    from sandbox import db as database

    db_path = tmp_path / "test_mailbox.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "archive_email",
                        "args": {"email_id": "em_001"},
                        "id": "call_archive_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Task finished."),
        ]
    )

    agent = build_agent(stop=StopRule(), model=model)

    config = {
        "configurable": {
            "thread_id": "test-human-approval"
        }
    }

    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content="Archive email em_001.")
            ]
        },
        config=config,
    )

    assert result.get("__interrupt__"), (
        "The agent must interrupt before executing a write."
    )

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT folder FROM emails WHERE id = ?",
            ("em_001",),
        ).fetchone()

        assert row is not None
        assert row["folder"] == "inbox"
    finally:
        conn.close()


def test_rejected_write_does_not_modify_database(tmp_path, monkeypatch):
    from sandbox import db as database

    db_path = tmp_path / "rejection_test.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "archive_email",
                        "args": {"email_id": "em_001"},
                        "id": "call_reject_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="The archive request was rejected."),
        ]
    )

    agent = build_agent(stop=StopRule(), model=model)

    config = {
        "configurable": {
            "thread_id": "test-human-rejection"
        }
    }

    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content="Archive email em_001.")
            ]
        },
        config=config,
    )

    assert result.get("__interrupt__")

    agent.invoke(
        Command(
            resume={
                "decisions": [
                    {
                        "type": "reject",
                        "message": "Do not archive this email.",
                    }
                ]
            }
        ),
        config=config,
    )

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT folder FROM emails WHERE id = ?",
            ("em_001",),
        ).fetchone()

        assert row is not None
        assert row["folder"] == "inbox"
    finally:
        conn.close()


def test_approved_write_modifies_database(tmp_path, monkeypatch):
    from sandbox import db as database

    db_path = tmp_path / "approval_test.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "archive_email",
                        "args": {"email_id": "em_001"},
                        "id": "call_approve_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Email archived successfully."),
        ]
    )

    agent = build_agent(stop=StopRule(), model=model)

    config = {
        "configurable": {
            "thread_id": "test-human-approval-success"
        }
    }

    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content="Archive email em_001.")
            ]
        },
        config=config,
    )

    assert result.get("__interrupt__")

    agent.invoke(
        Command(
            resume={
                "decisions": [
                    {"type": "approve"}
                ]
            }
        ),
        config=config,
    )

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT folder FROM emails WHERE id = ?",
            ("em_001",),
        ).fetchone()

        assert row is not None
        assert row["folder"] == "archive"
    finally:
        conn.close()


def test_approved_write_is_idempotent(tmp_path, monkeypatch):
    from sandbox import db as database
    from agent import tools

    db_path = tmp_path / "idempotency_test.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    draft = tools.draft_reply(
        "em_001",
        "Thank you for your message."
    )
    assert draft.ok

    draft_id = draft.data["draft_id"]

    first = tools.send_reply(draft_id)
    second = tools.send_reply(draft_id)

    assert first.ok
    assert second.ok
    assert second.idempotent_replay

    conn = connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sent WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()[0]

        assert count == 1
    finally:
        conn.close()


def test_agent_graph_stops_at_model_limit(tmp_path, monkeypatch):
    """Verify model-call limits in the actual LangChain graph."""

    from agent.config import MAX_MODEL_CALLS
    from sandbox import db as database

    db_path = tmp_path / "model_limit_test.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "list_emails",
                    "args": {
                        "folder": "inbox",
                        "unread_only": False,
                        "limit": i + 1,
                    },
                    "id": f"call_{i}",
                    "type": "tool_call",
                }
            ],
        )
        for i in range(MAX_MODEL_CALLS + 10)
    ]

    model = FakeToolCallingModel(responses=responses)
    stop = StopRule()
    agent = build_agent(stop=stop, model=model)

    config = {
        "configurable": {
            "thread_id": "test-model-call-limit"
        },
        "recursion_limit": 150,
    }

    try:
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="Keep checking the inbox repeatedly."
                    )
                ]
            },
            config=config,
        )

    except GraphRecursionError:
        print("\n--- MODEL LIMIT DIAGNOSTICS ---")
        print(f"Model calls: {stop.models}")
        print(f"Tool calls: {stop.tools}")
        print(f"Writes: {stop.writes}")
        print(f"Finished: {stop.finished}")
        print(f"Configured model limit: {MAX_MODEL_CALLS}")
        print("--------------------------------\n")
        raise

    assert stop.models == MAX_MODEL_CALLS
    assert not result.get("__interrupt__")


def test_agent_graph_stops_at_tool_limit(tmp_path, monkeypatch):
    """Check the tool-call budget in the actual LangChain graph."""

    from agent.config import MAX_TOOL_CALLS
    from sandbox import db as database

    db_path = tmp_path / "tool_limit_test.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    # Each model response requests five read-only tools.
    # Unique email IDs avoid the repeated-call guard.
    responses = []

    for batch in range(10):
        tool_calls = [
            {
                "name": "read_email",
                "args": {
                    "email_id": f"em_{batch * 5 + i + 1:03d}"
                },
                "id": f"call_{batch}_{i}",
                "type": "tool_call",
            }
            for i in range(5)
        ]

        responses.append(
            AIMessage(
                content="",
                tool_calls=tool_calls,
            )
        )

    model = FakeToolCallingModel(responses=responses)
    stop = StopRule()
    agent = build_agent(stop=stop, model=model)

    config = {
        "configurable": {
            "thread_id": "test-tool-call-limit"
        },
        "recursion_limit": 150,
    }

    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Read all the requested test emails."
                )
            ]
        },
        config=config,
    )

    print("\n--- TOOL LIMIT DIAGNOSTICS ---", flush=True)
    print(f"MODEL CALLS: {stop.models}", flush=True)
    print(f"TOOL CALLS: {stop.tools}", flush=True)
    print(f"TOOL LIMIT: {MAX_TOOL_CALLS}", flush=True)
    print("--------------------------------\n", flush=True)

    assert stop.tools == MAX_TOOL_CALLS
    assert stop.writes == 0
    assert not result.get("__interrupt__")

def test_agent_stops_when_cost_budget_exhausted():
    """The graph should terminate when no cost budget remains."""

    model = FakeToolCallingModel(
        responses=[
            AIMessage(content="This response should not be generated.")
        ]
    )

    stop = StopRule(max_cost_usd=0.0)
    agent = build_agent(stop=stop, model=model)

    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content="Check my inbox.")
            ]
        },
        config={
            "configurable": {
                "thread_id": "test-cost-budget-exhausted"
            },
            "recursion_limit": 30,
        },
    )

    assert stop.models == 0
    assert stop.tools == 0
    assert not result.get("__interrupt__")


def test_write_limit_blocks_approved_operation(tmp_path, monkeypatch):
    """An approved write must not bypass an exhausted write budget."""

    from agent.config import MAX_WRITES_PER_RUN
    from sandbox import db as database

    db_path = tmp_path / "write_limit_test.db"
    reset(path=db_path)

    monkeypatch.setenv("OPERATOR_BACKEND", "sandbox")
    monkeypatch.setattr(database, "SANDBOX_DB", str(db_path))

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "archive_email",
                        "args": {"email_id": "em_001"},
                        "id": "call_write_limit",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Write limit reached."),
        ]
    )

    stop = StopRule()
    stop.writes = MAX_WRITES_PER_RUN

    agent = build_agent(stop=stop, model=model)

    config = {
        "configurable": {
            "thread_id": "test-write-limit"
        },
        "recursion_limit": 75,
    }

    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content="Archive email em_001.")
            ]
        },
        config=config,
    )

    # Human approval may still be requested before the safety guard runs.
    if result.get("__interrupt__"):
        result = agent.invoke(
            Command(
                resume={
                    "decisions": [
                        {"type": "approve"}
                    ]
                }
            ),
            config=config,
        )

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT folder FROM emails WHERE id = ?",
            ("em_001",),
        ).fetchone()

        assert row is not None
        assert row["folder"] == "inbox"
    finally:
        conn.close()

    assert stop.writes == MAX_WRITES_PER_RUN
