# Bloomi — Project 3 task cards

## Task 1 — Sandbox & Tools
- **Assignee:** Khalil
- **Size:** Large
- **Priority:** High
- **Status:** Review (offline tests pass; GitHub push pending)
- **Description:** Implement seven schema-validated sandbox tools (two reads, four writes and finish), SQLite state changes, idempotent writes, actionable structured errors, call logging and deterministic injected failures.
- **Review criteria:** All seven tools callable; no real mailbox access; repeated writes do not duplicate state; SQLite audit and fault tests pass.

## Task 2 — Agent Loop, Stop Rule & Human Checkpoint
- **Assignee:** Eya
- **Size:** Large
- **Priority:** High
- **Status:** Review after a live run (offline stop tests pass)
- **Description:** Implement the LangChain `create_agent` loop with `gpt-4.1-mini`; implement and test stopping conditions first; enforce model/tool-call limits, repeated-call and write caps, bounded transient failure retries, HITL review before every write, system prompt and interactive CLI.
- **Acceptance:** Complete live CLI run with explicit approvals and rejections; verify write-denial never mutates the mailbox; verify budget limit and prompt-injection behavior.

## Task 3 — Evaluation Suite & Metrics
- **Assignee:** Mohamed
- **Size:** Large
- **Priority:** High
- **Status:** In progress (32 scenarios validate; API-run metrics pending)
- **Description:** Build 32 YAML scenarios across happy paths, tool failures, edge cases and prompt injections. Reset fixtures, inject faults, run with scripted human decisions, compare tool trajectories and forbidden calls, query resulting SQLite state, and export per-scenario metrics and summary.
- **Acceptance:** Run `uv run python -m eval.run_eval --live`, inspect 32 results and report measured success rate, failure recovery, injection pass rate, zero forbidden actions, stop-rule violations, p50/p95 latency and estimated token cost.

## Task 4 — Safety, Threat Model & Deliverables
- **Assignee:** Yosr
- **Size:** Large
- **Priority:** Medium
- **Status:** Review (report/results pending)
- **Description:** Document user-visible threat model and prompt-injection attack surface, unsafe tool policy, HITL and budget defenses; maintain error taxonomy, setup/usage README and dated postmortem; produce final report with verified screenshots and measured evaluation results.
- **Acceptance:** Explain five or more injection cases, document residual risks and recovery behavior, provide README and reproducible commands, verify no secrets are tracked, and include genuine measured results in final hand-in.

## Git push — safe workflow

**Do not run `git push --force`**. This ZIP intentionally excludes `.git` and `.env`.

From your real repository on Windows:

```powershell
git status
git fetch origin
# Resolve any existing README.md conflict before proceeding.
# Keep a backup of your current repository / uncommitted changes.
git merge origin/main
# Copy the new source files from the clean deliverable into this repository.
# Never copy .env, sandbox/mailbox.db, or caches.
git add agent sandbox eval tests docs README.md threat_model.md errors.md postmortem.md BLOOMI_TASKS.md .env.example
git diff --cached --check
git status
git commit -m "Implement sandbox operator, agent safety, evaluation and docs"
git push origin main
```

If a merge conflict remains, resolve it manually and verify changes before committing. A clean ZIP is not a replacement for your repository's Git history.
