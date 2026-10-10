# Part 1: Implementation and Testing

Detail behind the Part 1 submission document ([261002_MohammedZaloom_XPAND_P1_v1.0.pdf](final-submission/261002_MohammedZaloom_XPAND_P1_v1.0.pdf)). Part 1 was a design in the submission document; it is now also a working POC at **https://xpand.medgan.ai** (Inbox Automation), code in [`part-1-email-to-clickup`](../part-1-email-to-clickup). The Part 1 README is the operating guide; this note records how the build compares with the design and what was and was not verified.

## Design versus build

| Design (submission document) | As built |
|---|---|
| Five actions: `CREATE_TASK`, `UPDATE_TASK`, `REPLY`, `IGNORE`, `HUMAN_REVIEW` | Same five actions, schema-validated; an action without its payload degrades to `HUMAN_REVIEW` |
| Webhook to API Gateway, Lambda validates and fetches the email | Graph change notifications call a public API Gateway route (authenticated by clientState) that starts the asynchronous sync worker; an hourly EventBridge rule renews the subscription and runs a catch-up sync. Manual **Sync inbox** still works |
| DynamoDB message-ID idempotency | Conditional writes, explicit state machine, lease takeover, plus a marker in the ClickUp task so a retry adopts a half-finished create |
| Strands agent on AgentCore Runtime with Nova 2 Lite | Same, on a second IAM-authorized runtime |
| AgentCore Gateway MCP with ClickUp and Outlook tools, agent executes create/update/reply | Gateway with **read-only** ClickUp tools. Writes run only in the backend after policy and approval (a security decision: the model cannot reach an external write) |
| Strands native human-in-the-loop | Backend-enforced approval (Approve, Edit, Reject, and Decide for undecided items) with conditional state transitions. Chosen over in-agent pausing because approval must survive restarts and be auditable |
| Optional Cognito + Amplify reviewer portal | Built into the existing app: Inbox, Review queue, Activity, English and Arabic |
| Observability | Structured logs (redacted), audit trail in DynamoDB and the Activity page, AgentCore Observability and CloudWatch on the runtime |

## What was verified

**Real integrations:** ClickUp create, get, update and search on the real workspace (8 live tests, 4 deployed tests); the Bedrock agent; the deployed runtime over IAM auth; the gateway (tools listed as an MCP client, search called against the real list from AWS); real DynamoDB atomicity under 12 concurrent writers; Cognito authorization with a real non-reviewer user; the UI on production in English and Arabic.

**Mocked only:** Microsoft Graph (fake HTTP unit tests), ClickUp and Graph outages, and any real email send.

**Evidence:** screenshots of the real ClickUp list and tasks created by the agent are in `docs/screenshots/en-clickup-*.png` (see the Part 1 README).

## Problems found while testing

| Found by | Problem | Fix |
|---|---|---|
| Live test | The model returned `{}` for a list and a boolean; Strands re-asked forever (an unbounded loop) | Tolerant schema, `limits={"turns": 8}` on the agent, invalid output becomes a review item |
| Live test | ClickUp gives new tasks the list's first status (`blocked`) | Explicit, configured default status `to do` |
| Unit test | The resolver flagged a missing assignee on an update and applied create-time defaults to updates | Defaults apply only when creating |
| Moto | DynamoDB rejects redundant parentheses in the lease-takeover condition | Fixed the expression |
| Security review | The external-reply check used the model's `to` list instead of the real recipient | The check uses the sender |
| Security review | Read routes needed only a sign-in; the model had mailbox read and draft tools it did not need | Reviewer group on every route; the model has two read-only ClickUp tools only |
| Deployed test | The runtime returned HTTP 500 when the model could not produce a valid proposal | The runtime returns a clean "invalid" answer; the item goes to a person |
| Visual review | A reviewer could not act on an undecided item; empty notes showed as `{}`; Arabic bidi issues | Decide flow (create / reply / dismiss), sanitised notes, `dir="auto"` |

## Test counts

93 unit (2 skipped by design), 8 live, 4 deployed end-to-end; 175 web unit; 25 browser tests (8 for Inbox Automation). See the Part 1 README for the scenario table.
