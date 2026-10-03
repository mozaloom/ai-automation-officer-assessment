# Part 1 – AWS Architecture: AI-Powered Email-to-ClickUp Automation (v2)

Diagram: `part-1-aws-architecture-v2.drawio` (export: `part-1-aws-architecture-v2.drawio.png`)

Incoming Outlook work-request emails are triaged by a Strands agent running on Amazon Bedrock AgentCore. The agent decides to create or update a ClickUp task, reply, ignore the email, or ask a human to review.

## Flow

1. **Webhook:** Microsoft Graph pushes a change notification for the mailbox to an Amazon API Gateway endpoint. API Gateway only receives the call; it never reads the mailbox.
2. **Ingestion:** API Gateway invokes an AWS Lambda function. Lambda validates the notification and fetches the full email (sender, subject, body, attachments, Message ID, thread context, timestamp).
3. **Idempotency:** Before processing, Lambda checks the Message ID in Amazon DynamoDB (Message ID / Idempotency / Processing State) and records it, so the same email never creates a duplicate task.
4. **Invoke:** Lambda invokes the Strands Inbox Reviewer Agent hosted on Bedrock AgentCore Runtime.
5. **Reason:** The agent calls Amazon Bedrock Nova 2 Lite to understand the email, classify intent, extract task details (urgency, assignee, due date), check for duplicates, and decide the next action.
6. **Act:** The agent returns one of `CREATE_TASK`, `UPDATE_TASK`, `REPLY`, `IGNORE`, `HUMAN_REVIEW`. The first three run as MCP tool calls through AgentCore Gateway:
   - ClickUp MCP: `search_tasks`, `create_task`, `update_task` → ClickUp
   - Outlook MCP: `reply_to_email` → Microsoft Outlook
7. **Exception path:** `HUMAN_REVIEW` triggers Strands native human-in-the-loop: the agent proposes an action, a human reviews it (approve / edit / reject), and the decision resumes the agent. The agent then calls AgentCore Gateway; the human review step never executes MCP actions itself. It is used only for ambiguous requests, missing critical information, possible duplicates, sensitive or higher-risk actions, and unclear assignee or scope.
8. **Admin portal (optional):** A reviewer signs in with Amazon Cognito, uses a web app hosted on AWS Amplify, and approves, edits or rejects through API Gateway. The core agent does not depend on it.
9. **Observability:** AgentCore Observability exports agent traces, LLM and tool calls, MCP interactions, errors, latency and logs to Amazon CloudWatch.

## Services

| Service | Purpose |
|---|---|
| Amazon API Gateway | Receives the Microsoft Graph webhook; also fronts the admin portal APIs |
| AWS Lambda | Validates notifications, fetches the email, de-duplicates, invokes the agent |
| Amazon DynamoDB | Message ID / idempotency / processing state, checked by Lambda before processing (not the business database) |
| Bedrock AgentCore Runtime | Managed, serverless runtime that hosts the Strands agent |
| Strands Agents | Agent framework (code), distinct from the runtime that hosts it |
| Amazon Bedrock Nova 2 Lite | Cost-efficient LLM for routine classification, extraction and business-process reasoning |
| Bedrock AgentCore Gateway | Centralized, managed access to MCP tools |
| ClickUp MCP / Outlook MCP | MCP tool servers that separate agent reasoning from external integrations |
| Amazon Cognito, AWS Amplify | Admin portal sign-in and hosting (optional) |
| Bedrock AgentCore Observability, CloudWatch | Traces, metrics and logs |
| AWS IAM, KMS, WAF | Least-privilege access, encryption, protection of exposed endpoints |

## Key design decisions

- AI handles routine decisions automatically; humans review only ambiguity and risk.
- MCP separates agent reasoning from integrations, and AgentCore Gateway gives one controlled place to expose tools.
- DynamoDB provides idempotency and application state only.
- Serverless and managed AWS services are used where practical, sized for a proof of concept.
- Observability and security are cross-cutting layers; the diagram omits their arrows to stay readable.
