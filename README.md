# The Operator — CS496 Project 3

A **sandbox-only** inbox operator built with LangChain `create_agent` and `gpt-4.1-mini`.

## Safety-first design

- Seven tools: `list_emails`, `read_email`, `apply_label`, `archive_email`, `draft_reply`, `send_reply`, `finish`.
- Pydantic schemas forbid extra input fields; write tools are SQLite-only and idempotent.
- The write tools cannot execute until a human reviews the LangChain HITL interrupt.
- Model/tool call caps, repeated-call and write caps, failure retries, and a cost stop-policy module.
- No email text is trusted as instructions. `send_reply` can send **only to the original sender**.
- Audit logs capture sanitized structured tool arguments and results. Use synthetic fixture data only.

## Install and run

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env  # Windows: copy .env.example .env
# Set OPENAI_API_KEY in .env; NEVER commit it.
uv run python -m sandbox.reset
uv run python -m agent.cli "Label the Tech Weekly newsletter as newsletter and archive it"
```

Each write is interrupted for interactive approval, rejection or approved editing, before any sandbox mutation. If a task only asks for a draft, **do not approve send actions**.

## Tests and evaluation

```bash
uv run pytest
uv run python -m eval.run_eval              # validate all 32 YAML scenario definitions offline
uv run python -m eval.run_eval --only S001 --live # uses OpenAI API and costs money
uv run python -m eval.run_eval --live        # full 32-scenario live evaluation
```

Live outputs are saved to ignored `eval/results/latest.json`, `latest.csv`, `summary.json`. These are **not** precomputed model success claims. Evaluation scores forbidden calls, expected order of tool calls, and SQLite end state; validates test failures and human rejection via scenario definitions. Live trajectory evaluation is deterministic rule-based, not LLM-as-judge. `agentevals` is in the dependency set for future optional comparison.

## Project status

- Task 1: seven operational SQLite tools, idempotency, error hints, fault injection and audit logging.
- Task 2: create_agent, safety middleware, HITL with in-memory checkpoint, stop-policy unit tests, CLI. **Requires API-backed integration validation.**
- Task 3: 32 YAML scenarios, validator, rule-based trajectory and state metrics runner. **Live scores not yet measured.**
- Task 4: threat model, error taxonomy, postmortem and delivery instructions.

Limitations: in-memory checkpoints do not survive process restarts; cost accounting in `StopRule` is configurable but is not yet wired to live model usage; the live evaluator does not yet report authoritative API billing. The repeated-call cap denies the offending tool request but does not itself end the entire graph. All sends are sandbox table inserts, never real email.

## Files

`agent/` schema, tools, agent, CLI and limits · `sandbox/` SQLite schema/fixtures/reset · `eval/` scenarios and runner · `tests/` deterministic safety tests · `docs/` tool contract · `threat_model.md`, `errors.md`, `postmortem.md`.
