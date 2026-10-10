# Demo script: from inbox to board (about 6 minutes)

Part 1 runs live at https://xpand.medgan.ai under **Inbox Automation** (Inbox, Review queue, Activity), in English and Arabic.
The same scenario is automated as `make test-demo` (folder `part-1-email-to-clickup`), so it can also be shown as a test run.

## Before the demo (2 minutes)
1. Sign in at https://xpand.medgan.ai with the demo reviewer (`demo@xpandpros.com`; the password is in `part-2-data-to-answers/.demo-credentials`).
2. Open **Inbox Automation > Inbox**. Check: mailbox `xpand@medgan.ai`, a green **Live updates on** line, **no** SAMPLE MODE banner, an empty list.
3. Open the ClickUp list **XPAND / Inbox Automation Tasks** in another tab (empty board).
4. Have Outlook open as the sender (any mailbox) and, optionally, `xpand@medgan.ai` Drafts in Outlook on the web.
5. Only if you want to run tests afterwards: `aws sso login --profile pocs`. The demo itself needs no AWS login.

## The walkthrough
Send each email to **xpand@medgan.ai** from any mailbox. Wait a few seconds: it appears in the Inbox by itself (Microsoft Graph webhook).

| # | Send / do | What to point out | Test that proves it |
|---|---|---|---|
| 1 | **Subject:** `Prepare the board slides`<br>**Body:** `Please create a task: prepare the board slides. Assign it to Xpand Assessment, high priority, due <a date next month>. Description: prepare the slides for the quarterly board meeting.` | Appears with no click. Proposed action **Create task**; every value is only what the email says (nothing invented). **Open in Outlook** opens the source mail | `test_3` |
| 2 | **Review queue**: **Approve** (or **Edit and approve**; the assignee list only contains real ClickUp members) | Status Done, **Open in ClickUp** | `test_3` |
| 3 | In ClickUp open the task | Assignee, priority, due date, plus the list columns **Sender Email Address**, **Message Received Date**, **Source Message Link** (opens the email) and **Inbox Action** = Route | `test_3`, live test 1 |
| 4 | **Take the ClickUp screenshot now** (see below) | | |
| 5 | **Subject:** `Please confirm receipt`<br>**Body:** `Hi, can you confirm you received my message? A short reply is enough. Thanks.` | Proposal **Reply** in the Review queue with the reply text. In Outlook a **draft** now exists in Drafts. Nothing has been sent | `test_1` |
| 6 | **Approve** | The draft is sent and arrives in the sender's inbox; Drafts is empty (no orphan); approving again is refused | `test_1` |
| 7 | **Subject:** `Meeting time`<br>**Body:** `Can you confirm the time of the planning meeting next week? A short reply is enough.` then **Reject** (reason optional) | The draft is deleted, nothing is sent, **Activity** shows `draft_discarded` | `test_2` |
| 8 | **Subject:** `Office closed Monday`<br>**Body:** `FYI only, no action needed: the office is closed next Monday. Thanks.` | **Ignored**, no task | unit scenario 2 |
| 9 | **Subject:** `Contract question`, from an outside address, **Body:** `Please confirm the contract termination date and send us the signed legal agreement.` | Sensitive and external: goes to **Review queue**, never runs by itself | unit scenario 7 |
| 10 | **Activity** page, then **Sync inbox** | Full trail (who, what, when). Sync reports everything as already known: repeated delivery creates nothing | unit scenario 5, `test_3` |

## Taking the ClickUp screenshot
Use **Win + PrtScn**: Windows saves the file straight to `Pictures\Screenshots` (Win + Shift + S only copies to the clipboard and saves nothing). Save it right after step 3, with the filled columns visible, and tell the assistant to add it to `docs/screenshots`.

## What is automatic and what needs a person
Automatic: ignore, and a create when the email gives a title, a description and a real assignee and nothing similar exists. Always a person: every reply, anything ambiguous, sensitive or possibly duplicate, a missing assignee. The agent only proposes; the backend validates, decides and executes.

## Reset between runs
Archive the demo emails in `xpand@medgan.ai` (so they are not read again), delete the demo tasks in ClickUp, and ask the assistant to clear the inbox history. Do not reset the DynamoDB table by hand: the webhook subscription record lives in it.

## Run the tests live
```
cd part-1-email-to-clickup
make test        # unit: mocks, moto (no credentials)
make test-live   # real Bedrock agent + real ClickUp list
make test-e2e    # deployed API: Cognito, DynamoDB, webhook, real mailbox sync
make test-demo   # the scenario above on the real mailbox (it emails itself and cleans up)
```
