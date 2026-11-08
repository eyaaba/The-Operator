"""
Run the agent from the terminal (Task 2.6).

    uv run python -m agent.cli "Triage my inbox and draft replies to anything urgent"

Shows each step with rich and asks for approval before every write.
"""

import sys


def main() -> None:
    goal = " ".join(sys.argv[1:]) or "Triage my inbox."
    print(f"[not implemented yet - Task 2.6] goal = {goal!r}")


if __name__ == "__main__":
    main()
