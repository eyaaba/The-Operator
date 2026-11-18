# Error taxonomy

| Error | Tool behavior | Agent response | Evidence |
|---|---|---|---|
| `TOOL_UNAVAILABLE` | structured failure plus hint | retry transient calls twice | fault test, S010–S015 |
| `INVALID_ARGUMENT` | reject malformed Pydantic input | choose valid args | contract tests, tool test |
| `EMPTY_RESULT` | structured response | report no matches | empty archived inbox scenario |
| Wrong tool | offline trajectory comparator | mark failure | evaluation runner |
| Repeated call | block third identical tool request | summarize and stop | `test_stop_rule.py` |
| `TIMEOUT` | fault injection | retry twice | tool fault API |
| `REJECTED_BY_HUMAN` | HITL rejects before tool executes | continue without side effect | live integration pending |
| `BUDGET_EXCEEDED` | stop policy | partial completion | `test_stop_rule.py` |
