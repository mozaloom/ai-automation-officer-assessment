# AI & Automation Officer Assessment

Take-home assignment with two independent scenarios. **Live demo of Part 2: https://xpand.medgan.ai**

| Part | Scenario | What is here |
|---|---|---|
| 1 | [**From Inbox to Board**](part-1-email-to-clickup) | A design (documents and diagrams, no code) for turning work-request emails into ClickUp tasks with an AI agent, including when a human should review first |
| 2 | [**Answering from the Data**](part-2-data-to-answers) | A working, deployed app that lets marketing answer "where can I buy this?" in seconds: an authenticated bilingual (English/Arabic) dashboard and a streaming assistant over the POS data |

## At a glance

**Part 1.** An Inbox Reviewer Agent (Strands on Amazon Bedrock AgentCore, MCP tools for ClickUp and Outlook) picks one of five actions per email: create a task, update a task, reply, ignore, or send to a person. Clear cases run automatically; ambiguity, missing information, possible duplicates and sensitive actions go to human review. Duplicates are prevented by message-ID idempotency in DynamoDB. A rule-based approach was considered and rejected.

**Part 2.** API Gateway (Cognito-protected) → Bedrock AgentCore Runtime → Strands agent → `query_availability` (deterministic) → POS data in S3, with the web app on AWS Amplify. The model interprets and writes; the tool retrieves; a deterministic check makes sure every store, price and quantity in an answer comes from the returned records. Answers stream, work in English, Modern Standard Arabic and Jordanian dialect, and show the matching records as a table or chart.

![Part 2 dashboard](docs/screenshots/en-dashboard.png)

## Repository map

```
├── part-1-email-to-clickup/    design: README, architecture diagram (draw.io, PNG, SVG, PDF) and guide
├── part-2-data-to-answers/     implementation: src/ (agent, tools, web app), tests/, infrastructure/ (AWS CDK), architecture/
└── docs/
    ├── final-submission/       the two submission documents (.docx)
    ├── architecture/           workflow and architecture figures for both parts
    ├── screenshots/            the Part 2 app in English and Arabic
    └── part-2-implementation-and-testing.md
```

## Run Part 2

See [part-2-data-to-answers/README.md](part-2-data-to-answers/README.md) for setup, configuration, the API, deployment and tests. In short: `make install && make test` runs the unit tests with no AWS access; `make deploy` builds and deploys everything with the CDK.

The live site needs a sign-in. Sign-up is disabled; the demo user is created by `infrastructure/scripts/create_demo_user.sh` and its credentials are shared with the reviewers directly rather than stored in the repository.

## License

MIT, see [LICENSE](LICENSE).
