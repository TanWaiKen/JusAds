#!/bin/bash
# ============================================================
# JusAds — Pull secrets from AWS SSM Parameter Store
# Optional: use this if you store secrets in SSM instead of
# manually editing .env.production
# ============================================================

set -e

echo "Pulling secrets from AWS SSM Parameter Store..."

OUTPUT_FILE=".env.production"

# List of parameter names (must match what you stored in SSM)
PARAMS=(
    "/jusads/VERTEX_PROJECT_ID"
    "/jusads/VERTEX_LOCATION"
    "/jusads/AWS_ACCESS_KEY_ID"
    "/jusads/AWS_SECRET_ACCESS_KEY"
    "/jusads/AWS_REGION"
    "/jusads/S3_BUCKET_NAME"
    "/jusads/SUPABASE_URL"
    "/jusads/SUPABASE_KEY"
    "/jusads/ELEVENLABS_API_KEY"
    "/jusads/TAVILY_API_KEY"
    "/jusads/PREDICTHQ_API_KEY"
    "/jusads/FLUXAI_API_KEY"
    "/jusads/ZERNIO_API_KEY"
    "/jusads/ZERNIO_ACCOUNT_TIKTOK"
    "/jusads/ZERNIO_ACCOUNT_INSTAGRAM"
)

# Clear output file
> "$OUTPUT_FILE"

for PARAM in "${PARAMS[@]}"; do
    # Extract the env var name from the path (e.g., /jusads/SUPABASE_URL -> SUPABASE_URL)
    ENV_NAME=$(basename "$PARAM")

    # Fetch from SSM (ignore errors for optional params)
    VALUE=$(aws ssm get-parameter --name "$PARAM" --with-decryption --query "Parameter.Value" --output text 2>/dev/null || echo "")

    if [ -n "$VALUE" ]; then
        echo "${ENV_NAME}=${VALUE}" >> "$OUTPUT_FILE"
        echo "  ✓ ${ENV_NAME}"
    else
        echo "  ✗ ${ENV_NAME} (not found in SSM, skipping)"
    fi
done

echo ""
echo "Done! Secrets written to ${OUTPUT_FILE}"
echo "Run: docker compose up -d"
