#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Azure Environment Setup
# Reuses the existing Azure resources.

RESOURCE_GROUP="asd-release2-rg"
REGISTRY_NAME="asdr2registry140729394"
ENV_NAME="asd-r2-env-23332"
LOCATION="australiaeast"

echo "=== Release 2 Environment Setup ==="

echo "Checking Azure login..."
az account show --output none

echo "Checking resource group..."
az group show \
    --name "$RESOURCE_GROUP" \
    --output none

echo "Checking Azure Container Registry..."
az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

echo "Checking Container Apps environment..."
az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

echo "Checking deployment managed identity..."
az identity show \
    --name asd-r2-github-deploy \
    --resource-group "$RESOURCE_GROUP" \
    --output none

echo ""
echo "Resource group: $RESOURCE_GROUP"
echo "Region: $LOCATION"
echo "Container Registry: $REGISTRY_NAME"
echo "Container Apps Environment: $ENV_NAME"

echo ""
echo "=== Existing Azure Environment Verified ==="