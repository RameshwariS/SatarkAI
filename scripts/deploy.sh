#!/usr/bin/env bash
# One-command deploy. Needs: AWS CLI v2 + AWS SAM CLI, logged in (aws configure).
# Usage: ./scripts/deploy.sh [stack-name] [region]
set -euo pipefail
STACK="${1:-satark-ai}"
REGION="${2:-us-east-1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building and deploying backend ($STACK in $REGION)"
cd "$ROOT/backend"
sam build
sam deploy --stack-name "$STACK" --region "$REGION" --resolve-s3 \
  --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset

out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
BUCKET="$(out WebBucketName)"; DIST="$(out DistributionId)"; URL="$(out WebsiteUrl)"

echo "==> Uploading website to s3://$BUCKET"
aws s3 sync "$ROOT/frontend" "s3://$BUCKET" --delete --region "$REGION"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" >/dev/null

echo
echo "Live URL: $URL"
echo "Health check: $URL/api/health"
