# Error taxonomy

Owner: Task 4.4. Every row needs a test that shows the behaviour.

| # | Class | How it shows up | What the agent does | Test |
|---|---|---|---|---|
| E1 | Tool down | `TOOL_UNAVAILABLE` | Retry up to 2×, then report partial progress and `finish` | _todo_ |
| E2 | Bad arguments | `INVALID_ARGUMENT` (schema) | Read the hint, fix the arguments, try once more | _todo_ |
| E3 | Empty result | `EMPTY_RESULT` | Tell the user nothing matched; do not invent emails | _todo_ |
| E4 | Wrong tool | Trajectory eval flags it | (measured, not handled at runtime) | _todo_ |
| E5 | Loop | Same call repeated > 2 | Repeated-call guard stops the run | _todo_ |
| E6 | Timeout | `TIMEOUT` | Same as E1 | _todo_ |
| E7 | User changes mind | `REJECTED_BY_HUMAN` | Do not retry the same write; continue or `finish` | _todo_ |

## Recovery after failure

_Fill in from eval: of the scenarios with one injected fault, % that still finished the task._
