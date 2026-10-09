# Demo script: from inbox to board (about 6 minutes)

Everything below runs on the live system at https://xpand.medgan.ai (sign in with the demo reviewer). Part 1 is **Inbox Automation** in the sidebar.
The same scenario is automated as `make test-demo` (in `part-1-email-to-clickup`), so you can show the test instead of typing emails.

## Before you start
- Inbox page shows the mailbox `xpand@medgan.ai`, the green **Live updates on** line, and no SAMPLE MODE banner.
- ClickUp list "Inbox Automation Tasks" is open in another tab.

## Walkthrough (each step maps to a test)
| # | You do | You see | Proven by |
|---|---|---|---|
| 1 | From any mail account send `xpand@medgan.ai`: "Please create a task: prepare the board slides. Assign it to Xpand Assessment, high priority, due <a date>. Description: ..." | Within seconds the email appears in **Inbox** with no click (webhook). The agent proposes **Create task** with real field values; assignee, priority and due date are only what the email says | `test_3` |
| 2 | Open the email: **Proposed action**, extracted fields, "No similar task found", **Open in Outlook** | Nothing was created without a reason: missing description means **Review queue** | unit scenarios 1, 8 |
| 3 | **Review queue** > **Approve** (or **Edit and approve**: the assignee list contains only real ClickUp members) | Status Done, **Open in ClickUp** link | `test_3` |
| 4 | In ClickUp: the task has assignee, priority, due date, and the list columns **Sender Email Address**, **Message Received Date**, **Source Message Link** (opens the email) and **Inbox Action** | The columns are filled from the email, nothing is guessed | `test_3`, live test 1 |
| 5 | Send `xpand@medgan.ai`: "Can you confirm you received my message? A short reply is enough." | Proposal **Reply** in the Review queue; the reply text is shown; a **draft** now exists in the mailbox Drafts folder | `test_1` |
| 6 | **Approve** | The draft is sent and arrives; Drafts is empty again (no orphan); a second Approve is refused (409) | `test_1` |
| 7 | Send another confirm email, then **Reject** | The draft is deleted from Drafts, nothing is sent, the audit trail shows `draft_discarded` | `test_2` |
| 8 | Send "Thanks, FYI: the office is closed Monday" | **Ignored**, no task | live and unit scenario 2 |
| 9 | **Activity** | Every step with who, what and when | `test_2` |
| 10 | **Sync inbox** | "already known" for everything: repeated delivery creates nothing | `test_3`, unit scenario 5 |

## What is automatic and what needs a person
Automatic: ignore, and a create when the email gives title, description and a real assignee and no similar task exists. Always a person: any reply, anything ambiguous, sensitive or possibly duplicate, a missing assignee. The agent only proposes; the backend validates, decides and executes.

## Run the tests live
```
cd part-1-email-to-clickup
make test        # unit: mocks, moto (no credentials)
make test-live   # real Bedrock agent + real ClickUp list
make test-e2e    # deployed API: Cognito, DynamoDB, webhook, real mailbox sync
make test-demo   # the scenario above on the real mailbox (sends itself emails, cleans up after)
```
