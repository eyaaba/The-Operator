
"""Regression tests for evaluation stop-rule violation detection."""

from agent.config import (
    MAX_MODEL_CALLS,
    MAX_TOOL_CALLS,
    MAX_WRITES_PER_RUN,
)
from eval.run_eval import check_stop_violations


def make_metrics(
    model_calls=0,
    tool_calls=0,
    write_calls=0,
):
    return {
        "model_calls": model_calls,
        "guard_tool_calls": tool_calls,
        "write_calls": write_calls,
    }


def test_no_stop_violations_within_limits():
    scenario = {"max_steps": 25}

    metrics = make_metrics(
        model_calls=5,
        tool_calls=10,
        write_calls=3,
    )

    violations = check_stop_violations(
        metrics, scenario, actual_calls=10
    )

    assert violations == []


def test_reaching_limits_is_not_a_violation():
    scenario = {"max_steps": MAX_TOOL_CALLS}

    metrics = make_metrics(
        model_calls=MAX_MODEL_CALLS,
        tool_calls=MAX_TOOL_CALLS,
        write_calls=MAX_WRITES_PER_RUN,
    )

    violations = check_stop_violations(
        metrics,
        scenario,
        actual_calls=MAX_TOOL_CALLS,
    )

    assert violations == []


def test_model_call_limit_violation():
    scenario = {"max_steps": 100}

    metrics = make_metrics(
        model_calls=MAX_MODEL_CALLS + 1,
    )

    violations = check_stop_violations(
        metrics, scenario, actual_calls=0
    )

    assert "model_call_limit" in violations


def test_tool_call_limit_violation():
    scenario = {"max_steps": 100}

    metrics = make_metrics(
        tool_calls=MAX_TOOL_CALLS + 1,
    )

    violations = check_stop_violations(
        metrics, scenario, actual_calls=0
    )

    assert "tool_call_limit" in violations


def test_write_limit_violation():
    scenario = {"max_steps": 100}

    metrics = make_metrics(
        write_calls=MAX_WRITES_PER_RUN + 1,
    )

    violations = check_stop_violations(
        metrics, scenario, actual_calls=0
    )

    assert "write_limit" in violations


def test_scenario_step_limit_violation():
    scenario = {"max_steps": 8}
    metrics = make_metrics()

    violations = check_stop_violations(
        metrics, scenario, actual_calls=9
    )

    assert "scenario_max_steps" in violations


def test_multiple_stop_violations():
    scenario = {"max_steps": 8}

    metrics = make_metrics(
        model_calls=MAX_MODEL_CALLS + 1,
        tool_calls=MAX_TOOL_CALLS + 1,
        write_calls=MAX_WRITES_PER_RUN + 1,
    )

    violations = check_stop_violations(
        metrics, scenario, actual_calls=30
    )

    assert set(violations) == {
        "scenario_max_steps",
        "model_call_limit",
        "tool_call_limit",
        "write_limit",
    }
