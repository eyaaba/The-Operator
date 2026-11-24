import json
from unittest.mock import MagicMock

from agent import tools
from agent.gmail_backend import _execute as gmail_execute
from agent.schemas import ErrorCode
from agent.stop_rule import StopRule, StopRun
from eval.metrics import aggregate, trajectory_score
from eval.run_eval import check_state
from sandbox.db import connect
from sandbox.reset import reset


def test_read_email_does_not_change_mailbox(tmp_path, monkeypatch):
    from sandbox import db as database
    path = tmp_path / 'mailbox.db'
    reset(path=path)
    monkeypatch.setattr(database, 'SANDBOX_DB', str(path))
    assert tools.read_email('em_001').ok
    db = connect(path)
    assert db.execute('SELECT is_read FROM emails WHERE id=?', ('em_001',)).fetchone()[0] == 0
    db.close()


def test_invalid_args_are_audited(tmp_path, monkeypatch):
    from sandbox import db as database
    path = tmp_path / 'mailbox.db'
    reset(path=path)
    monkeypatch.setattr(database, 'SANDBOX_DB', str(path))
    assert tools.read_email('not_valid').error_code == ErrorCode.INVALID_ARGUMENT
    db = connect(path)
    row = db.execute('SELECT tool, result_json FROM audit_log ORDER BY id DESC LIMIT 1').fetchone()
    assert row['tool'] == 'read_email'
    assert json.loads(row['result_json'])['error_code'] == 'INVALID_ARGUMENT'
    db.close()


def test_draft_body_not_recorded_in_audit(tmp_path, monkeypatch):
    from sandbox import db as database
    path = tmp_path / 'mailbox.db'
    reset(path=path)
    monkeypatch.setattr(database, 'SANDBOX_DB', str(path))
    assert tools.draft_reply('em_001', 'PRIVATE MESSAGE CONTENT').ok
    db = connect(path)
    text = db.execute('SELECT args_json, result_json FROM audit_log ORDER BY id DESC LIMIT 1').fetchone()
    assert 'PRIVATE MESSAGE CONTENT' not in text['args_json']
    assert 'PRIVATE MESSAGE CONTENT' not in text['result_json']
    db.close()


def test_unexpected_write_fails_trajectory():
    calls = [('list_emails', {}, {'ok': True}), ('send_reply', {'draft_id':'dr_001'}, {'ok':True}),
             ('finish', {'summary':'done'}, {'ok': True})]
    scenario = {'expected_trajectory': {'steps':[{'tool':'list_emails'}, {'tool':'finish'}]}}
    score = trajectory_score(calls, scenario)
    assert score['ordered'] and score['unauthorized_writes'] == 1
    assert score['tool_call_precision'] < 1


def test_empty_archive_assertion_is_exact(tmp_path, monkeypatch):
    from sandbox import db as database
    path = tmp_path / 'mailbox.db'
    reset(path=path)
    monkeypatch.setattr(database, 'SANDBOX_DB', str(path))
    db = connect(path)
    db.execute("UPDATE emails SET folder='archive' WHERE id='em_001'")
    db.commit()
    db.close()
    assert not check_state({'expected_end_state': {'archived': [], 'sent_count': 0}})


def test_cost_limit_stops_model_calls():
    from pytest import raises
    stop = StopRule(max_cost_usd=.0001)
    stop.add_usage(500, 0)
    with raises(StopRun):
        stop.before_model()


def test_gmail_rejects_send_without_explicit_enable(monkeypatch):
    monkeypatch.delenv('OPERATOR_ENABLE_GMAIL_SEND', raising=False)
    service = MagicMock()
    state = {'emails': {}, 'drafts': {'dr_001': {'id':'gmail_draft','email_id':'em_001',
             'body':'test','recipient':'test@example.com'}}, 'sent':{}}
    result = gmail_execute(service, 'test-account@example.com', 'send_reply', {'draft_id':'dr_001'}, state)
    assert result.error_code == ErrorCode.NOT_ALLOWED
    service.users().drafts().send.assert_not_called()


def test_gmail_rejects_unlisted_recipient(monkeypatch):
    monkeypatch.setenv('OPERATOR_ENABLE_GMAIL_SEND', 'yes')
    monkeypatch.setenv('OPERATOR_GMAIL_ALLOWED_RECIPIENTS', 'trusted@example.com')
    service = MagicMock()
    state = {'emails': {}, 'drafts': {'dr_001': {'id':'gmail_draft','email_id':'em_001',
             'body':'test','recipient':'attacker@example.com'}}, 'sent':{}}
    result = gmail_execute(service, 'test-account@example.com', 'send_reply', {'draft_id':'dr_001'}, state)
    assert result.error_code == ErrorCode.NOT_ALLOWED
    service.users().drafts().send.assert_not_called()


def test_aggregates_report_metrics():
    rows = [{'category':'happy_path','success':True,'seconds':1,'input_tokens':100,'output_tokens':20,
             'cost_usd':0.001,'tool_call_precision':1,'step_accuracy':1,'wasted_steps':0},
            {'category':'tool_failure','success':False,'seconds':2,'input_tokens':200,'output_tokens':40,
             'cost_usd':0.002,'tool_call_precision':.5,'step_accuracy':.5,'wasted_steps':2}]
    result = aggregate(rows)
    assert result['task_success_rate'] == .5
    assert result['recovery_rate'] == 0
    assert result['projected_cost_100_tasks_usd'] == .15


def test_retry_attempts_count_toward_tool_cap():
    from pytest import raises
    from agent.config import MAX_TOOL_CALLS
    stop = StopRule()
    stop.before_tool('list_emails', {})
    for _ in range(MAX_TOOL_CALLS-1):
        stop.before_retry('list_emails')
    with raises(StopRun):
        stop.before_retry('list_emails')

def test_unexpected_write_in_incomplete_trajectory():
    from eval.metrics import trajectory_score

    scenario = {
        "expected_trajectory": {
            "steps": [
                {"tool": "list_emails"},
                {"tool": "read_email"},
                {"tool": "finish"},
            ]
        }
    }

    actual_calls = [
        ("list_emails", {}, None),
        ("send_reply", {"draft_id": "draft_001"}, None),
        ("finish", {"summary": "Done"}, None),
    ]

    score = trajectory_score(actual_calls, scenario)

    assert score["ordered"] is False
    assert score["unauthorized_writes"] == 1
    assert score["step_accuracy"] < 1.0
    assert score["wasted_steps"] >= 1

def test_missing_evaluation_metrics_are_not_counted_as_zero():
    from eval.metrics import aggregate

    rows = [
        {
            "category": "happy_path",
            "success": True,
            "step_accuracy": 1.0,
            "tool_call_precision": 0.8,
            "wasted_steps": 1,
            "seconds": 2.0,
        },
        {
            "category": "happy_path",
            "success": False,
            "error": "API quota exceeded",
        },
    ]

    summary = aggregate(rows)

    assert summary["evaluated"] == 2
    assert summary["task_success_rate"] == 0.5

    # Only the successfully measured trajectory contributes.
    assert summary["step_accuracy"] == 1.0
    assert summary["tool_call_precision"] == 0.8
    assert summary["wasted_steps_per_task"] == 1

    # Missing cost measurements must not become zero-cost estimates.
    assert summary["total_cost_usd"] is None
    assert summary["mean_cost_per_task_usd"] is None
    assert summary["projected_cost_100_tasks_usd"] is None
