# Error taxonomy

| Error class | Agent/tool behavior | Evidence and verification |
|---|---|---|
| `INVALID_ARGUMENT` | Reject malformed or extra fields; return a repair hint | `test_contract.py`, `test_security_regression.py` |
| `NOT_FOUND` | Return a valid error and suggest listing current IDs | `test_tools.py`; inspect run trace for correct recovery |
| `EMPTY_RESULT` | Explain that there are no matching messages | `S017`; pending live run |
| `TOOL_UNAVAILABLE` | Structured failure, bounded retry on non-send operations | `test_tools.py`, `S010-S015`; pending live recovery metrics |
| `TIMEOUT` | Structured simulated failure, bounded retry where safe | Tool fault injection; pending end-to-end check |
| Wrong tool / arguments | Scenario must fail if forbidden or unauthorized action is performed | `test_security_regression.py`, trajectory scorer |
| Repeated tool request | Block after configured repetition threshold | `test_stop_rule.py`; check complete live termination |
| `REJECTED_BY_HUMAN` | Rejected write must not mutate mailbox | HITL configured; live approve/reject integration pending |
| `BUDGET_EXCEEDED` | Stop further tool/model operations; report partial outcome | `test_stop_rule.py`, cost regression test; live budget check pending |
| User changes mind | Reject writes or abandon the operation safely | CLI rejection policy; live evidence pending |

A scenario YAML file is a planned experiment, not evidence of successful recovery. Attach actual evaluation traces and resulting metrics before final submission.
