#!/usr/bin/env bash
set -euo pipefail

# Usage: deploy_to_eks.sh <aws_region> <aws_account_id> <ecr_repository> <image_tag>
if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <aws_region> <aws_account_id> <ecr_repository> <image_tag>"
  exit 2
fi

AWS_REGION=$1
AWS_ACCOUNT_ID=$2
ECR_REPO=$3
IMAGE_TAG=$4

ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO"

echo "Building image $ECR_URI:$IMAGE_TAG"
docker build -t "$ECR_URI:$IMAGE_TAG" ..

echo "Logging in to ECR"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

echo "Pushing image"
docker push "$ECR_URI:$IMAGE_TAG"

echo "Rendering k8s manifests"
mkdir -p /tmp/dragon_deploy
cat k8s/secret.template.yaml | \
  sed "s|\${GEMINI_API_KEY_BASE64}|$(echo -n "$GEMINI_API_KEY" | base64 -w0)|g" | \
  sed "s|\${GROQ_API_KEY_BASE64}|$(echo -n "$GROQ_API_KEY" | base64 -w0)|g" | \
  sed "s|\${MONGO_URI_BASE64}|$(echo -n "$MONGO_URI" | base64 -w0)|g" > /tmp/dragon_deploy/secret.yaml

cat k8s/deployment.yaml | sed "s|\${ECR_IMAGE}|$ECR_URI|g" | sed "s|\${IMAGE_TAG}|$IMAGE_TAG|g" > /tmp/dragon_deploy/deployment.yaml
cp k8s/service.yaml /tmp/dragon_deploy/service.yaml

echo "Applying manifests to cluster"
kubectl apply -f /tmp/dragon_deploy/secret.yaml
kubectl apply -f /tmp/dragon_deploy/deployment.yaml
kubectl apply -f /tmp/dragon_deploy/service.yaml

echo "Deployment applied. Use kubectl get svc -n default to find the LoadBalancer IP/hostname."
