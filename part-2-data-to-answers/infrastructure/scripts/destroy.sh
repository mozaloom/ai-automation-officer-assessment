#!/usr/bin/env bash
# Remove everything this project created. Asks first unless --yes is given.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

if [ "${1:-}" != "--yes" ]; then
  read -r -p "Delete the POS availability stack in account $CDK_DEFAULT_ACCOUNT ($AWS_PROFILE)? [y/N] " ANSWER
  [ "$ANSWER" = "y" ] || { echo "aborted"; exit 1; }
fi

BUCKET="$(output DataBucketName)"
RUNTIME_ID="$(output RuntimeArn | sed 's:.*/::')"

# The data bucket is versioned: delete every version and delete marker before the stack removes it.
python3 - "$BUCKET" <<'PY'
import sys, boto3
bucket = boto3.client("s3").list_object_versions
s3 = boto3.client("s3")
for page in s3.get_paginator("list_object_versions").paginate(Bucket=sys.argv[1]):
    items = [{"Key": o["Key"], "VersionId": o["VersionId"]} for o in page.get("Versions", []) + page.get("DeleteMarkers", [])]
    if items:
        s3.delete_objects(Bucket=sys.argv[1], Delete={"Objects": items})
PY

(cd "$ROOT/infrastructure" && cdk destroy --force)
aws logs delete-log-group --log-group-name "/aws/bedrock-agentcore/runtimes/${RUNTIME_ID}-DEFAULT" 2>/dev/null || true
rm -f "$ROOT/.demo-credentials" "$OUTPUTS"
echo "destroyed"
