# Demo script: from inbox to board (about 6 minutes)

Part 1 runs live at https://xpand.medgan.ai under **Inbox Automation** (Inbox, Review queue, Activity), in English and Arabic.
The same scenario is automated as `make test-demo` (folder `part-1-email-to-clickup`), so it can also be shown as a test run.

## Before the demo (2 minutes)
1. Sign in at https://xpand.medgan.ai with the demo reviewer (`demo@xpandpros.com`; the password is in `part-2-data-to-answers/.demo-credentials`).
2. Open **Inbox Automation > Inbox**. Check: mailbox `xpand@medgan.ai`, a green **Live updates on** line, **no** SAMPLE MODE banner, an empty list.
3. Open the ClickUp list **XPAND / Inbox Automation Tasks** in another tab (empty board).
4. Have Outlook open as the sender (any mailbox) and, optionally, `xpand@medgan.ai` Drafts in Outlook on the web.
5. Only if you want to run tests afterwards: `aws sso login --profile pocs`. The demo itself needs no AWS login.

## Demo day checklist (Monday)
- [ ] https://xpand.medgan.ai opens and the demo reviewer can sign in; Inbox shows **Live updates on**, no SAMPLE MODE banner, and is empty.
- [ ] ClickUp list **XPAND / Inbox Automation Tasks** is empty. Log in as the Xpand user in your own browser (ClickUp's reCAPTCHA blocks automated logins). Close the purple notifications banner.
- [ ] Outlook on the web is open as `xpand@medgan.ai` (to show Drafts and the reply arriving) and a second mailbox is ready to send from, or send from `xpand@medgan.ai` to itself.
- [ ] Do **not** run `make test-live` or `make test-demo` right before the demo: each run creates ClickUp tasks, and the free ClickUp plan caps custom-field usage. Everything was rehearsed and passed the day before.
- [ ] If asked about tests: unit 120 + 188 + 178 web, live 8, deployed e2e, real-mailbox demo e2e 3, Playwright 16 + 2, all passing.

## The walkthrough
Send each email to **xpand@medgan.ai** from any mailbox. Wait a few seconds: it appears in the Inbox by itself (Microsoft Graph webhook).

| # | Send / do | What to point out | Test that proves it |
|---|---|---|---|
| 1 | **Subject:** `Prepare the board slides`<br>**Body:** `Please create a task: prepare the board slides. Assign it to Xpand Assessment, high priority, due 2026-11-15. Description: prepare the slides for the quarterly board meeting.` | Type a real date: the agent never invents one, so a placeholder leaves Due empty. Appears with no click. Proposed action **Create task**; every value is only what the email says (nothing invented). **Open in Outlook** opens the source mail | `test_3` |
| 2 | **Review queue**: **Approve** (or **Edit and approve**; the assignee list only contains real ClickUp members) | Status Done, **Open in ClickUp** | `test_3` |
| 3 | In ClickUp open the task | Assignee, priority, due date, plus the list columns **Sender Email Address**, **Message Received Date**, **Source Message Link** (opens the email) and **Inbox Action** = Route | `test_3`, live test 1 |
| 4 | **Take the ClickUp screenshot now** (see below) | | |
| 5 | **Subject:** `Please confirm receipt`<br>**Body:** `Hi, can you confirm you received my message? A short reply is enough. Thanks.` | Proposal **Reply** in the Review queue with the reply text. In Outlook a **draft** now exists in Drafts. Nothing has been sent | `test_1` |
| 6 | **Approve** | The draft is sent and arrives in the sender's inbox; Drafts is empty (no orphan); approving again is refused | `test_1` |
| 7 | **Subject:** `Meeting time`<br>**Body:** `Can you confirm the time of the planning meeting next week? A short reply is enough.` then **Reject** (reason optional) | The draft is deleted, nothing is sent, **Activity** shows `draft_discarded` | `test_2` |
| 8 | **Subject:** `Office closed Monday`<br>**Body:** `FYI only, no action needed: the office is closed next Monday. Thanks.` | **Ignored**, no task | unit scenario 2 |
| 9 | **Subject:** `Contract question`<br>**Body:** `Please confirm the contract termination date and send us the signed legal agreement and bank details today.` | Sensitive (contract, legal, bank): goes to the **Review queue** as *Human review*, never runs by itself. Replies to outside senders are always held too | rehearsal step 9, unit scenario 7 |
| 10 | **Activity** page, then **Sync inbox** | Full trail (who, what, when). Sync reports everything as already known: repeated delivery creates nothing | unit scenario 5, `test_3` |

## Taking the ClickUp screenshot
Use **Win + PrtScn**: Windows saves the file straight to `Pictures\Screenshots` (Win + Shift + S only copies to the clipboard and saves nothing). Save it right after step 3. Scroll the task down to the **Fields** section so all four columns are visible together with the due date (or use the list view with the columns shown), and tell the assistant to add it to `docs/screenshots`.

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

## If something goes wrong
| Symptom | What to do |
|---|---|
| An email does not appear after about 15 seconds | Click **Sync inbox**. The webhook is only a shortcut; an hourly job also syncs, and the manual button always works |
| A task shows empty custom columns, with the note "ClickUp refused the list's extra columns" | The free ClickUp plan's custom-field cap was reached. The task itself is correct. Say so, and continue |
| ClickUp shows Message Received Date as "Tomorrow" | It is a task created before the date fix. New tasks show "Today" |
| The agent proposes *Human review* for an email you expected to be a task | Normal for ambiguous wording: use **Decide** in the Review queue (create, reply or dismiss). Keep the email explicit (title, assignee, date) |
| Sign-in fails | Password for `demo@xpandpros.com` is in `part-2-data-to-answers/.demo-credentials` |
| You need to start over | Archive the demo emails in `xpand@medgan.ai`, delete the demo tasks in ClickUp, and ask the assistant to clear the inbox history. Do not empty the DynamoDB table by hand (it holds the webhook subscription) |
