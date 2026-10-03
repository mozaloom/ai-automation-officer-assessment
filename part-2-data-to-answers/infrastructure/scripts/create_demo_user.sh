#!/usr/bin/env bash
# Create (or reset) the demo Cognito user. The password is generated, written to the git-ignored
# .demo-credentials file and printed once. Never commit it.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POOL_ID="${USER_POOL_ID:-$(python3 -c "import json;print(json.load(open('$ROOT/build/outputs.json'))['PosAvailabilityStack']['UserPoolId'])")}"
EMAIL="${DEMO_EMAIL:-demo@xpandpros.com}"
PASSWORD="${DEMO_PASSWORD:-$(python3 -c "import secrets,string;a=string.ascii_letters+string.digits;print(''.join(secrets.choice(a) for _ in range(14))+'-Xp9!')")}"

if ! aws cognito-idp admin-get-user --user-pool-id "$POOL_ID" --username "$EMAIL" >/dev/null 2>&1; then
  aws cognito-idp admin-create-user --user-pool-id "$POOL_ID" --username "$EMAIL" \
    --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
    --message-action SUPPRESS >/dev/null
fi
aws cognito-idp admin-set-user-password --user-pool-id "$POOL_ID" --username "$EMAIL" --password "$PASSWORD" --permanent
umask 077
printf 'email=%s\npassword=%s\n' "$EMAIL" "$PASSWORD" > "$ROOT/.demo-credentials"
echo "demo user ready: $EMAIL (password saved to .demo-credentials)"
