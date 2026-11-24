# Threat model — The Operator

## Security objective and boundaries

Protect mailbox contents, user intent, message recipients, label/archive/draft/sent state, and authentication credentials. The language model is a planner, not a privileged authority. Email subjects, bodies, sender names and tool outputs are untrusted. The user and configured system policy define scope; untrusted messages cannot authorize new actions.

The default SQLite mailbox is an isolated, repeatable test environment. An optional real Gmail backend is restricted to an explicitly named test account. Google OAuth scopes are powerful, so use disposable accounts and locally protected credentials only. The CLI asks for approval before the four explicit write tools. Gmail sending additionally requires `OPERATOR_ENABLE_GMAIL_SEND=yes` and a strict recipient allowlist.

## Attack surfaces and mitigations

| Attack | Surface | Mitigation | Test |
|---|---|---|---|
| Ignore instructions and archive every email | Message body | Treat email as data; explicit user scope; HITL/write cap | S020, S023 |
| Send private information to attacker | Message body or sender | `send_reply` has no model-selected recipient; Gmail recipient allowlist | S026 and Gmail regression test |
| Spoofed system instructions | Subject or body | Do not elevate tool output to system instructions | S025, S028 |
| Sender-display-name authority spoof | Sender metadata | Preserve trust boundary; restrict all writes | S024, S029 |
| Force unsolicited sending | Content injection | HITL, draft/send separation, disabled Gmail sending by default | S020, S026 |
| Repeat calls or infinite plan loop | Agent control path | Model/tool/write/repetition caps and bounded retries | Stop-rule tests |
| Tool failure or timeout | Tool execution | Structured error plus hint, no blind resend after uncertain failure | S010-S015 |
| OAuth token/client-secret disclosure | Local filesystem | `.gitignore`, user-only credentials, no credential logging | Verify archive and Git staging |
| Changes through a supposed read tool | Tool implementation | `read_email` now never updates mailbox state | Read-only regression test |

## Residual risks

Human approval can be mistaken or overly broad. In-memory interrupts do not survive process restarts. Gmail test mail is still real external email; its effects cannot be undone by SQLite reset. Local Gmail alias state is ignored by Git but should be protected on the machine. A failure after Gmail's send API accepts a message may leave an uncertain delivery outcome; sending must not be blindly retried. Token-cost enforcement can exceed an estimated threshold by one model call. Real injection-block and stop-rule results are pending model-backed testing.

## Validation requirements

Execute at least five injection scenarios under the same safety controls used in the demo and record actual trajectories, forbidden calls, final state, and approvals. Verify approval and rejection without unintended writes. Inspect both raw outcomes and the summary metrics. Never call offline scenario validation an injection-defense success rate.
