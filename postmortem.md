# Postmortem and implementation record

| Issue | Cause / impact | Resolution / verification status |
|---|---|---|
| Placeholder implementations in original `agent/tools.py` | Initial module was a scaffold, not a working tool layer | Implemented SQLite tools, schemas, idempotency and offline tests |
| Divergent Git history and README merge conflict | Local Task 1 commit and remote README updates diverged | Created a backup branch, resolved conflict and pushed history-preserving merge |
| `read_email` changed read state | Violated read-only/approval boundary | Removed `is_read` update and added regression test |
| Evaluator accepted extra write and incomplete state checks | Trajectory comparison only matched subsequences; database assertions were permissive | Added unauthorized-write checks and exact assertions for declared end-state fields |
| Cost policy was not connected to live model usage | Limits existed separately from agent middleware | Connected model usage tracking and cost-based further-action blocking; needs live validation |
| Agent's original live run failed | Exact environment error was not supplied in the project archive | Do not claim fixed; rerun with OpenAI credentials and capture traceback |
| Real Gmail requirement conflicts with deterministic test fixtures | External Gmail mailbox cannot be reset reliably between experiments | Added optional OAuth test-account backend while retaining SQLite for graded evaluation |
| No verified live metrics | No confirmed model-backed end-to-end execution | Report generator marks these as pending until measured |

## Lessons

Passing unit tests does not prove a safe tool-using agent. A supposedly read-only function must be audited for side effects. Approval should be checked where writes actually execute. The evaluator must penalize incorrect paths and state changes even when a final answer looks correct. Security and experiment results should reflect observed execution rather than design intent.

## Remaining release gates

Run a clean Windows install, verify `create_agent` invocation, approve/reject/edit Gmail test operations, run one sandbox scenario live, run the full 32-case evaluation, inspect cost and injection results, rebuild `report.pdf`, and commit the verified outputs and final documentation. Record any failures and corrective work before declaring the project complete.
