Production deployment notes (ECS / ECR)

This directory contains helper templates and notes for deploying the Dragon Streamlit app to AWS ECS (Fargate).

Prerequisites:
- An AWS account with ECR and ECS permissions
- An ECR repository (the GH Actions workflow can create one)
- An ECS cluster and service configured to run Fargate tasks
- GitHub repository secrets set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, ECR_REPOSITORY, ECS_CLUSTER, ECS_SERVICE

Recommended flow:
1. Push to `main` — GH Actions will build the Docker image and push to ECR.
2. The workflow registers a minimal task definition referencing the image and forces a new deployment of the target ECS service.

Customize the `task_definition.json` or use AWS Console to add environment variables, secrets (via Secrets Manager / SSM), and mount points.
