# Taller 01 – Despliegue de Servicios de Red con AWS CDK

Solución del taller *Despliegue de Servicios de Red*. El script de Yahoo Finance
se expone como servicio web con **Flask**, se empaqueta con **Docker** y se
despliega en una **EC2 con Ubuntu 24.04**. La infraestructura se define con
**AWS CDK (Python)**, que genera y aplica una plantilla de **CloudFormation**.

## Arquitectura

```
 Equipo                              AWS (CloudFormation: StockMarketStack)
 ─────────                              ───────────────────────────────────────
 cdk deploy ──► stock_app/ (.zip) ──► S3 (bucket de bootstrap de CDK)
                                          │  (rol IAM: lectura)
                                          ▼
                    VPC pública ──► EC2 t3.micro Ubuntu 24.04 ("demo_docker")
                    SG: 80/tcp             user-data:
                                             1. instala Docker
                                             2. usuario ubuntu → grupo docker
                                             3. descarga código de S3
                                             4. docker build  stock-market:2.0
                                             5. docker run -p 80:5000
 Navegador ── http://<DNS público>/ ──────► contenedor Flask (gunicorn :5000)
                                                  └──► Yahoo Finance
```

* La imagen se **construye dentro de la EC2** (no hace falta Docker local ni Docker Hub).
* Sin SSH ni puerto 22: la administración es por **SSM Session Manager**.
* VPC sin NAT Gateway y volumen gp3 de 16 GB → dentro del free tier.

## Estructura

```
taller1-cdk/
├── .env                    # Credenciales AWS (NO subir a git)
├── requirements.txt        # Dependencias de CDK
├── cdk.json                # Configuración de CDK (tipo de instancia, stock)
├── cdk_app.py              # Punto de entrada de CDK
├── infra/
│   └── stock_market_stack.py   # Stack: VPC, SG, IAM, S3 asset, EC2 + user-data
├── stock_app/              # Contenedor
│   ├── Dockerfile
│   ├── requirements.txt    # flask, gunicorn, yfinance
│   ├── read_value_yf.py    # Script original del taller
│   └── app.py              # API Flask
├── deploy.sh               # bootstrap + deploy
└── destroy.sh              # elimina todo (¡MUY IMPORTANTE!)
```

## Requisitos

* Python 3.9+ y Node.js 18+ (CDK CLI se ejecuta con `npx`, no hace falta instalarlo).
* Un usuario IAM con permisos para CloudFormation, EC2, IAM, S3 y SSM
  (para el taller, `AdministratorAccess` es lo más sencillo).

## Preparar el ambiente de Python

Desde la carpeta `taller1-cdk/`, crear un entorno virtual e instalar las
dependencias de CDK (`aws-cdk-lib`, `constructs`, `python-dotenv`):

**macOS / Linux**

```bash
cd taller1-cdk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
cd taller1-cdk
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verificar la instalación:

```bash
pip show aws-cdk-lib | grep Version
python -c "import aws_cdk, constructs, dotenv; print('Dependencias OK')"
npx --yes aws-cdk@2 --version
```

Con el ambiente activo se puede usar CDK directamente (cargando antes el `.env`):

```bash
set -a; source .env; set +a      # exporta AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
npx aws-cdk@2 synth              # genera la plantilla de CloudFormation en cdk.out/
npx aws-cdk@2 bootstrap          # solo la primera vez por cuenta/región
npx aws-cdk@2 deploy             # despliega
```

Para salir del ambiente: `deactivate`.

> `cdk.json` ejecuta la app con `.venv/bin/python`, así CDK siempre usa el
> Python del entorno virtual aunque exista otro `python3` en el PATH
> (por ejemplo Homebrew). En **Windows**, cambiar esa línea a
> `"app": ".venv\\Scripts\\python cdk_app.py"`.

> **Opcional – ambiente de la app Flask** (para probarla sin Docker):
>
> ```bash
> cd stock_app
> python3 -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt
> python app.py                  # http://localhost:5000
> ```

> `deploy.sh` crea el ambiente `.venv` e instala `requirements.txt`
> automáticamente si no existe, así que este paso manual es opcional cuando
> se usa el script.

## Despliegue

1. Editar `.env` con las credenciales:

   ```
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=us-east-2
   ```

2. Ejecutar:

   ```bash
   ./deploy.sh
   ```

   El script crea el entorno virtual, instala `requirements.txt`, hace
   `cdk bootstrap` (solo la primera vez por cuenta/región) y `cdk deploy`.

3. Al final el script imprime la URL (`ServiceUrl`). Esperar **3–5 minutos**
   mientras la instancia instala Docker y construye la imagen, y luego abrirla
   en el navegador.

### Endpoints

| Ruta | Descripción |
|------|-------------|
| `/` | Datos de GOOGL desde 2020-01-01 (igual que el taller) |
| `/stock/AMZN` | Otro ticker |
| `/stock/AMZN?start=2024-01-01&end=2024-12-31` | Rango de fechas |
| `/health` | Chequeo de salud (JSON) |

Para cambiar el ticker por defecto: `npx aws-cdk@2 deploy -c stock=AMZN`
(con el `.env` cargado) o editar `cdk.json`.

## Verificar / depurar en la instancia

```bash
aws ssm start-session --target <InstanceId> --region <region>   # o desde la consola: "Connect" → Session Manager
sudo tail -f /var/log/stock-market-setup.log
docker ps
docker logs stock-market
```

## Pruebas locales (opcional, requiere Docker)

```bash
cd stock_app
docker image build -t stock-market:2.0 .
docker container run --rm --name stock-market -p 5000:5000 stock-market:2.0
# http://localhost:5000
```

## Eliminar recursos (MUY IMPORTANTE)

```bash
./destroy.sh
```

Equivale a "Terminate instance" del taller, pero borra todo el stack
(EC2, VPC, Security Group, rol IAM). El bucket de bootstrap de CDK se conserva
(costo despreciable); se puede borrar eliminando el stack `CDKToolkit` en
CloudFormation.

## Notas

* Si se cambia el código de `stock_app/` y se vuelve a desplegar, CDK detecta el
  cambio y **reemplaza la instancia** con la nueva versión.
* Yahoo Finance a veces limita peticiones desde IPs de nube. Si la página
  muestra "No se encontraron datos", esperar un momento y recargar.
