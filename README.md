# The Operator

CS496 AI Engineering · Project 3 · Fall 2026

An email triage agent using LangChain `create_agent`, `gpt-4.1-mini`, seven structured tools, human approval checkpoints, and a reproducible trajectory-level evaluation suite. It supports two separate backends:

- **SQLite sandbox (default):** synthetic messages, deterministic reset, fault injection, grading and evaluations.
- **Gmail test mailbox (opt-in):** real Gmail API operations via OAuth, restricted to a dedicated test account. This is for an integration demonstration, **not** the evaluation backend and **not** a personal/production inbox.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- OpenAI API key for model-backed runs (never commit credentials)
- Gmail OAuth desktop client credentials, only if testing Gmail

## Install and run with the graded sandbox

```powershell
uv sync
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY locally.
uv run python -m sandbox.reset
uv run pytest
uv run python -m eval.run_eval
uv run python -m agent.cli "Label the Tech Weekly newsletter as newsletter and archive it"
```

Every explicit write (`apply_label`, `archive_email`, `draft_reply`, `send_reply`) is interrupted for approval. Use `[r]` to reject; do not approve a `send_reply` action when the user requested only a draft.

## Gmail test-account integration

1. Create a **separate, disposable Gmail account** with no private/real messages. Create at least one other controlled test recipient. Do not use your regular mailbox.
2. In Google Cloud Console, enable the Gmail API and configure the OAuth consent screen. Create an OAuth **Desktop application** client. For a testing-mode app, register the test account as a test user. Download the client JSON into the local project folder as `client_secret.json` (ignored by Git).
3. Install Gmail support: `uv sync --extra gmail`.
4. Edit `.env`:

```dotenv
OPERATOR_BACKEND=gmail
OPERATOR_GMAIL_TEST_ACCOUNT=dedicated-test-account@gmail.com
OPERATOR_GMAIL_CLIENT_SECRETS=client_secret.json
OPERATOR_GMAIL_ALLOWED_RECIPIENTS=other-controlled-test@example.com
OPERATOR_ENABLE_GMAIL_SEND=no
```

5. Run `uv run python -m agent.gmail_setup` to complete OAuth in your browser and verify the account identity. Then run:

```powershell
uv run python -m agent.cli "List my test inbox and summarize the subjects. Do not change anything."
```

6. For a controlled write demo, request a label or archive operation and explicitly approve it in the CLI. **Sending remains disabled** unless `OPERATOR_ENABLE_GMAIL_SEND=yes` is explicitly configured, a recipient is on the allowlist, and you also approve the `send_reply` checkpoint. Gmail `send_reply` will send a **real email** to the original sender of the test message.

Do not use `sandbox.reset` to reset Gmail; it only resets SQLite. Gmail message IDs are mapped to strict tool IDs in ignored `.gmail_state/aliases.json` so the existing tool contract remains unchanged. Gmail is not used for the 32-scenario evaluation because it cannot provide a deterministic full reset. Google scopes (`gmail.modify` and `gmail.compose`) are sensitive/restricted; use a test-only app and follow Google's current OAuth policies.

## Seven tool contracts

| Tool | Kind | Effect |
|---|---|---|
| `list_emails` | Read | List message metadata |
| `read_email` | Read | Read content **without changing read status** |
| `apply_label` | Write | Apply an allowlisted label |
| `archive_email` | Write | Remove the message from inbox |
| `draft_reply` | Write | Prepare a reply without sending |
| `send_reply` | Write | Send the existing approved draft to its original sender |
| `finish` | Control | Record a short completion summary |

Tool inputs are Pydantic-validated, extra fields rejected, and failures return structured hints. SQLite writes are idempotent and audited; Gmail is separately restricted with account and recipient allowlists and requires human approval through the agent. Sending is never retried blindly after an uncertain API failure.

## Agent safety

The agent uses `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`, a custom `StopRule` and `HumanInTheLoopMiddleware` with an in-memory checkpointer. Configured limits are 15 model calls, 25 tool calls, 10 writes, 2 identical-call repetitions, 2 retries for transient non-send tool errors, and an estimated $0.05 model-usage ceiling. The model-budget check is based on returned usage and may overrun by a single call; it is a soft cost bound, **not** a billing guarantee. In-memory approvals cannot survive a process restart.

Email subjects/bodies/sender names are untrusted data. `send_reply` deliberately has no `to` parameter. Gmail real sending also requires a recipient allowlist and is disabled by default. This implementation does not permanently delete messages.

## Evaluation

```powershell
uv run pytest -q                         # offline regression tests
uv run python -m eval.run_eval           # schema validation only, no model call
uv run python -m eval.run_eval --only S001 --live
uv run python -m eval.run_eval --live     # all 32; OpenAI credits required
```

The runner uses the **SQLite backend only**, resets a known synthetic fixture for each case, applies simulated tool faults, and scripts the human checkpoint decisions. Cases cover happy paths (10), injected content (9), tool failures (6), and edge cases (7). The YAML validator checks format; **32 valid definitions are not 32 passing agent runs**.

Metrics include task success, ordered trajectory, unauthorized writes, expected database state, step accuracy, tool-call precision, wasted steps, tool-failure recovery, injection-case outcomes, latency, input/output tokens, estimated cost and projected cost at 100 tasks. Prices are configured in `.env` (defaults $0.40 and $1.60 per million input/output tokens; verify against the model provider's current rate). Cost estimates are not invoices. Scenario quality and correctness require real model execution and human review before making a submission claim.

Live results are written to ignored `eval/results/latest.json`, `latest.csv` and `summary.json`. A failed live run is a failure; it must not be silently counted as success.

## Report

Generate the maximum-four-page report using:

```powershell
uv sync --extra report
uv run python scripts/build_report.py
```

The report generator reads `eval/results/summary.json` if available; otherwise it explicitly states that live metrics are pending. Re-run it **after** all 32 live scenarios and the final clean-clone verification. Never fabricate missing measurements.

## Project structure

- `agent/`: schemas, tools, stop policy, LangChain graph, CLI, Gmail OAuth adapter
- `sandbox/`: SQLite schema, seed fixture, reset script
- `eval/`: 32 YAML cases, deterministic scorer, live runner
- `tests/`: contract, sandbox, tool, stop and security regression tests
- `docs/`: tool contract and technical references
- `errors.md`, `threat_model.md`, `postmortem.md`: safety documents
- `scripts/build_report.py`: reproducible four-page report generator


## Current verification status

Offline tests and evaluation definition validation can be reproduced without credentials. Gmail OAuth, Gmail API mutations, live `gpt-4.1-mini` execution, complete human approval/resume behavior, all live metrics and final submission readiness **must be verified on a credentialed test machine**. A working live run must not be assumed from offline tests.
