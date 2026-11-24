import pytest
from agent.stop_rule import StopRule, StopRun
from agent.config import MAX_MODEL_CALLS, MAX_TOOL_CALLS, MAX_WRITES_PER_RUN, MAX_REPEATED_CALL

def test_stops_at_max_model_calls():
    s=StopRule()
    for _ in range(MAX_MODEL_CALLS): s.before_model()
    with pytest.raises(StopRun): s.before_model()

def test_stops_at_max_tool_calls():
    s=StopRule()
    for i in range(MAX_TOOL_CALLS): s.before_tool('read_email', {'email_id':f'em_{i+1:03}'})
    with pytest.raises(StopRun): s.before_tool('list_emails',{})

def test_stops_on_repeated_identical_call():
    s=StopRule()
    for _ in range(MAX_REPEATED_CALL): s.before_tool('read_email', {'email_id':'em_001'})
    with pytest.raises(StopRun): s.before_tool('read_email', {'email_id':'em_001'})

def test_stops_at_write_cap():
    s=StopRule()
    for i in range(MAX_WRITES_PER_RUN): s.before_tool('archive_email', {'email_id':f'em_{i+1:03}'})
    with pytest.raises(StopRun): s.before_tool('archive_email', {'email_id':'em_999'})

def test_finish_ends_the_run():
    s=StopRule();s.before_model();s.before_tool('finish', {'summary':'done'})
    with pytest.raises(StopRun): s.before_model()


def test_stops_when_cost_budget_is_reached(monkeypatch):
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_1M", "1000000")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_1M", "1000000")

    stop = StopRule(max_cost_usd=0.50)

    stop.before_model()
    stop.add_usage(input_tokens=1, output_tokens=0)

    assert stop.cost_usd == pytest.approx(1.0)

    with pytest.raises(StopRun):
        stop.before_model()

def test_retries_count_toward_tool_limit():
    stop = StopRule()

    stop.before_tool("read_email", {"email_id": "em_001"})

    assert stop.tools == 1

    stop.before_retry("read_email")

    assert stop.tools == 2


def test_write_retries_count_toward_write_limit():
    stop = StopRule()

    stop.before_tool("archive_email", {"email_id": "em_001"})

    assert stop.writes == 1

    stop.before_retry("archive_email")

    assert stop.writes == 2

def test_retry_blocked_at_tool_limit():
    stop = StopRule()

    for i in range(MAX_TOOL_CALLS):
        stop.before_tool(
            "read_email",
            {"email_id": f"em_{i+1:03}"}
        )

    with pytest.raises(StopRun):
        stop.before_retry("read_email")


def test_write_retry_blocked_at_write_limit():
    stop = StopRule()

    for i in range(MAX_WRITES_PER_RUN):
        stop.before_tool(
            "archive_email",
            {"email_id": f"em_{i+1:03}"}
        )

    with pytest.raises(StopRun):
        stop.before_retry("archive_email")
