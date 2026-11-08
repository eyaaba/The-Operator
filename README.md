# Inbox Operator

CS496 AI Engineering — Project 3 "The Operator" — MedTech, Fall 2026.

An email triage agent that reads a (sandboxed) inbox, labels and archives
emails, and drafts and sends replies — **only after a human approves each write**.

## Setup (one command)

Requires [uv](https://docs.astral.sh/uv/). Then:

```bash
uv sync
```

Copy `.env.example` to `.env` and paste the OpenAI key.

## Run (one command)

```bash
uv run python -m sandbox.reset && uv run python -m agent.cli "Triage my inbox"
```

## Other commands

| What | Command |
|---|---|
| Reset the sandbox mailbox | `uv run python -m sandbox.reset` |
| Run the tests | `uv run pytest` |
| Run the full eval | `uv run python -m eval.run_eval` |

## Stack

LangChain `create_agent` + middleware (human-in-the-loop, call limits, retries) ·
OpenAI `gpt-4.1-mini` · Pydantic strict schemas · SQLite sandbox ·
AgentEvals trajectory evaluators · pytest · LangSmith tracing (optional).

## Repo map

```
agent/        tools, schemas (the contract), the agent, config (limits), CLI
sandbox/      SQLite schema, fixture inboxes, reset script
eval/         30+ YAML scenarios, trajectory evaluator, metrics runner
tests/        contract, sandbox, stop-rule proofs
docs/         tool_contract.md
errors.md  threat_model.md  postmortem.md  report.pdf
```

## Results

_Filled in after the eval (Task 3.5)._

| Metric | Value |
|---|---|
| Task success rate (n=32) | |
| Recovery after failure | |
| Injection cases blocked | |
| Stop-rule violations | |
| Median cost per task | |
| p50 / p95 time per task | |

## Contributions

| Member | Owned | Also did |
|---|---|---|
| Nour | Task 2 — agent loop, stop rule, checkpoint | |
| Khalil | Task 1 — sandbox & tools | |
| Mohamed | Task 3 — evaluation & metrics | |
| Yosr | Task 4 — safety, threat model, deliverables | |
