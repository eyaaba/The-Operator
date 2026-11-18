# Postmortem and implementation journal

| Date | Observation | Impact | Fix / next action |
|---|---|---|---|
| 2026-11-18 | Uploaded ZIP and GitHub `agent/tools.py` still contained `NotImplementedError`, despite Task 1 being described as complete | Task 1 could not be verified | Implemented six SQLite email operations and the finish tool; added end-to-end offline tests |
| 2026-11-18 | ZIP contained unresolved `README.md` merge conflict; local Git history was ahead/behind origin | A blind push could overwrite others' work | Created a clean deliverable without `.git`; remote reconciliation required before push |
| 2026-11-18 | LangChain/OpenAI dependencies and a usable API key were not present in the execution environment | Could not verify live agent/HITL or publish true success and cost metrics | Added offline safety tests and 32 scenario definitions; live `--live` remains to run |
| 2026-11-18 | GitHub host could not be resolved from the sandbox shell | Direct `git push` failed | Documented safe local merge-and-push workflow |

## Lessons

Mark task completion only when runnable functionality is merged and tested. Keep scope of sandbox writes narrow, make approval mandatory, and measure actual rather than hypothetical model performance.
