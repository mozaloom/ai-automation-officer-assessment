# Part 2 follow-up: streaming + Arabic/English + UI de-slop

Plan: `~/.claude/plans/pasted-content-id-4dcb-implement-part-melodic-curry.md`
Branch: `feature/part2-ui-streaming-i18n` (the demo-user-email edits are carried uncommitted; commit them separately)

- [x] 0. Spike: Bearer accepted by the Cognito authorizer (done); streaming through API Gateway HTTP_PROXY (verify at first deploy)
- [x] 1. Backend streaming (`ask_stream`, event protocol, CORS middleware, tests)
- [x] 2. Backend Arabic (glossary, normalisation, prompt, grounding, tests, live set)
- [x] 3. (stack + e2e tests written; deploy waits for the web client) Infra: `/ask` HTTP_PROXY + STREAM, deploy, API e2e (SSE)
- [x] 4. (code written; vitest has 16 failing tests to fix) Web foundation: locale routing, dictionaries, Intl, RTL, fonts, toggle
- [x] 5. (code written, not yet visually inspected) UI redesign + web-design-guidelines audit
- [x] 6. (code written, tests failing) Streaming UI (parser, stop, progressive markdown)
- [x] 7. One batched inspection (desktop+mobile x en+ar), one fix batch, one confirm
- [x] 8. Deploy, production e2e, docs, Arabic review sheet

## Review
Done and deployed (xpand.medgan.ai): streaming assistant (SSE through API Gateway HTTP_PROXY + STREAM, verified incremental), Arabic/English UI at /en and /ar (RTL, Jordanian dates, glossary-backed names), Arabic and dialect search with Arabic-aware grounding, de-slopped UI (KPI strip, CSS bars, flat sections, URL filters).
Verified: pytest unit (coverage 95%), 36 live Bedrock tests (22 EN + 14 AR), 18 deployed-API tests, 127 vitest, eslint, tsc, next build, 13 Playwright tests on production (EN + AR, desktop + mobile).
Left: native Jordanian proofread of the Arabic copy (src/tools/glossary.json, lib/i18n/messages/ar.ts); README/architecture docs not yet updated for streaming and bilingual; nothing committed (demo-user edits are also uncommitted on this branch and should be a separate commit); mobile KPI scope line truncates ("12 c...").
