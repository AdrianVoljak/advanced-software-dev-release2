#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"

echo "=== Release 2 Image Build ==="

az account show --output none

REGISTRY_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" -o tsv)

if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" ]]; then
    echo "ERROR: Registry name missing from resource group tags."
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"

echo "Registry: $REGISTRY_NAME"
echo "Image tag: $IMAGE_TAG"

build_image() {
    local service="$1"
    local context="$2"
    local dockerfile="$3"

    echo ""
    echo "Building $service..."

    az acr build \
        --registry "$REGISTRY_NAME" \
        --image "${service}:${IMAGE_TAG}" \
        --file "$dockerfile" \
        "$context"

    echo "Completed: $service"
}

# Shared services
build_image "user-database" \
    "./shared/database" "Dockerfile"

build_image "auth-backend" \
    "./shared/backend" "Dockerfile"

build_image "portal-frontend" \
    "./shared/frontend" "Dockerfile"

# Assessment Tracker services
build_image "assessment-database" \
    "./student-adrianvoljak/database" "Dockerfile"

build_image "assessment-backend" \
    "./student-adrianvoljak" "backend/Dockerfile"

build_image "assessment-frontend" \
    "./student-adrianvoljak/frontend" "Dockerfile"

echo ""
echo "=== All Six Images Built Successfully ==="
echo "Image tag: $IMAGE_TAG"
