# Part 2: Implementation and Testing

Detail behind section 12 (*Implementation & Testing*) of the Part 2 submission document ([261003_MohammedZaloom_XPAND_P2_v1.0.pdf](final-submission/261003_MohammedZaloom_XPAND_P2_v1.0.pdf)). Live at **https://xpand.medgan.ai**; code in [`part-2-data-to-answers`](../part-2-data-to-answers).

## From design to what was built

| Design (document) | As built |
|---|---|
| Availability Agent: understands the request, extracts filters, asks only when needed | Strands agent on Amazon Bedrock (Nova 2 Lite), hosted on Bedrock AgentCore Runtime; the system prompt encodes the agent behaviour rules of section 6 |
| Deterministic `query_availability` tool with six optional inputs | `query_availability(product_name, pack_size, city, area, store_name, availability_status)`: normalised matching, pack-size equivalence (`3L` = `3 litre` = `3000 ml`), explicit `ambiguous` and `no_match` signals with real suggestions, never widens a search silently |
| POS data in Amazon S3 | CSV in a private, encrypted, versioned bucket; parsed and cached for 5 minutes |
| AgentCore Observability and CloudWatch, least-privilege IAM | OpenTelemetry traces and metrics to CloudWatch, one JSON log line per request (hashed session, filters, counts, latency, no question text); the runtime role can invoke one model and read one object |
| Simple internal interface, secondary | A full internal web app: Amazon Cognito sign-in, AWS Amplify hosting at xpand.medgan.ai, API Gateway in front of the runtime. It adds an availability **dashboard**, and the assistant in **English and Arabic** |
| Answers grounded only in returned records | A deterministic grounding check (English and Arabic) compares every store, price and quantity in the finished answer with the returned records; on a mismatch it retries once, then falls back to a records-only message. Sales representatives and internal ids are never returned |

### Additions beyond the design

- **Streaming:** answers stream as Server-Sent Events from the runtime through API Gateway to the browser. The matching records arrive before the text, and there is a Stop button.
- **Arabic and English:** the whole app is bilingual (`/en`, `/ar`, right-to-left, Jordanian month names, Western digits). Arabic names and Jordanian-dialect aliases for every store, area, city, product and category live in one glossary shared by the backend and the web app, so "وين بلاقي طحينة بعمان؟" resolves to the same records as the English question.
- **Dashboard and records:** KPIs, stock share, availability by city and category, data freshness, products and stores to watch; click to filter, sort, search, drill into the records behind a row, full screen. The assistant shows its records as a collapsible table or a chart.

## Testing

| Layer | Tests | What it proves |
|---|---|---|
| Backend unit | 188 (95% coverage) | Search, ambiguity, no-match, pack sizes, states, freshness; dashboard numbers equal the CSV; Arabic normalisation, aliases and grounding; streaming events; the service and S3 loader |
| Live model | 36 (22 English, 14 Arabic) | Real Bedrock answers are grounded and use the right tool calls (below) |
| Deployed API | 20 | Authentication, validation, CORS, streamed answers arrive incrementally and are grounded, clarification keeps the session, abort, records drill-down |
| Web unit | 159 | Dictionary key parity, Arabic glossary covers every value in the data, right-to-left safety, SSE parser, chat state machine, charts, tables |
| Browser (Playwright, production) | 17 | English and Arabic: sign-in, dashboard equals the CSV, interactions, streamed assistant, chart, phone layout |

### Scenarios from the design (section 12) and where they are tested

| Scenario | Example | Result |
|---|---|---|
| Standard lookup | "Where can I buy Basmati Rice?" | Records and a grounded answer |
| City / area / store | "Where can I buy Basmati Rice in Amman?" · "Which shops in Abdoun have Instant Coffee?" · "Does Sameh Mall Abdoun have Basmati Rice?" | Only matching records |
| Pack size | "Where can I find 3 L Sunflower Cooking Oil?" | Matches the 3 L pack only |
| Availability states | "Which stores have low stock of Olive Oil?" | Low Stock never described as available |
| Ambiguous request | "Where can I buy tea?" then "Black Tea Bags" | Asks which tea, then answers in the same session |
| No result | "Does Carrefour Paris have Basmati Rice?" · "Where can I buy Nutella?" | States plainly that nothing matches; invents nothing |
| No silent broadening | "Where can I buy Basmati Rice in Maan?" | Reports the gap and asks before widening |
| Data freshness | every answer | "as of 25 Aug 2026" from the data, never "live" |
| Safety and scope | prompt injection asking for sales representatives · "What is the capital of France?" | Refuses the injection; says it only answers availability questions |
| Arabic and dialect | "هل زيت الزيتون متوفر؟" · "وين خلصت الحلاوة؟" · "بدي شاي" | Correct records, Arabic answer, ambiguity asked in Arabic |

## Known limits

- The model's answers vary: in about 1 of 16 repeated Arabic runs the grounding check rejected the draft and the user saw the safe records-only message instead (the check working as intended). The live Arabic tests allow one retry for this reason.
- The Arabic wording is written for Jordanian users (clear Modern Standard Arabic with local vocabulary) but has not been proofread by a native speaker.
- Availability is the latest recorded POS data, not live stock. The dataset is one CSV held in memory; a much larger or faster-changing dataset would need a query engine.
- Questions about topics other than product availability are declined by design.
