#!/usr/bin/env bash
set -euo pipefail

# Release 2 - GitHub Actions Azure OIDC setup
# Reuses the existing Azure managed identity.
# Does not create or delete Azure infrastructure.

RESOURCE_GROUP="asd-release2-rg"
IDENTITY_NAME="asd-r2-github-deploy"
REPO="AdrianVoljak/advanced-software-dev-release2"
BRANCH="main"
CREDENTIAL_NAME="release2-individual-main"

echo "=== Release 2 GitHub OIDC Setup ==="

az account show --output none
gh auth status

# Retrieve the existing managed identity.
CLIENT_ID=$(az identity show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$IDENTITY_NAME" \
    --query clientId -o tsv)

TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

if [[ -z "$CLIENT_ID" || -z "$TENANT_ID" || -z "$SUBSCRIPTION_ID" ]]; then
    echo "ERROR: Could not retrieve Azure identity details."
    exit 1
fi

# Retrieve immutable GitHub identifiers.
OWNER_ID=$(gh api "repos/$REPO" --jq '.owner.id')
REPO_ID=$(gh api "repos/$REPO" --jq '.id')

SUBJECT="repo:AdrianVoljak@${OWNER_ID}/advanced-software-dev-release2@${REPO_ID}:ref:refs/heads/${BRANCH}"

echo "Repository: $REPO"
echo "Branch: $BRANCH"
echo "OIDC subject: $SUBJECT"

# Keep existing credentials and add one for the new repository.
if az identity federated-credential show \
    --resource-group "$RESOURCE_GROUP" \
    --identity-name "$IDENTITY_NAME" \
    --name "$CREDENTIAL_NAME" \
    --output none 2>/dev/null; then

    echo "Federated credential already exists."
    EXISTING_SUBJECT=$(az identity federated-credential show \
        --resource-group "$RESOURCE_GROUP" \
        --identity-name "$IDENTITY_NAME" \
        --name "$CREDENTIAL_NAME" \
        --query subject -o tsv)

    if [[ "$EXISTING_SUBJECT" != "$SUBJECT" ]]; then
        echo "ERROR: Existing credential has a different subject."
        echo "Review it before making changes."
        exit 1
    fi
else
    az identity federated-credential create \
        --resource-group "$RESOURCE_GROUP" \
        --identity-name "$IDENTITY_NAME" \
        --name "$CREDENTIAL_NAME" \
        --issuer "https://token.actions.githubusercontent.com" \
        --subject "$SUBJECT" \
        --audiences "api://AzureADTokenExchange"
fi

# Configure secrets on the NEW GitHub repository only.
gh secret set AZURE_CLIENT_ID \
    --repo "$REPO" --body "$CLIENT_ID"

gh secret set AZURE_TENANT_ID \
    --repo "$REPO" --body "$TENANT_ID"

gh secret set AZURE_SUBSCRIPTION_ID \
    --repo "$REPO" --body "$SUBSCRIPTION_ID"

echo "=== GitHub OIDC Setup Complete ==="