# Part 2 – AWS Architecture: Product Availability Agent

Diagram: `part-2-aws-architecture.drawio` (export: `part-2-aws-architecture.drawio.png`)

A marketing user asks a natural-language question about product availability. A Strands agent turns it into structured filters, a deterministic tool searches the POS availability data, and the agent answers using only the records returned.

## Flow

1. **Question:** The marketing user submits a question through a simple internal web UI hosted on AWS Amplify, for example "Where can I buy Olive Oil Extra Virgin in Amman?".
2. **API:** The UI calls Amazon API Gateway, which receives the request and forwards it to the agent runtime.
3. **Agent:** The Strands Availability Agent, hosted on Amazon Bedrock AgentCore Runtime, understands the request, extracts filters (product, pack size, city, area, store, availability), and decides whether to ask for clarification.
4. **Model:** The agent calls an Amazon Bedrock foundation model for language understanding, reasoning and response generation.
5. **Tool:** The agent calls `query_availability` with the structured filters. The tool is deterministic: it searches the dataset and returns matching records.
6. **Data:** The tool reads `pos_availability.csv` from Amazon S3.
7. **Response:** The agent writes the answer grounded in the returned records and sends it back through API Gateway to the user.

## Services

| Service | Purpose |
|---|---|
| AWS Amplify | Hosts the simple internal web UI where marketing submits questions |
| Amazon API Gateway | Internal API / demo interface: an access layer in front of the agent, not the core solution |
| Amazon Bedrock AgentCore Runtime | Managed runtime that hosts the Strands agent |
| Strands Agents | Agent framework: interpretation, filter extraction, clarification, tool calling |
| Amazon Bedrock (foundation model) | Natural-language understanding, reasoning and response generation |
| `query_availability` | Deterministic retrieval tool over the POS data |
| Amazon S3 (POS Availability Dataset) | Holds `pos_availability.csv`: structured POS availability data used by the query tool, the source of truth |
| AgentCore Observability, Amazon CloudWatch | Agent traces, tool calls, logs, errors and latency metrics |
| AWS IAM | Least-privilege permissions for the agent to access Bedrock and S3 |

## Key design decisions

- **LLM / agent = interpretation and reasoning.** The model decides what is being asked; it never looks up availability itself.
- **`query_availability` = deterministic retrieval.** The same filters always return the same records.
- **S3 POS data = source of truth.** The answer is grounded in the returned records.
- **Intentionally lean.** The data is structured tabular POS data, so there is no vector database, RAG pipeline, DynamoDB, Lambda, EventBridge, Cognito, VPC or MCP.
- **ERP ingestion is out of scope.** The POS data is already supplied to marketing from the ERP system, so the diagram shows the pipeline as a dashed box and does not implement it.
