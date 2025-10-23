Quick deploy helpers

Local build & push (using environment variables):

```bash
# Set these first:
export AWS_ACCOUNT_ID=123456789012
export AWS_REGION=us-east-1
export ECR_REPOSITORY=dragon

# Build & push (uses scripts/push_ecr.sh)
./scripts/push_ecr.sh latest
```

Use the GitHub Actions workflow (push to `main`) to build and deploy to ECS.
