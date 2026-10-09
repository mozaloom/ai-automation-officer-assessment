# Part 1 – AWS Architecture: Inbox Reviewer (as built)

Diagram: `part-1-aws-architecture.drawio` (exports: `.drawio.png`, `.drawio.svg`, `.drawio.pdf`)

Incoming work-request emails are read from the `xpand@medgan.ai` mailbox (Microsoft Graph, or the labelled sample mailbox until Graph is connected). A Strands agent on Amazon Bedrock AgentCore proposes one of five actions; a deterministic backend validates it, applies policy, and either executes it in ClickUp or queues it for a person to approve, edit or reject. It runs in the same AWS stack and application as Part 2.

## Flow

1. **Sign-in:** a reviewer signs in at https://xpand.medgan.ai (Amazon Cognito) and opens **Inbox Automation**. Only members of the Cognito group `inbox-reviewers` may use the `/inbox/*` API.
2. **Sync:** **Sync inbox** calls `POST /inbox/sync` on the existing API Gateway. It answers 202 immediately (API Gateway allows 29 seconds) and the `inbox-api` Lambda invokes itself asynchronously to process the mailbox.
3. **Idempotent claim:** for each email the Lambda makes a conditional write in DynamoDB keyed by the message ID. If the message is already known (second sync, webhook retry, a concurrent worker) it is recorded as a duplicate delivery and nothing is redone. A worker that died is taken over only after its lease expires.
4. **Triage:** the Lambda sends the email and a small context (real ClickUp members, list statuses, task names) to the **AgentCore Runtime** `inbox_reviewer_agent` (IAM/SigV4). The Strands agent (Nova 2 Lite) may call **read-only** tools through the **AgentCore Gateway** (MCP): `clickup_search_tasks` and `clickup_get_task`, served by the `inbox-tools` Lambda. It returns a structured `Triage` proposal.
5. **Deterministic checks:** the backend validates the proposal against a schema, maps the assignee, status, priority and due date to **real ClickUp values** (never guessing), searches ClickUp for similar tasks, and applies the policy.
6. **Route:** clear, low-risk proposals run automatically; everything else becomes a review item.
7. **Execute:** the backend (not the model) creates or updates the ClickUp task, or sends an approved reply. Task creation first looks for its own `[email:<id>]` marker so a retry after a lost answer never creates a second task.
8. **Review:** the reviewer sees the email, the proposal, the real field values and similar tasks, and chooses Approve, Edit (or Decide, for an item the agent could not decide) or Reject. The approval gate is a conditional DynamoDB write, so it can only succeed once.
9. **Audit:** every step is an audit item (who, what, outcome, task id), shown in the **Activity** page. Email text is never copied into the audit trail.

## Services

| Service | Purpose |
|---|---|
| AWS Amplify, Amazon Cognito, Amazon API Gateway | Reused from Part 2: hosting, sign-in (with the `inbox-reviewers` group), the `/inbox/*` routes |
| AWS Lambda `xpand-inbox-api` | Sync worker, orchestration, policy, approvals, execution |
| AWS Lambda `xpand-inbox-tools` | The two read-only ClickUp tools; no mailbox access |
| Amazon Bedrock AgentCore Runtime `inbox_reviewer_agent` | Hosts the Strands agent (IAM inbound; a second runtime because Part 2's is JWT-only) |
| Amazon Bedrock AgentCore Gateway | The MCP boundary between the agent and the tools |
| Amazon Bedrock (Nova 2 Lite) | Language understanding and the structured proposal |
| Amazon DynamoDB `xpand-inbox-state` | Message state, leases, proposals and the audit trail |
| AWS Secrets Manager | ClickUp token and Graph refresh token (created by the setup scripts, not by CDK) |
| Amazon CloudWatch and AgentCore Observability | Logs (30 days) and traces |
| ClickUp, Microsoft Outlook (Graph) | External systems: ClickUp is the system of record for tasks |

## Key design decisions

- **The model proposes; the backend decides.** Policy, duplicate detection, authorization and approval state are deterministic code, never an LLM.
- **Read-only tools for the model.** The design document had the agent execute create/update/reply through MCP. As built, only reads go through the Gateway; every external write happens in the backend after policy and approval, so a prompt injected into an email cannot cause one.
- **Nothing is invented.** An unknown assignee, status or invalid date is reported, not guessed. The only default is the configured priority, labelled as a default.
- **Safe failure.** Reads and the proposal are retried (bounded); task creation and sending are not. Failed items keep their proposal and can be retried.
- **One stack.** The Part 1 resources are added to the existing stack with a single construct, and removed with it.
