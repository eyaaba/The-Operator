
"""Command-line interface for The Operator."""

import argparse
import json
import os
import uuid

from dotenv import load_dotenv


def get_human_decisions(interrupts):
    from agent.config import CHECKPOINT_POLICY

    decisions = []

    for interrupt in interrupts:
        detail = interrupt.value

        for action in detail.get("action_requests", []):
            name = action["name"]
            allowed = CHECKPOINT_POLICY.get(name, ["reject"])

            print(
                "\nPROPOSED WRITE:",
                json.dumps(action, indent=2, default=str)
            )

            options = ["Approve [a]", "Reject [r]"]

            if "edit" in allowed:
                options.append("Edit [e]")

            choice = input(
                ", ".join(options) + " (default reject): "
            ).strip().lower()

            if choice == "a" and "approve" in allowed:
                decisions.append({"type": "approve"})

            elif choice == "e" and "edit" in allowed:
                try:
                    edited = json.loads(
                        input("Replacement args as JSON: ")
                    )

                    if not isinstance(edited, dict):
                        raise ValueError(
                            "Arguments must be a JSON object."
                        )

                    decisions.append({
                        "type": "edit",
                        "edited_action": {
                            "name": name,
                            "args": edited,
                        },
                    })

                except (json.JSONDecodeError, ValueError) as exc:
                    print(f"Invalid edit: {exc}")

                    decisions.append({
                        "type": "reject",
                        "message": "Invalid edited arguments.",
                    })

            else:
                decisions.append({
                    "type": "reject",
                    "message": "Human rejected this write.",
                })

    return decisions


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="The Operator - Safe Email Management Agent"
    )

    parser.add_argument(
        "goal",
        nargs="*",
        help="Natural-language task for the agent."
    )

    args = parser.parse_args()

    from langgraph.types import Command
    from agent.graph import build_agent

    agent = build_agent()

    run_id = str(uuid.uuid4())

    os.environ["OPERATOR_RUN_ID"] = run_id

    config = {
        "configurable": {
            "thread_id": run_id
        },
        "recursion_limit": 75,
    }

    goal = " ".join(args.goal).strip() or "Triage my inbox."

    payload = {
        "messages": [
            {
                "role": "user",
                "content": goal,
            }
        ]
    }

    while True:
        result = agent.invoke(payload, config=config)

        interrupts = result.get("__interrupt__", ())

        if not interrupts:
            for message in result.get("messages", [])[-5:]:
                content = getattr(message, "content", "")

                if content:
                    print(
                        content
                        if isinstance(content, str)
                        else str(content)
                    )

            break

        decisions = get_human_decisions(interrupts)

        if not decisions:
            print("No approval decisions were provided. Stopping.")
            break

        payload = Command(
            resume={
                "decisions": decisions
            }
        )


if __name__ == "__main__":
    main()
