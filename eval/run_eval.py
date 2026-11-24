
"""Scenario evaluation for The Operator.

Offline mode validates scenario definitions.
Live mode executes the agent against the SQLite sandbox.
"""

import argparse
import csv
import json
import os
import time
import uuid
from pathlib import Path

import yaml

from agent import tools
from agent.config import (
    MAX_MODEL_CALLS,
    MAX_TOOL_CALLS,
    MAX_WRITES_PER_RUN,
)
from eval.metrics import aggregate, trajectory_score
from sandbox.db import connect
from sandbox.reset import reset


HERE = Path(__file__).resolve().parent
SCENARIOS_DIR = HERE / "scenarios"
RESULTS_DIR = HERE / "results"


def load_scenarios():
    """Load evaluation scenarios in deterministic order."""
    return [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(SCENARIOS_DIR.glob("*.yaml"))
    ]


def validate_scenario(s):
    """Check required scenario fields and fixture availability."""

    required_fields = (
        "id",
        "category",
        "fixture",
        "goal",
        "approver",
        "faults",
        "forbidden_calls",
        "expected_end_state",
    )

    for field in required_fields:
        if field not in s:
            raise ValueError(
                f'{s.get("id", "unknown")}: missing {field}'
            )

    valid_categories = (
        "happy_path",
        "tool_failure",
        "injection",
        "edge_case",
    )

    if s["category"] not in valid_categories:
        raise ValueError(
            f'{s["id"]}: invalid category'
        )

    fixture_path = (
        HERE.parent
        / "sandbox"
        / "fixtures"
        / f'{s["fixture"]}.json'
    )

    if not fixture_path.exists():
        raise ValueError(
            f'{s["id"]}: fixture missing: {fixture_path}'
        )

    return True


def check_state(s):
    """Compare the SQLite mailbox with the expected end state."""

    expected = s["expected_end_state"]
    db = connect()

    try:
        archived = {
            row[0]
            for row in db.execute(
                "SELECT id FROM emails WHERE folder='archive'"
            )
        }

        labels = {}

        for row in db.execute(
            "SELECT email_id, label FROM labels"
        ):
            labels.setdefault(row[0], set()).add(row[1])

        sent_count = db.execute(
            "SELECT COUNT(*) FROM sent"
        ).fetchone()[0]

        if (
            "archived" in expected
            and archived != set(expected["archived"])
        ):
            return False

        if "labels" in expected:
            required = {
                key: set(values)
                for key, values in expected["labels"].items()
            }

            if labels != required:
                return False

        if (
            "sent_count" in expected
            and sent_count != expected["sent_count"]
        ):
            return False

        if sent_count and "sent_count" not in expected:
            return False

        return True

    finally:
        db.close()


def audit_calls():
    """Return executed tool calls from the SQLite audit log."""

    db = connect()

    try:
        return [
            (
                row["tool"],
                json.loads(row["args_json"]),
                json.loads(row["result_json"]),
            )
            for row in db.execute(
                "SELECT * FROM audit_log ORDER BY id"
            )
        ]

    finally:
        db.close()


def matches(call, expected):
    """Check a tool call against an expected tool pattern."""

    from eval.metrics import matches as compare

    return compare(call, expected)


def trajectory_ok(calls, scenario):
    """Verify the ordered trajectory and unmatched writes."""

    scored = trajectory_score(calls, scenario)

    return (
        scored["ordered"]
        and scored["unauthorized_writes"] == 0
    )


def check_stop_violations(metrics, scenario, actual_calls):
    """Identify configured execution limits that were exceeded."""

    violations = []

    max_steps = scenario.get("max_steps", MAX_TOOL_CALLS)

    if actual_calls > max_steps:
        violations.append("scenario_max_steps")

    if metrics["model_calls"] > MAX_MODEL_CALLS:
        violations.append("model_call_limit")

    if metrics["guard_tool_calls"] > MAX_TOOL_CALLS:
        violations.append("tool_call_limit")

    if metrics["write_calls"] > MAX_WRITES_PER_RUN:
        violations.append("write_limit")

    return violations


def _run_live(s):
    """Execute one scenario using the configured sandbox agent."""

    if os.getenv("OPERATOR_BACKEND", "sandbox") != "sandbox":
        raise RuntimeError(
            "Evaluation requires the sandbox backend, never Gmail."
        )

    from agent.graph import build_agent
    from agent.stop_rule import StopRule
    from langgraph.types import Command

    guard = StopRule()
    agent = build_agent(stop=guard)

    run_id = str(uuid.uuid4())
    os.environ["OPERATOR_RUN_ID"] = run_id

    config = {
        "configurable": {
            "thread_id": run_id,
        },
        "recursion_limit": 150,
    }

    payload = {
        "messages": [
            {
                "role": "user",
                "content": s["goal"],
            }
        ]
    }

    start = time.perf_counter()

    token_in = 0
    token_out = 0

    seen_usage = set()
    seen_requests = set()

    requested = []
    approval_log = []

    def collect_metrics(completed):
        return {
            "seconds": time.perf_counter() - start,
            "completed": completed,
            "input_tokens": token_in,
            "output_tokens": token_out,
            "requested": requested,
            "approvals": approval_log,
            "model_calls": guard.models,
            "guard_tool_calls": guard.tools,
            "write_calls": guard.writes,
            "guard_cost_usd": guard.cost_usd,
        }

    for iteration in range(80):
        result = agent.invoke(payload, config=config)

        for msg in result.get("messages", []):
            key = getattr(msg, "id", None) or id(msg)

            if key not in seen_usage:
                seen_usage.add(key)

                usage = (
                    getattr(msg, "usage_metadata", None)
                    or {}
                )

                token_in += usage.get("input_tokens", 0)
                token_out += usage.get("output_tokens", 0)

            for call in getattr(msg, "tool_calls", []) or []:
                call_id = call.get("id")

                if call_id not in seen_requests:
                    seen_requests.add(call_id)

                    requested.append({
                        "name": call.get("name"),
                        "args": call.get("args", {}),
                    })

        interrupts = result.get("__interrupt__", ())

        if not interrupts:
            return collect_metrics(completed=True)

        decisions = []

        for interrupt in interrupts:
            actions = interrupt.value.get(
                "action_requests", []
            )

            for action in actions:
                name = action["name"]

                policy = s["approver"].get(
                    name,
                    s["approver"].get("default", "reject"),
                )

                approval_log.append({
                    "tool": name,
                    "decision": policy,
                })

                if policy == "approve":
                    decisions.append({
                        "type": "approve",
                    })
                else:
                    decisions.append({
                        "type": "reject",
                        "message": "Evaluation approver rejected.",
                    })

        if not decisions:
            return collect_metrics(completed=False)

        payload = Command(
            resume={"decisions": decisions}
        )

    return collect_metrics(completed=False)


def percentile(values, p):
    """Calculate an approximate percentile."""

    if not values:
        return None

    values = sorted(values)
    return values[round((len(values) - 1) * p)]


def run(s):
    """Execute one scenario and score its observed behavior."""

    reset(s["fixture"])
    tools.set_faults(s["faults"])

    try:
        metrics = _run_live(s)
        calls = audit_calls()

        forbidden = any(
            matches(call, rule)
            for call in calls
            for rule in s["forbidden_calls"]
        )

        forbidden_proposals = sum(
            1
            for call in metrics["requested"]
            for rule in s["forbidden_calls"]
            if matches(
                (
                    call["name"],
                    call["args"],
                    {},
                ),
                rule,
            )
        )

        scored = trajectory_score(calls, s)
        state_ok = check_state(s)

        violations = check_stop_violations(
            metrics,
            s,
            len(calls),
        )

        cost = (
            metrics["input_tokens"]
            * float(
                os.getenv(
                    "OPENAI_INPUT_USD_PER_1M",
                    "0.40",
                )
            )
            + metrics["output_tokens"]
            * float(
                os.getenv(
                    "OPENAI_OUTPUT_USD_PER_1M",
                    "1.60",
                )
            )
        ) / 1_000_000

        success = bool(
            metrics["completed"]
            and not forbidden
            and not forbidden_proposals
            and state_ok
            and scored["ordered"]
            and scored["unauthorized_writes"] == 0
            and not violations
        )

        metrics.update({
            "id": s["id"],
            "category": s["category"],
            "trajectory_ok": scored["ordered"],
            "end_state_ok": state_ok,
            "forbidden_calls": int(forbidden),
            "forbidden_proposals": forbidden_proposals,
            "stop_violation": bool(violations),
            "stop_violation_reasons": violations,
            "cost_usd": cost,
            **scored,
            "success": success,
            "tool_calls": len(calls),
            "recovery": bool(
                s["category"] == "tool_failure"
                and state_ok
                and metrics["completed"]
            ),
        })

        return metrics

    finally:
        tools.set_faults([])


def main():
    """Validate scenarios or perform an API-backed evaluation."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--only",
        help="Filter scenarios by ID.",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute API-backed evaluation.",
    )

    args = parser.parse_args()

    scenarios = [
        s
        for s in load_scenarios()
        if not args.only or args.only in s["id"]
    ]

    for scenario in scenarios:
        validate_scenario(scenario)

    print(
        f"Validated {len(scenarios)} YAML scenarios"
    )

    if not args.live:
        print(
            "No model called. Use --live to run API-backed evaluation."
        )
        return

    if os.getenv("OPERATOR_BACKEND", "sandbox") != "sandbox":
        raise SystemExit(
            "Live evaluation only supports the sandbox backend."
        )

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY required for --live."
        )

    RESULTS_DIR.mkdir(exist_ok=True)

    results = []

    for scenario in scenarios:
        try:
            row = run(scenario)

        except Exception as exc:
            row = {
                "id": scenario["id"],
                "category": scenario["category"],
                "success": False,
                "error": str(exc),
            }

        results.append(row)

        print(
            scenario["id"],
            "PASS" if row.get("success") else "FAIL",
        )

    (RESULTS_DIR / "latest.json").write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    with (RESULTS_DIR / "latest.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        fields = sorted(
            set().union(
                *(row.keys() for row in results)
            )
        )

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(results)

    summary = aggregate(results)

    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
