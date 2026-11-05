#!/usr/bin/env python3
"""Punto de entrada de CDK: sintetiza el stack de CloudFormation."""

import os

import aws_cdk as cdk
from dotenv import load_dotenv

from infra.stock_market_stack import StockMarketStack

# Carga AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY y AWS_REGION desde .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

region = os.getenv("AWS_REGION") or os.getenv("CDK_DEFAULT_REGION") or "us-east-1"
account = os.getenv("CDK_DEFAULT_ACCOUNT")  # lo resuelve el CLI con las credenciales

app = cdk.App()

StockMarketStack(
    app,
    "StockMarketStack",
    env=cdk.Environment(account=account, region=region),
    instance_type=app.node.try_get_context("instanceType") or "t3.micro",
    default_stock=app.node.try_get_context("stock") or "GOOGL",
    description="Taller 01 - Servicio Flask stock-market en Docker sobre EC2 Ubuntu",
)

app.synth()
