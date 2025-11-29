Storing secrets for production

This document shows recommended approaches for storing and referencing sensitive values (API keys, DB URIs) in AWS when deploying the Dragon app.

1) AWS Secrets Manager (recommended)
   - Create a secret for each sensitive value (or a single JSON blob):
     - GEMINI_API_KEY, MONGO_URI, OPENAI_API_KEY, GROQ_API_KEY
   - In your ECS task definition, reference secrets using the `secrets` field:
     {
       "name": "GEMINI_API_KEY",
       "valueFrom": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:<secret-name>"
     }

2) SSM Parameter Store (encrypted)
   - Store encrypted SecureString parameters and reference similarly.

3) IAM and task role
   - Use an ECS Task Role with minimal permissions to access Secrets Manager/SSM.

4) GitHub Actions
   - Do NOT store secrets in the repository. Use GitHub Secrets for AWS credentials and any non-sensitive configuration.

Example: Add `secrets` entries to `taskdef.template.json` for each environment variable you want injected at runtime.
