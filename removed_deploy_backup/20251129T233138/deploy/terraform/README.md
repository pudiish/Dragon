This folder contains Terraform configuration to create an ECR repository and an EKS cluster.

Quickstart (local):
1. Configure AWS credentials in your shell (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
2. Set required Terraform variables, e.g. using environment variables:

   export TF_VAR_aws_account_id=123456789012
   export TF_VAR_aws_region=us-east-1

3. Initialize and apply Terraform:

   cd deploy/terraform
   terraform init
   terraform apply -auto-approve

4. After apply, run the kubeconfig command printed in outputs:
   aws eks update-kubeconfig --region <region> --name <cluster-name>

5. Build and push the Docker image then run the deployment script (from repo root):

   ./deploy/deploy_to_eks.sh <region> <account_id> dragon <image_tag>

Notes:
- The Terraform config uses community modules and creates a VPC, EKS cluster, and an ECR repo. Adjust resource sizes for production.
- You will need to allow Terraform to create IAM roles and EC2 instances.
