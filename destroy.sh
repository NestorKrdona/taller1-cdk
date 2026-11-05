#!/usr/bin/env bash
# MUY IMPORTANTE: elimina todos los recursos para que AWS no cobre de mas
set -euo pipefail
cd "$(dirname "$0")"

set -a; source .env; set +a
export AWS_DEFAULT_REGION="$AWS_REGION"
export CDK_DEFAULT_REGION="$AWS_REGION"

npx --yes aws-cdk@2 --app ".venv/bin/python cdk_app.py" destroy StockMarketStack --force
rm -f cdk-outputs.json
echo ">> Stack eliminado (EC2, VPC, Security Group y rol IAM)."
