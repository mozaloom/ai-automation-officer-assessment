#!/usr/bin/env bash
# Full deployment: package the agent, deploy the stack, upload the data, create the demo user, publish the web app.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

"$ROOT/infrastructure/scripts/package_agent.sh"
"$ROOT/infrastructure/scripts/package_inbox.sh"
(cd "$ROOT/infrastructure" && cdk deploy --require-approval never --outputs-file "$OUTPUTS")

aws s3 cp "$ROOT/data/pos_availability.csv" "s3://$(output DataBucketName)/pos_availability.csv" --only-show-errors

# AgentCore creates the runtime log group on first use; make sure it exists and expires.
LOG_GROUP="/aws/bedrock-agentcore/runtimes/$(output RuntimeArn | sed 's:.*/::')-DEFAULT"
aws logs create-log-group --log-group-name "$LOG_GROUP" 2>/dev/null || true
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days 30

[ -f "$ROOT/.demo-credentials" ] || "$ROOT/infrastructure/scripts/create_demo_user.sh"
"$ROOT/infrastructure/scripts/deploy_web.sh"
echo "done. Run: make smoke"
