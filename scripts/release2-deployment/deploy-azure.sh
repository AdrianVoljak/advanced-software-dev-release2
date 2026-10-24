#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Deploy individual six-service application.
# Reuses existing Azure Container Apps, ACR and storage.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"

echo "=== Release 2 Azure Deployment ==="

az account show --output none

REGISTRY_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" -o tsv)

ENV_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" -o tsv)

REGISTRY_SERVER=$(az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query loginServer -o tsv)

echo "Resource group: $RESOURCE_GROUP"
echo "Environment: $ENV_NAME"
echo "Registry: $REGISTRY_SERVER"
echo "Image tag: $IMAGE_TAG"

# Verify all six existing Container Apps.
SERVICES=(
    user-database
    assessment-database
    auth-backend
    assessment-backend
    assessment-frontend
    portal-frontend
)

for service in "${SERVICES[@]}"; do
    az containerapp show \
        --name "$service" \
        --resource-group "$RESOURCE_GROUP" \
        --output none
done

# Retrieve internal ingress FQDNs.
get_url() {
    local fqdn
    fqdn=$(az containerapp show \
        --name "$1" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.configuration.ingress.fqdn \
        -o tsv)

    echo "https://${fqdn}"
}

USER_DATABASE_URL=$(get_url user-database)
ASSESSMENT_DATABASE_URL=$(get_url assessment-database)
AUTH_BACKEND_URL=$(get_url auth-backend)
ASSESSMENT_BACKEND_URL=$(get_url assessment-backend)
ASSESSMENT_FRONTEND_URL=$(get_url assessment-frontend)

# Update image and runtime configuration.
deploy_service() {
    local service="$1"
    shift

    echo ""
    echo "Deploying $service..."

    az containerapp update \
        --name "$service" \
        --resource-group "$RESOURCE_GROUP" \
        --image "${REGISTRY_SERVER}/${service}:${IMAGE_TAG}" \
        "$@" \
        --output none

    echo "Updated: $service"
}

# 1. Databases: retain existing Azure Files mounts.
deploy_service user-database

deploy_service assessment-database \
    --set-env-vars DATABASE_PORT=5008

# 2. Backends: connect to the internal databases.
deploy_service auth-backend \
    --set-env-vars \
        "DATABASE_SERVICE_URL=${USER_DATABASE_URL}"

deploy_service assessment-backend \
    --set-env-vars \
        "BACKEND_PORT=5007" \
        "DATABASE_SERVICE_URL=${ASSESSMENT_DATABASE_URL}" \
        "AI_ENABLED=false" \
        "MCP_ENABLED=false" \
        "RAG_ENABLED=false"

# 3. Assessment frontend.
deploy_service assessment-frontend

# 4. Public portal: route requests to internal services.
deploy_service portal-frontend \
    --set-env-vars \
        "AUTH_BACKEND_URL=${AUTH_BACKEND_URL}" \
        "ASSESSMENT_BACKEND_URL=${ASSESSMENT_BACKEND_URL}" \
        "ASSESSMENT_FRONTEND_URL=${ASSESSMENT_FRONTEND_URL}"

PORTAL_FQDN=$(az containerapp show \
    --name portal-frontend \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

echo ""
echo "=== Release 2 Azure Deployment Updated ==="
echo "Portal: https://${PORTAL_FQDN}"
echo "Image tag: $IMAGE_TAG"