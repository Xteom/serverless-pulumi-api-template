# API Deployment Template with Pulumi Automation API

This template provides a standardized approach for deploying serverless APIs on AWS using:

- AWS Lambda with containerized functions
- API Gateway for endpoint management
- Pulumi for infrastructure as code
- Pulumi Automation API for programmatic deployments
- S3 for state management
- GitHub Actions for CI/CD

## Template Structure

```
.
├── deploy.sh                 # Deployment script
├── docker
│   ├── deploy.dockerfile     # Dockerfile for deployment container
│   └── lambda.dockerfile     # Dockerfile for Lambda containers
├── .github
│   └── workflows
│       └── build.yml         # GitHub Actions workflow
├── .gitignore
├── pulumi
│   ├── __main__.py           # Pulumi infrastructure code with Automation API
│   ├── config.py             # Configuration for your API
│   └── Pulumi.yaml           # Pulumi project file
├── requirements.txt          # Python dependencies
└── src
    ├── common                # Shared code
    │   ├── auth.py           # Authentication utilities
    │   └── ...               # Other shared modules
    └── functions             # Lambda function handlers
        ├── api-{name}-authorizer.py
        ├── api-{name}-{function}.py
        └── ...
```

## How to Use This Template

1. **Copy the Template Files**: Start by copying the template files to your new repository.

2. **Configure Your API**: Update `pulumi/config.py` with your API-specific configuration:
   - Specify your API name, description, and stage
   - Configure Lambda functions with appropriate memory and timeout settings
   - Define API resources and methods
   - Set up authorizer if needed

3. **Implement Function Handlers**: Create Lambda function handlers in `src/functions/`:
   - Follow the naming convention: `api-{api-name}-{function-name}.py`
   - Implement the main function logic
   - Use shared code from the `common` directory for reusable functionality

4. **Set Up GitHub Actions**: Update `.github/workflows/build.yml`:
   - Configure secrets for AWS credentials and ECR repository
   - Customize the workflow to build your specific Lambda functions

5. **Deploy Your API**: Push to your repository to trigger the GitHub Actions workflow or run locally:
   ```bash
   ./deploy.sh
   ```

## Key Components

### 1. Pulumi Automation API

The template uses Pulumi's Automation API for programmatic deployments:

```python
def deploy_infra():
    stack_name = f"{api_name}-stack"
    project_name = f"{api_name}-infra"
    
    # Create or select stack
    stack = auto.select_stack(...)
    
    # Deploy
    up_res = stack.up(on_output=print)
```

This approach provides:
- Consistent deployments across environments
- Centralized state management in S3
- Better error handling and logging

### 2. Lambda Function Management

Lambda functions are created from the configuration in `config.py`:

```python
for function_config in LAMBDA_CONFIG["functions"]:
    function_name = function_config["name"]
    # Create Lambda function...
```

Each function uses a Docker image from ECR with the appropriate handler code.

### 3. API Gateway Integration

API Gateway resources and methods are configured automatically:

```python
for resource_config in API_ENDPOINTS["resources"]:
    resource_path = resource_config["path"]
    # Create API resource...
    
    for method_config in resource_config["methods"]:
        # Create method and integration...
```

This includes:
- CORS configuration for cross-origin requests
- Authorization using a custom authorizer if specified
- Lambda permissions for API Gateway invocation

### 4. Error Handling and Logging

The template includes comprehensive error handling and logging:

```python
try:
    # Operation...
except Exception as e:
    logger.error(f"Error: {str(e)}")
    # Handle error...
```

## Environment Variables

The deployment process uses several environment variables, which you should configure in your GitHub repository secrets:

- **AWS Configuration**:
  - `AWS_REGION`: AWS region for deployment
  - `AWS_ACCOUNT_ID`: Your AWS account ID
  - `AWS_ACCESS_KEY_ID`: AWS access key for deployment
  - `AWS_SECRET_ACCESS_KEY`: AWS secret key for deployment

- **Pulumi Configuration**:
  - `PULUMI_STATE_BUCKET`: S3 bucket for Pulumi state
  - `PULUMI_ACCESS_TOKEN`: Pulumi access token (if using Pulumi service)
  - `PULUMI_CONFIG_PASSPHRASE`: Passphrase for Pulumi config encryption
  - `USE_AUTOMATION_API`: Set to "true" to use the Pulumi Automation API (recommended)

- **API Configuration**:
  - `API_NAME`: Name of your API
  - `REPO_NAME`: ECR repository name

- **Service URLs** (customize for your API):
  - `SERVICE_URL_1`: URL for external service 1
  - `SERVICE_URL_2`: URL for external service 2
  - `SERVICE_URL_3`: URL for external service 3
  - `AUTH_ENDPOINT`: Authentication service endpoint

## Common Customizations

### Adding a New Endpoint

To add a new endpoint:

1. Update `config.py` with the new method:
   ```python
   "methods": [
       {
           "http_method": "GET",
           "function": "api-your-api-name-get-function",
           "requires_auth": True
       }
   ]
   ```

2. Create the function handler in `src/functions/`.

3. Update `.github/workflows/build.yml` to build the new function.

### Changing Authentication

To modify the authentication:

1. Update the authorizer function in `src/functions/api-{name}-authorizer.py`.
2. Configure the authorizer in `pulumi/config.py`.
3. Set `requires_auth` to `False` for any methods that don't require authentication.

## Best Practices

1. **Modular Design**: Keep function handlers focused on a single responsibility.
2. **Environment Variables**: Store configuration in environment variables, not hardcoded.
3. **Error Handling**: Implement proper error handling in all Lambda functions.
4. **Testing**: Write tests for your API functionality before deployment.
5. **Logging**: Use consistent logging patterns for better troubleshooting.

## Troubleshooting

Common issues and solutions:

1. **"Invalid Resource identifier"**: Ensure resource IDs are correctly referenced in your Pulumi code.
2. **"Function not found"**: Check that your function names in `config.py` match the actual Lambda handlers.
3. **Deployment failures**: Check CloudWatch Logs for detailed error messages.
4. **Authentication issues**: Verify your authorizer is correctly configured and working.

For more help, check CloudWatch Logs or the GitHub Actions workflow output.