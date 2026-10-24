
#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Build and push six container images.
# Reuses the existing Azure Container Registry.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"

echo "=== Release 2 Image Build ==="

az account show --output none

# Retrieve the existing registry.
REGISTRY_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" -o tsv)

if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" ]]; then
    echo "ERROR: Registry name missing from resource group tags."
    exit 1
fi

REGISTRY_SERVER=$(az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query loginServer -o tsv)

# Ensure we're building from the repository root.
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Use the Git commit as the image version.
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"

echo "Registry: $REGISTRY_NAME"
echo "Image tag: $IMAGE_TAG"

# Authenticate Docker with the existing registry.
echo "Logging into Azure Container Registry..."
az acr login --name "$REGISTRY_NAME"

build_image() {
    local service="$1"
    local context="$2"
    local dockerfile="$3"

    local image="${REGISTRY_SERVER}/${service}:${IMAGE_TAG}"

    echo ""
    echo "Building $service..."

    docker build \
        --platform linux/amd64 \
        --tag "$image" \
        --file "$dockerfile" \
        "$context"

    echo "Pushing $service..."

    docker push "$image"

    echo "Completed: $service"
}

# Shared services
build_image "user-database" \
    "./shared/database" "shared/database/Dockerfile"

build_image "auth-backend" \
    "./shared/backend" "shared/backend/Dockerfile"

build_image "portal-frontend" \
    "./shared/frontend" "shared/frontend/Dockerfile"

# Assessment Tracker
build_image "assessment-database" \
    "./student-adrianvoljak/database" \
    "student-adrianvoljak/database/Dockerfile"

build_image "assessment-backend" \
    "./student-adrianvoljak" \
    "student-adrianvoljak/backend/Dockerfile"

build_image "assessment-frontend" \
    "./student-adrianvoljak/frontend" \
    "student-adrianvoljak/frontend/Dockerfile"

echo ""
echo "=== All Six Images Built and Pushed Successfully ==="
echo "Registry: $REGISTRY_SERVER"
echo "Image tag: $IMAGE_TAG"
