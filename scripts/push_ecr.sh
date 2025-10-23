#!/usr/bin/env bash
# Helper to build and push local image to ECR
set -euo pipefail

if [ -z "${AWS_ACCOUNT_ID:-}" ] || [ -z "${AWS_REGION:-}" ] || [ -z "${ECR_REPOSITORY:-}" ]; then
  echo "Please set AWS_ACCOUNT_ID, AWS_REGION and ECR_REPOSITORY environment variables"
  exit 2
fi

IMAGE_TAG=${1:-latest}
IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY"

# Build
docker build -t "$IMAGE_URI:$IMAGE_TAG" .

# Ensure repo exists
aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region "$AWS_REGION"

# Login & push
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker push "$IMAGE_URI:$IMAGE_TAG"

echo "Pushed $IMAGE_URI:$IMAGE_TAG"
