#!/usr/bin/env bash
# Store (or rotate) the ClickUp credentials for the Inbox Reviewer in AWS Secrets Manager. The token is typed at a HIDDEN prompt:
# it never appears in the terminal, shell history, chat or git.
#   ClickUp: avatar (bottom-left) > Settings > Apps > API Token > Generate/Regenerate (starts with pk_).
#   List ID: open the list in ClickUp; the URL is https://app.clickup.com/<TEAM_ID>/v/li/<LIST_ID>.
set -euo pipefail
SECRET_ID="${CLICKUP_SECRET_ID:-xpand/inbox/clickup}"
read -r -s -p "ClickUp API token (hidden): " TOKEN; echo
read -r -p "Workspace (team) ID [${CLICKUP_TEAM_ID:-}]: " TEAM; TEAM="${TEAM:-${CLICKUP_TEAM_ID:-}}"
read -r -p "List ID [${CLICKUP_LIST_ID:-}]: " LIST; LIST="${LIST:-${CLICKUP_LIST_ID:-}}"
[ -n "$TOKEN" ] && [ -n "$TEAM" ] && [ -n "$LIST" ] || { echo "token, team ID and list ID are all required" >&2; exit 1; }
PAYLOAD="$(TOKEN="$TOKEN" TEAM="$TEAM" LIST="$LIST" python3 -c 'import json,os;print(json.dumps({"token":os.environ["TOKEN"],"team_id":os.environ["TEAM"],"list_id":os.environ["LIST"]}))')"
unset TOKEN
if aws secretsmanager describe-secret --secret-id "$SECRET_ID" >/dev/null 2>&1; then
  aws secretsmanager put-secret-value --secret-id "$SECRET_ID" --secret-string "$PAYLOAD" >/dev/null
else
  aws secretsmanager create-secret --name "$SECRET_ID" --description "ClickUp token and list for the Inbox Reviewer" --secret-string "$PAYLOAD" >/dev/null
fi
unset PAYLOAD
echo "stored in Secrets Manager: $SECRET_ID (token not shown). Test: python3 -m inbox.cli check-clickup"
