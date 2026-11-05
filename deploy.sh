#!/usr/bin/env bash
# Despliega el stack con CDK -> CloudFormation usando las credenciales de .env
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: falta el archivo .env (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)" >&2
  exit 1
fi

set -a; source .env; set +a
export AWS_DEFAULT_REGION="$AWS_REGION"
export CDK_DEFAULT_REGION="$AWS_REGION"

# Entorno virtual de Python con aws-cdk-lib
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# Se usa SIEMPRE el Python del entorno virtual (no el del sistema)
VENV_PY=".venv/bin/python"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r requirements.txt
"$VENV_PY" -c "import aws_cdk, constructs, dotenv" \
  || { echo "ERROR: dependencias no instaladas en .venv" >&2; exit 1; }
echo ">> Python usado por CDK: $("$VENV_PY" -c 'import sys;print(sys.executable)')"

# --app fuerza a CDK a ejecutar cdk_app.py con el Python de .venv
cdk() { npx --yes aws-cdk@2 --app "$VENV_PY cdk_app.py" "$@"; }

echo ">> Bootstrap de CDK en la region $AWS_REGION (solo crea recursos la primera vez)"
cdk bootstrap

echo ">> Desplegando StockMarketStack"
cdk deploy StockMarketStack --require-approval never --outputs-file cdk-outputs.json

echo
echo ">> Listo. La instancia tarda ~3-5 minutos en instalar Docker y construir la imagen."
echo ">> URL del servicio:"
"$VENV_PY" -c "import json;print(json.load(open('cdk-outputs.json'))['StockMarketStack']['ServiceUrl'])"
