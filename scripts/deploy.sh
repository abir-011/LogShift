#!/usr/bin/env bash
set -Eeuo pipefail

# Prevent overlapping deployments
exec 200>/tmp/logshift-deploy.lock
flock -n 200 || {
    echo "Another deployment is already running. Skipping."
    exit 0
}

APP_DIR="/home/ubuntu/LogShift"
COMPOSE_FILE="docker-compose.prod.yml"
AWS_REGION="ap-southeast-2"
ECR_REGISTRY="522979904445.dkr.ecr.ap-southeast-2.amazonaws.com"
ECR_REPOSITORY="logshift"
HEALTH_URL="http://localhost:8000/health/"

cd "$APP_DIR"

echo "Checking ECR for the latest image..."

# Find the image digest associated with the latest tag
LATEST_DIGEST=$(aws ecr describe-images \
    --repository-name "$ECR_REPOSITORY" \
    --region "$AWS_REGION" \
    --image-ids imageTag=latest \
    --query 'imageDetails[0].imageDigest' \
    --output text)

if [[ -z "$LATEST_DIGEST" || "$LATEST_DIGEST" == "None" ]]; then
    echo "ERROR: Could not find the latest ECR image."
    exit 1
fi

# Find the commit SHA tag associated with that digest
LATEST_TAG=$(aws ecr describe-images \
    --repository-name "$ECR_REPOSITORY" \
    --region "$AWS_REGION" \
    --query "imageDetails[?imageDigest=='$LATEST_DIGEST'].imageTags[]" \
    --output text | tr '\t' '\n' | grep -E '^[0-9a-f]{40}$' | head -n 1 || true)

if [[ -z "$LATEST_TAG" ]]; then
    echo "ERROR: Could not identify the commit SHA tag."
    exit 1
fi

echo "Latest available image: $LATEST_TAG"

# Identify the currently deployed image
CURRENT_IMAGE=$(docker inspect \
    --format='{{.Config.Image}}' logshift-web)

CURRENT_TAG="${CURRENT_IMAGE##*:}"

# Restore the previous image and verify its health
rollback() {
    echo "Restoring previous image: $CURRENT_TAG"

    if ! docker image inspect "$ECR_REGISTRY/$ECR_REPOSITORY:$CURRENT_TAG" >/dev/null 2>&1; then
        echo "ERROR: Previous image is unavailable locally."
        return 1
    fi

    if ! IMAGE_TAG="$CURRENT_TAG" docker compose \
        -f "$COMPOSE_FILE" up -d --no-deps web; then
        echo "ERROR: Could not restore the previous image."
        return 1
    fi

    for attempt in {1..12}; do
        if curl -fsS "$HEALTH_URL" >/dev/null; then
            echo "Rollback successful: $CURRENT_TAG"
            return 0
        fi

        echo "Waiting for rollback health check ($attempt/12)..."
        sleep 5
    done

    echo "ERROR: Previous image was restored, but health check failed."
    return 1
}

if [[ "$LATEST_TAG" == "$CURRENT_TAG" ]]; then
    echo "Already running the latest image."
    exit 0
fi

echo "Deploying $LATEST_TAG (previous: $CURRENT_TAG)"

# Authenticate Docker with ECR
aws ecr get-login-password --region "$AWS_REGION" |
    docker login --username AWS --password-stdin "$ECR_REGISTRY"

trap 'docker logout "$ECR_REGISTRY" >/dev/null 2>&1 || true' EXIT

# Pull the new image
docker pull "$ECR_REGISTRY/$ECR_REPOSITORY:$LATEST_TAG"

# Deploy without touching PostgreSQL
if ! IMAGE_TAG="$LATEST_TAG" docker compose \
    -f "$COMPOSE_FILE" up -d --no-deps web; then
    echo "ERROR: Deployment command failed. Rolling back..."
    rollback || echo "CRITICAL: Rollback failed. Manual intervention required."
    exit 1
fi

# Verify application health
for attempt in {1..12}; do
    if curl -fsS "$HEALTH_URL" >/dev/null; then
        echo "Deployment successful: $LATEST_TAG"
        exit 0
    fi

    echo "Waiting for health check ($attempt/12)..."
    sleep 5
done

# Roll back to the previous image
echo "ERROR: Health check failed. Rolling back..."

rollback || echo "CRITICAL: Rollback failed. Manual intervention required."

exit 1