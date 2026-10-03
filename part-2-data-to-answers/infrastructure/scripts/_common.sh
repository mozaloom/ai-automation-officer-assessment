# Shared by the deploy scripts. Sourced, not executed.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export AWS_PROFILE="${AWS_PROFILE:-pocs}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""
export CDK_DEFAULT_ACCOUNT="${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"
export CDK_DEFAULT_REGION="$AWS_REGION"
OUTPUTS="$ROOT/build/outputs.json"

# output <Name>: read a CloudFormation output written by `cdk deploy --outputs-file`.
output() {
  python3 -c "import json,sys;print(next(iter(json.load(open('$OUTPUTS')).values()))['$1'])"
}
