#!/usr/bin/env bash
# Build the Next.js static export with the deployed settings and publish it to Amplify (manual deployment).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

APP_DIR="$ROOT/src/app"
APP_ID="$(output AmplifyAppId)"

export NEXT_PUBLIC_API_BASE_URL="$(output ApiUrl | sed 's:/*$::')"
export NEXT_PUBLIC_COGNITO_USER_POOL_ID="$(output UserPoolId)"
export NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID="$(output UserPoolClientId)"

echo "building the web app"
(cd "$APP_DIR" && npm ci --no-audit --no-fund --loglevel=error && npm run build)

rm -f "$ROOT/build/web.zip"
(cd "$APP_DIR/out" && zip -qr "$ROOT/build/web.zip" .)

read -r JOB_ID UPLOAD_URL < <(aws amplify create-deployment --app-id "$APP_ID" --branch-name main --query '[jobId,zipUploadUrl]' --output text)
curl -sf -X PUT -H "Content-Type: application/zip" --data-binary "@$ROOT/build/web.zip" "$UPLOAD_URL"
aws amplify start-deployment --app-id "$APP_ID" --branch-name main --job-id "$JOB_ID" >/dev/null

echo "deploying (job $JOB_ID)"
for _ in $(seq 1 60); do
  STATUS="$(aws amplify get-job --app-id "$APP_ID" --branch-name main --job-id "$JOB_ID" --query job.summary.status --output text)"
  case "$STATUS" in
    SUCCEED) echo "deployed: https://$(output AmplifyDefaultDomain) and $(output WebUrl)"; exit 0 ;;
    FAILED|CANCELLED) echo "deployment $STATUS" >&2; exit 1 ;;
  esac
  sleep 5
done
echo "timed out waiting for the deployment" >&2; exit 1
