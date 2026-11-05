"""
Stack de CloudFormation (generado con CDK) para el Taller 01 - Despliegue de
Servicios de Red.

Recursos que crea:
  * VPC con una subred publica (sin NAT Gateway para no generar costos).
  * Security Group que solo permite HTTP (80) desde Internet. Sin SSH (22).
  * Rol IAM para la instancia: Session Manager (SSM) + lectura del codigo en S3.
  * Asset en S3 con la carpeta stock_app/ (Dockerfile + codigo Flask).
  * Instancia EC2 t3.micro con Ubuntu 24.04 cuyo user-data:
      1. Instala Docker (repositorio oficial de Docker para Ubuntu).
      2. Habilita al usuario 'ubuntu' para ejecutar contenedores.
      3. Descarga el codigo desde S3, construye la imagen y ejecuta el contenedor
         publicando el puerto 80 -> 5000.
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct

APP_DIR = Path(__file__).resolve().parent.parent / "stock_app"

UBUNTU_AMI_PARAM = (
    "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
)

IMAGE_TAG = "stock-market:2.0"
CONTAINER_NAME = "stock-market"
HOST_PORT = 80
CONTAINER_PORT = 5000


class StockMarketStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        instance_type: str = "t3.micro",
        default_stock: str = "GOOGL",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------- Red
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=1,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                )
            ],
        )

        sg = ec2.SecurityGroup(
            self,
            "WebSg",
            vpc=vpc,
            description="Permite HTTP desde Internet hacia el servicio stock-market",
            allow_all_outbound=True,
        )
        sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(HOST_PORT), "HTTP desde Internet"
        )

        # ---------------------------------------------------------- IAM / S3
        role = iam.Role(
            self,
            "InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
        )

        # Empaqueta stock_app/ en un .zip y lo sube al bucket de bootstrap de CDK
        app_asset = s3_assets.Asset(
            self,
            "StockAppSource",
            path=str(APP_DIR),
            exclude=["__pycache__", "*.pyc", ".venv", ".env"],
        )
        app_asset.grant_read(role)

        # --------------------------------------------------------- User data
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "set -euxo pipefail",
            "exec > >(tee -a /var/log/stock-market-setup.log) 2>&1",
            "export DEBIAN_FRONTEND=noninteractive",
            # --- 1. Instalar Docker (https://docs.docker.com/engine/install/ubuntu/)
            "apt-get update -y",
            "apt-get install -y ca-certificates curl unzip",
            "install -m 0755 -d /etc/apt/keyrings",
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc",
            "chmod a+r /etc/apt/keyrings/docker.asc",
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] '
            'https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" '
            "> /etc/apt/sources.list.d/docker.list",
            "apt-get update -y",
            "apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin",
            "systemctl enable --now docker",
            # --- 2. Habilitar al usuario 'ubuntu' para ejecutar contenedores
            "usermod -aG docker ubuntu",
            # --- 3. AWS CLI para descargar el codigo desde S3
            "snap install aws-cli --classic",
            # --- 4. Descargar codigo, construir imagen y ejecutar contenedor
            "mkdir -p /opt/stock-market",
            f"/snap/bin/aws s3 cp s3://{app_asset.s3_bucket_name}/{app_asset.s3_object_key} "
            f"/tmp/stock_app.zip --region {self.region}",
            "unzip -o /tmp/stock_app.zip -d /opt/stock-market",
            f"docker build -t {IMAGE_TAG} /opt/stock-market",
            f"docker rm -f {CONTAINER_NAME} || true",
            f"docker run -d --restart unless-stopped --name {CONTAINER_NAME} "
            f"-e STOCK={default_stock} -p {HOST_PORT}:{CONTAINER_PORT} {IMAGE_TAG}",
            "docker ps",
            "echo 'stock-market desplegado correctamente'",
        )

        # ---------------------------------------------------------- Instancia
        instance = ec2.Instance(
            self,
            "StockMarketInstance",
            instance_name="demo_docker",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_type=ec2.InstanceType(instance_type),
            machine_image=ec2.MachineImage.from_ssm_parameter(
                UBUNTU_AMI_PARAM, os=ec2.OperatingSystemType.LINUX
            ),
            security_group=sg,
            role=role,
            user_data=user_data,
            # Si cambia el codigo (hash del asset) se reemplaza la instancia
            user_data_causes_replacement=True,
            require_imdsv2=True,
            associate_public_ip_address=True,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        16,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        delete_on_termination=True,
                    ),
                )
            ],
        )
        Tags.of(self).add("Proyecto", "Taller01-ComputacionDistribuida")

        # ----------------------------------------------------------- Outputs
        CfnOutput(self, "InstanceId", value=instance.instance_id)
        CfnOutput(
            self,
            "PublicDnsName",
            value=instance.instance_public_dns_name,
        )
        CfnOutput(
            self,
            "ServiceUrl",
            value=f"http://{instance.instance_public_dns_name}",
            description="Abrir en el navegador (esperar ~3-5 min tras el deploy)",
        )
        CfnOutput(
            self,
            "SsmConnectCommand",
            value=f"aws ssm start-session --target {instance.instance_id} --region {self.region}",
            description="Conexion a la instancia sin SSH",
        )
