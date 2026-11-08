"""
Run every scenario in eval/scenarios and print the metrics table (Task 3.3 / 3.4).

    uv run python -m eval.run_eval              # all scenarios
    uv run python -m eval.run_eval --only S020  # one scenario

For each scenario: reset sandbox -> inject faults -> run agent with scripted
approver -> score trajectory (agentevals) + forbidden calls + end state ->
record steps, tokens, cost, latency.
"""

from pathlib import Path

import yaml

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenarios() -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(SCENARIOS_DIR.glob("*.yaml"))]


def main() -> None:
    scenarios = load_scenarios()
    print(f"Loaded {len(scenarios)} scenarios. Runner not implemented yet (Task 3.3).")


if __name__ == "__main__":
    main()
