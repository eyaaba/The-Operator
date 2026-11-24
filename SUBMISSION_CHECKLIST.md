# Final release checklist (Windows PowerShell)

The source package does not contain `.env`, Gmail OAuth credentials or a verified live run. Do not call it fully submission-ready until the steps below pass.

1. Extract to a clean directory and install dependencies with network access:

   ```powershell
   uv lock
   uv sync --extra gmail --extra report
   Copy-Item .env.example .env
   ```

2. Edit `.env` and add a valid `OPENAI_API_KEY`. Use `OPERATOR_BACKEND=sandbox` while validating the agent and evaluation.

   ```powershell
   uv run python -m sandbox.reset
   uv run pytest -q
   uv run python -m eval.run_eval
   uv run python -m agent.cli "Label the Tech Weekly newsletter as newsletter and archive it"
   ```

   Confirm that the agent interrupts before every write, permits a rejection without a mutation, and resumes when approved. If a live run raises an error, capture its exact traceback and fix it before continuing.

3. Run the evaluation in the **SQLite sandbox**:

   ```powershell
   uv run python -m eval.run_eval --only S001 --live
   uv run python -m eval.run_eval --live
   ```

   Inspect `eval/results/latest.csv`, `latest.json` and `summary.json`. Validate failures, unexpected writes, step accuracy, tool-call precision, timing, token cost and injection-case behavior. Review each failing case; do not replace failures with invented successes. Note that the scripted evaluator approver does not substitute for a person at the CLI checkpoint.

4. Optional real Gmail test-mailbox demonstration: use the dedicated test mailbox setup in README, then:

   ```powershell
   uv run python -m agent.gmail_setup
   uv run python -m agent.cli "List my test inbox without changing anything"
   ```

   Enable sending only for an allowlisted controlled test recipient. Never use a personal or work Gmail inbox. Gmail modifications cannot be undone with the SQLite reset command.

5. Finalize the report using the live 32-case summary:

   ```powershell
   uv run python scripts/build_report.py
   ```

   Confirm `report.pdf` is four pages, displays measured live results, and matches the latest evaluation data. Include screenshots of the live demo if the instructor requests them.

6. Confirm team contributions and ensure all secrets are excluded from Git:

   ```powershell
   git status --short
   git check-ignore .env .gmail_state/token.json client_secret.json sandbox/mailbox.db
   git diff --check
   ```

   Push after the clean-clone test. Keep the repository freeze deadline in mind. Only mark Tasks 2-4 Done after evidence has been reviewed.
