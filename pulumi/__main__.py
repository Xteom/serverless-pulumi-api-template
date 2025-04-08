# pulumi/__main__.py

import os
import pulumi
import pulumi_aws as aws
import json
import time
import logging
from pulumi import automation as auto
from pulumi.automation import LocalWorkspaceOptions, ProjectSettings, ProjectBackend
from config import (
    API_CONFIG, 
    LAMBDA_CONFIG, 
    API_ENDPOINTS, 
    ECR_CONFIG,
    STORAGE_CONFIG
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize variables from config and environment
region = os.getenv("AWS_REGION", API_CONFIG["region"])
account_id = os.getenv("AWS_ACCOUNT_ID", ECR_CONFIG["account_id"]) 
ecr_repository = os.getenv("REPO_NAME", ECR_CONFIG["repository"])
api_name = os.getenv("API_NAME", API_CONFIG["name"])
states_bucket = os.getenv("PULUMI_STATE_BUCKET")

# Validate required environment variables
if not states_bucket and os.getenv("USE_AUTOMATION_API", "true").lower() == "true":
    logger.warning("PULUMI_STATE_BUCKET not set. Using local Pulumi state storage.")
    
if not account_id or not ecr_repository:
    logger.warning("Using values from config.py because AWS_ACCOUNT_ID or REPO_NAME not set in environment variables.")

def pulumi_program():
    """Define the infrastructure using Pulumi's declarative approach.
    This function wraps your existing Pulumi code.
    """
    # Create IAM role for Lambda functions
    lambda_role = aws.iam.Role(f"{api_name}-lambda-exec-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Principal": {
                    "Service": [
                        "lambda.amazonaws.com",
                        "apigateway.amazonaws.com"
                    ]
                },
                "Effect": "Allow",
                "Sid": ""
            }]
        }))

    # Attach policies to Lambda role
    aws.iam.RolePolicyAttachment(f"{api_name}-lambda-basic-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

    aws.iam.RolePolicyAttachment(f"{api_name}-lambda-s3-access",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess")

    # Add permissions to invoke other Lambdas
    aws.iam.RolePolicy("lambda-invoke-policy",
        role=lambda_role.name,
        policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "lambda:InvokeFunction"
                    ],
                    "Resource": "*"
                }
            ]
        }))

    # Dictionary to store Lambda functions
    lambda_functions = {}
    
    # Create Lambda functions for each function in config
    for function_config in LAMBDA_CONFIG["functions"]:
        function_name = function_config["name"]
        # Extract base name (without api prefix) for resource naming
        base_name = function_name.replace(f"api-{api_name}-", "")
        resource_name = f"{api_name}-{base_name}-function"
        
        # Add timestamp to force updates
        env_vars = function_config.get("environment_variables", {}).copy()
        env_vars["DEPLOY_TIMESTAMP"] = str(int(time.time()))
        
        # Create Lambda function
        function = aws.lambda_.Function(resource_name,
            package_type="Image",
            image_uri=f"{account_id}.dkr.ecr.{region}.amazonaws.com/{ecr_repository}:{function_name}",
            role=lambda_role.arn,
            timeout=function_config.get("timeout", 30),
            memory_size=function_config.get("memory", 2048),
            environment={
                "variables": env_vars
            })
        
        # Store function in dictionary with original name as key
        lambda_functions[function_name] = function

    # Create API Gateway
    api = aws.apigateway.RestApi(f"{api_name}-api",
        description=API_CONFIG["description"],
        endpoint_configuration={
            "types": "REGIONAL"
        },
        policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": "execute-api:Invoke",
                "Resource": "*"
            }]
        }))

    # Create authorizer if an authorizer function is present
    authorizer = None
    authorizer_function_name = f"api-{api_name}-authorizer"
    if authorizer_function_name in lambda_functions:
        authorizer = aws.apigateway.Authorizer(f"{api_name}-api-authorizer",
            rest_api=api.id,
            type="REQUEST",
            authorizer_uri=lambda_functions[authorizer_function_name].invoke_arn,
            authorizer_credentials=lambda_role.arn,
            identity_source="method.request.header.Authorization",
            authorizer_result_ttl_in_seconds=3600,
            name=f"api-{api_name}-authorizer")

    # Dictionary to store API resources
    api_resources = {}
    
    # Create API resources and methods for each resource in config
    for resource_config in API_ENDPOINTS["resources"]:
        resource_path = resource_config["path"]
        
        # Create API resource
        resource = aws.apigateway.Resource(resource_path,
            rest_api=api.id,
            parent_id=api.root_resource_id,
            path_part=resource_path)
        
        # Store resource in dictionary
        api_resources[resource_path] = resource
        
        # Add CORS support for the resource
        options_method = aws.apigateway.Method(f"{resource_path}-options",
            rest_api=api.id,
            resource_id=resource.id,
            http_method="OPTIONS",
            authorization="NONE",
            request_parameters={
                "method.request.header.Access-Control-Allow-Headers": False,
                "method.request.header.Access-Control-Allow-Methods": False,
                "method.request.header.Access-Control-Allow-Origin": False
            })

        options_method_response = aws.apigateway.MethodResponse(f"{resource_path}-options-method-response",
            rest_api=api.id,
            resource_id=resource.id,
            http_method="OPTIONS",
            status_code="200",
            response_models={
                "application/json": "Empty"
            },
            response_parameters={
                "method.response.header.Access-Control-Allow-Headers": True,
                "method.response.header.Access-Control-Allow-Methods": True,
                "method.response.header.Access-Control-Allow-Origin": True
            },
            opts=pulumi.ResourceOptions(depends_on=[options_method]))

        options_integration = aws.apigateway.Integration(f"{resource_path}-options-integration",
            rest_api=api.id,
            resource_id=resource.id,
            http_method="OPTIONS",
            type="MOCK",
            passthrough_behavior="WHEN_NO_TEMPLATES",
            request_templates={
                "application/json": """{"statusCode": 200}"""
            },
            opts=pulumi.ResourceOptions(depends_on=[options_method]))
        
        # Determine allowed methods for CORS
        allowed_methods = [method["http_method"] for method in resource_config["methods"]]
        allowed_methods_str = f"'{','.join(allowed_methods + ['OPTIONS'])}'"

        options_integration_response = aws.apigateway.IntegrationResponse(f"{resource_path}-options-integration-response",
            rest_api=api.id,
            resource_id=resource.id,
            http_method="OPTIONS",
            status_code="200",
            response_parameters={
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,Origin,Accept,Referer,User-Agent'",
                "method.response.header.Access-Control-Allow-Methods": allowed_methods_str,
                "method.response.header.Access-Control-Allow-Origin": "'*'"
            },
            opts=pulumi.ResourceOptions(depends_on=[
                options_method,
                options_integration,
                options_method_response
            ]))
        
        # Create methods for each method in resource config
        for method_config in resource_config["methods"]:
            http_method = method_config["http_method"]
            function_name = method_config["function"]
            
            # Create method
            method = aws.apigateway.Method(f"{http_method.lower()}-{resource_path}",
                rest_api=api.id,
                resource_id=resource.id,
                http_method=http_method,
                authorization="CUSTOM" if method_config.get("requires_auth", True) and authorizer else "NONE",
                authorizer_id=authorizer.id if method_config.get("requires_auth", True) and authorizer else None,
                request_parameters={
                    "method.request.header.Authorization": method_config.get("requires_auth", True)
                })
            
            # Create integration
            integration = aws.apigateway.Integration(f"{http_method.lower()}-{resource_path}-integration",
                rest_api=api.id,
                resource_id=resource.id,
                http_method=method.http_method,
                integration_http_method="POST",
                type="AWS_PROXY",
                uri=lambda_functions[function_name].invoke_arn,
                credentials=lambda_role.arn)
            
            # Create Lambda permission for API Gateway
            permission = aws.lambda_.Permission(
                f"{function_name}-{http_method}-permission",
                action="lambda:InvokeFunction",
                function=lambda_functions[function_name].arn.apply(lambda arn: arn),
                principal="apigateway.amazonaws.com",
                source_arn=pulumi.Output.all(api_id=api.id, stage=API_CONFIG["stage_name"]).apply(
                    lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/{args['stage']}/{http_method}/{resource_path}"
                ),
                opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions[function_name]])
            )

    # Create deployment with dependencies on all resources and methods
    deployment = aws.apigateway.Deployment(f"{api_name}-api-deployment",
        rest_api=api.id,
        # Add explicit depends_on for all methods and integrations
        opts=pulumi.ResourceOptions(depends_on=[
            resource for resource in api_resources.values()
        ]))

    # Create stage
    stage = aws.apigateway.Stage(f"{api_name}-api-stage",
        deployment=deployment.id,
        rest_api=api.id,
        stage_name=API_CONFIG["stage_name"])

    # Permission for authorizer if it exists
    if authorizer:
        auth_permission = aws.lambda_.Permission(
            f"{api_name}-authorizer-permission",
            action="lambda:InvokeFunction",
            function=lambda_functions[authorizer_function_name].arn.apply(lambda arn: arn),
            principal="apigateway.amazonaws.com",
            source_arn=pulumi.Output.all(api_id=api.id).apply(
                lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/authorizers/*"
            ),
            opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions[authorizer_function_name]])
        )

    # Export the API endpoint URL
    pulumi.export('api_url', pulumi.Output.concat(
        "https://", api.id, ".execute-api.", region, ".amazonaws.com/", stage.stage_name
    ))

def deploy_infra():
    """
    Deploy the infrastructure using Pulumi Automation API.
    This function creates or selects a stack and deploys the infrastructure.
    """
    # Use consistent naming for stack and project
    stack_name = f"{api_name}-stack"
    project_name = f"{api_name}-infra"
    
    # Define the Pulumi project settings with optional S3 backend
    project_settings = ProjectSettings(
        name=project_name,
        runtime="python"
    )
    
    # Add S3 backend if states_bucket is specified
    if states_bucket:
        project_settings.backend = ProjectBackend(states_bucket)
        logger.info(f"Using S3 bucket '{states_bucket}' for Pulumi state")
    
    # Pass the required environment variables to the workspace
    env_vars = {
        "AWS_REGION": region,
        "AWS_ACCOUNT_ID": account_id,
        "REPO_NAME": ecr_repository,
        "API_NAME": api_name,
        "PULUMI_CONFIG_PASSPHRASE": os.getenv("PULUMI_CONFIG_PASSPHRASE", "")
    }
    
    # Set workspace options
    ws_opts = LocalWorkspaceOptions(
        project_settings=project_settings,
        env_vars=env_vars
    )

    try:
        logger.info(f"Creating or selecting the Pulumi stack '{stack_name}'...")
        
        # First try to select the stack if it exists
        try:
            stack = auto.select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=pulumi_program,
                opts=ws_opts
            )
            logger.info(f"Selected existing stack '{stack_name}'")
        except Exception as e:
            logger.info(f"Stack selection failed: {str(e)}, trying to create new stack")
            # If selection fails, create a new stack
            stack = auto.create_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=pulumi_program,
                opts=ws_opts
            )
            logger.info(f"Created new stack '{stack_name}'")

        # Configure AWS region
        logger.info(f"Configuring AWS region '{region}' for the stack...")
        stack.set_config("aws:region", auto.ConfigValue(value=region))

        # Ensure required plugins are installed
        logger.info("Installing AWS plugin...")
        stack.workspace.install_plugin("aws", "v4.0.0")

        # Deploy the infrastructure
        logger.info("Deploying infrastructure...")
        up_res = stack.up(on_output=print)
        
        logger.info("Deployment complete!")
        if 'api_url' in up_res.outputs:
            logger.info(f"API URL: {up_res.outputs.get('api_url').value}")
        else:
            logger.warning("API URL not found in outputs")
        
        return up_res
    
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        raise

# Main entry point
if __name__ == "__main__":
    try:
        deploy_infra()
    except Exception as e:
        logger.error(f"Infrastructure deployment failed: {str(e)}")
        # Exit with error code for CI/CD pipeline to detect failure
        import sys
        sys.exit(1)