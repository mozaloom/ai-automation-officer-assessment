# Part 2 – AWS Architecture: Product Availability Agent

Diagram: `part-2-aws-architecture.drawio` (exports: `.drawio.png`, `.drawio.svg`, `.drawio.pdf`)

A marketing user signs in to an internal web app, sees a POS availability dashboard, and asks the Availability Assistant natural-language questions. A Strands agent turns each question into structured filters, a deterministic tool searches the POS data, and the answer is grounded in the records returned.

## Flow

1. **Web app:** The user opens https://xpand.medgan.ai, a Next.js static site hosted on AWS Amplify, and signs in. The browser authenticates against an Amazon Cognito user pool (Secure Remote Password), so the password never leaves the browser.
2. **API:** The app calls Amazon API Gateway with the Cognito **ID token**. API Gateway validates it with a Cognito authorizer, checks the request shape, and applies throttling.
3. **Runtime:** API Gateway forwards the request over HTTPS to Amazon Bedrock AgentCore Runtime with the same token. The runtime validates the JWT again (inbound JWT authorizer) before any code runs.
4. **Dashboard:** `GET /dashboard` is answered by deterministic analytics over the POS data (no model call).
5. **Assistant:** `POST /ask` goes to the Strands Availability Agent, which understands the question, extracts filters (product, pack size, city, area, store, availability) and decides whether to ask for clarification.
6. **Model:** The agent calls an Amazon Bedrock foundation model (Nova 2 Lite) for understanding, reasoning and the written answer.
7. **Tool:** The agent calls `query_availability`, a deterministic function that searches the dataset and returns matching records, ambiguity signals or "no match" hints.
8. **Data:** The tool reads `pos_availability.csv` from Amazon S3. The ERP pipeline that produces this file is out of scope.
9. **Response:** A deterministic check verifies that every store, price and quantity in the answer appears in the returned records (one corrective retry, then a records-only fallback). The answer and the exact records go back to the user.

## Services

| Service | Purpose |
|---|---|
| AWS Amplify | Hosts the web UI at xpand.medgan.ai (static export, security headers, custom domain through the existing Route 53 hosted zone) |
| Amazon Cognito | User pool for sign-in (self sign-up disabled, demo user created by an administrator) |
| Amazon API Gateway | Internal API in front of the agent: Cognito authorizer, request validation, throttling, CORS |
| Amazon Bedrock AgentCore Runtime | Managed runtime that hosts the Strands agent and the dashboard analytics |
| Strands Agents | Agent framework: interpretation, filter extraction, clarification, tool calling |
| Amazon Bedrock (Nova 2 Lite) | Language understanding, reasoning and answer generation |
| `query_availability` | Deterministic retrieval tool over the POS data |
| Amazon S3 | Holds `pos_availability.csv`, the source of truth |
| AgentCore Observability, Amazon CloudWatch | Structured logs, traces (OpenTelemetry), metrics |
| AWS IAM | Least-privilege execution role: Bedrock model invocation and read of one S3 object |

## Key design decisions

- **LLM / agent = interpretation and reasoning.** The model decides what is asked; it never looks up availability itself.
- **`query_availability` = deterministic retrieval.** The same filters always return the same records.
- **S3 POS data = source of truth.** Answers are grounded in the returned records, and the UI shows those records next to the answer.
- **No Lambda.** API Gateway cannot call AgentCore through an AWS service integration, but a plain HTTPS integration that forwards the Cognito token works, and AgentCore validates the JWT itself.
- **Intentionally lean.** The data is structured tabular POS data, so there is no vector database, RAG pipeline, DynamoDB, Lambda, EventBridge, VPC or MCP.
- **ERP ingestion is out of scope.** The POS data is already supplied to marketing from the ERP system.
