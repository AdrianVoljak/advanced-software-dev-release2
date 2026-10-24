#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Azure Deployment Verification
# Tests six Container Apps and the public portal.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short=12 HEAD)}"

SERVICES=(
    user-database
    auth-backend
    portal-frontend
    assessment-database
    assessment-backend
    assessment-frontend
)

PASSED=0
FAILED=0

pass() {
    echo "PASS: $1"
    PASSED=$((PASSED + 1))
}

fail() {
    echo "FAIL: $1"
    FAILED=$((FAILED + 1))
}

echo "=== Release 2 Deployment Testing ==="

az account show --output none

REGISTRY_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" -o tsv)

REGISTRY_SERVER=$(az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query loginServer -o tsv)

echo "Expected image tag: $IMAGE_TAG"

# Test 1: Verify each deployed Container App.
for service in "${SERVICES[@]}"; do
    echo ""
    echo "Checking $service..."

    if ! app_json=$(az containerapp show \
        --name "$service" \
        --resource-group "$RESOURCE_GROUP" \
        -o json 2>/dev/null); then
        fail "$service exists"
        continue
    fi

    pass "$service exists"

    actual_image=$(echo "$app_json" | \
        python -c "import json,sys; d=json.load(sys.stdin); print(d['properties']['template']['containers'][0]['image'])")

    expected_image="${REGISTRY_SERVER}/${service}:${IMAGE_TAG}"

    if [[ "$actual_image" == "$expected_image" ]]; then
        pass "$service image matches deployment"
    else
        fail "$service image mismatch: $actual_image"
    fi

    running_status=$(echo "$app_json" | \
        python -c "import json,sys; d=json.load(sys.stdin); print(d['properties'].get('runningStatus','Unknown'))")

    if [[ "$running_status" == "Running" ]]; then
        pass "$service running"
    else
        fail "$service running status: $running_status"
    fi
done

# Test 2: Public portal HTTPS availability.
PORTAL_FQDN=$(az containerapp show \
    --name portal-frontend \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv)

PORTAL_URL="https://${PORTAL_FQDN}"

echo ""
echo "Testing portal: $PORTAL_URL"

check_http() {
    local description="$1"
    local path="$2"

    local status
    status=$(curl -L -sS -o /dev/null \
        --max-time 30 \
        -w "%{http_code}" \
        "${PORTAL_URL}${path}") || status="000"

    if [[ "$status" == "200" ]]; then
        pass "$description (HTTP $status)"
    else
        fail "$description (HTTP $status)"
    fi
}

check_http "Portal homepage" "/"
check_http "Login page" "/login.html"
check_http "Registration page" "/register.html"
check_http "Assessment Tracker frontend" "/assessments/"

# Test 3: Cloud-only disabled Multi-Agent route.
multi_agent_status=$(curl -sS -o /dev/null \
    --max-time 30 \
    -w "%{http_code}" \
    "${PORTAL_URL}/multi-agent-api/" \
    ) || multi_agent_status="000"

if [[ "$multi_agent_status" == "503" ]]; then
    pass "Multi-Agent API disabled in cloud (HTTP 503)"
else
    fail "Multi-Agent API disablement (HTTP $multi_agent_status)"
fi

echo ""
echo "=== Deployment Test Summary ==="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Portal: $PORTAL_URL"
echo "Image tag: $IMAGE_TAG"

if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi

echo "=== All Deployment Tests Passed ==="
