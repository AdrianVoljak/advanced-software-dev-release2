#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Validate existing Container Apps environment.
# Does not create or delete Azure resources.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"

echo "=== Release 2 Container Apps Environment ==="

az account show --output none

ENV_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" -o tsv)

if [[ -z "$ENV_NAME" || "$ENV_NAME" == "None" ]]; then
    echo "ERROR: Container Apps environment name missing."
    exit 1
fi

az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

echo "Environment: $ENV_NAME"
echo "Resource group: $RESOURCE_GROUP"

echo "=== Container Apps Environment Ready ==="
