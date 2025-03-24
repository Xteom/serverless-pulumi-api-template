# API Template Setup Instructions

This document guides you through setting up a new API using this template.

## Prerequisites

1. AWS Account with appropriate permissions
2. GitHub repository
3. Pulumi account (for state management)
4. Docker installed locally (for testing)

## Step 1: Configure GitHub Repository Secrets

Add the following secrets to your GitHub repository:

- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `AWS_ACCOUNT_ID`: Your AWS account ID
- `REPO_NAME`: Your ECR repository name
- `API_NAME`: Name of your API (e.g., "inventory", "users", "orders")
- `PULUMI_ACCESS_TOKEN`: Your Pulumi access token
- `PULUMI_CONFIG_PASSPHRASE`: A passphrase for encrypting Pulumi config values
- `PULUMI_STATE_BUCKET`: S3 bucket name for storing Pulumi state (required for Automation API)

## Step 2: Configure Your API

1. **Edit `pulumi/config.py`**:
   - Update API name, description, and stage name
   - Configure S3 buckets for your data
   - Set Lambda function configurations
   - Define API endpoints and methods

2. **Customize Lambda Functions**:
   - Edit the functions in `src/functions/` to match your business logic
   - Update required fields and validation in each function
   - Customize error handling and responses

3. **Adjust Storage Operations**:
   - Modify `src/common/storage.py` if you need different storage patterns
   - Add any specialized query methods for your use case

4. **Update Authentication**:
   - Configure `src/common/auth.py` to point to your authentication service
   - Adjust the token validation logic if needed

## Step 3: Local Testing

You can test your API locally before deploying:

```bash
# Install dependencies
pip install -r requirements.txt

# Build and run a Lambda function locally
docker build \
  --build-arg FUNCTION_NAME=get-items \
  -t api-test:latest \
  -f docker/lambda.dockerfile .

# Test with sample event
docker run -p 9000:8080 api-test:latest
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{...}'
```

## Step 4: Deployment

1. Push your changes to the main branch
2. GitHub Actions will automatically:
   - Run tests
   - Build and push Docker images
   - Deploy infrastructure with Pulumi

3. Monitor the GitHub Actions workflow for deployment status

## Step 5: Adding New Endpoints

To add a new endpoint to your API:

1. Create a new function file in `src/functions/`
2. Add the function configuration to `pulumi/config.py`
3. Add the function name to the FUNCTIONS array in `.github/workflows/build.yml`
4. Commit and push your changes

## Troubleshooting

- Check CloudWatch Logs for Lambda function errors
- Review API Gateway logs for request/response issues
- Examine GitHub Actions logs for build and deployment errors