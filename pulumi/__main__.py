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
    STORAGE_CONFIG, 
    LAMBDA_CONFIG, 
    API_ENDPOINTS, 
    ECR_CONFIG
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

# Create S3 buckets
buckets = {}
for bucket_config in STORAGE_CONFIG["buckets"]:
    bucket = aws.s3.Bucket(
        bucket_config["name"],
        versioning=aws.s3.BucketVersioningArgs(
            enabled=bucket_config.get("enable_versioning", True),
        )
    )
    buckets[bucket_config["name"]] = bucket

# Create Lambda execution role
lambda_role = aws.iam.Role("lambda-exec-role",
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
aws.iam.RolePolicyAttachment("lambda-basic-execution",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

aws.iam.RolePolicyAttachment("lambda-s3-access",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess")

# Add inline policy for API Gateway permissions
aws.iam.RolePolicy("lambda-api-gateway-policy",
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

# Create Lambda functions
lambda_functions = {}

for function_config in LAMBDA_CONFIG["functions"]:
    # Replace bucket placeholders in environment variables
    env_vars = {}
    for key, value in function_config.get("environment_variables", {}).items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            bucket_name = value[2:-1]
            if bucket_name in buckets:
                env_vars[key] = buckets[bucket_name].id
        else:
            env_vars[key] = value

    # Create the Lambda function
    function = aws.lambda_.Function(
        f"{function_config['name']}-function",
        package_type="Image",
        image_uri=f"{account_id}.dkr.ecr.{region}.amazonaws.com/{ecr_repository}:api-{api_name}-{function_config['name']}",
        role=lambda_role.arn,
        timeout=function_config.get("timeout", 30),
        memory_size=function_config.get("memory", 2048),
        environment={
            "variables": env_vars
        }
    )
    
    lambda_functions[function_config['name']] = function

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

# Create authorizer if it exists
authorizer = None
if "authorizer" in lambda_functions:
    authorizer = aws.apigateway.Authorizer(f"{api_name}-authorizer",
        rest_api=api.id,
        type="REQUEST",
        authorizer_uri=lambda_functions["authorizer"].invoke_arn,
        authorizer_credentials=lambda_role.arn,
        identity_source="method.request.header.Authorization",
        authorizer_result_ttl_in_seconds=3600,
        name=f"{api_name}-authorizer"
    )

# Helper function to create CORS configuration
def create_cors_for_resource(resource_id, allowed_methods):
    resource_prefix = resource_id.apply(lambda id: id.split("/")[-1])
    
    options_method = aws.apigateway.Method(f"{resource_prefix}-options",
        rest_api=api.id,
        resource_id=resource_id,
        http_method="OPTIONS",
        authorization="NONE",
        request_parameters={
            "method.request.header.Access-Control-Allow-Headers": False,
            "method.request.header.Access-Control-Allow-Methods": False,
            "method.request.header.Access-Control-Allow-Origin": False
        })

    options_method_response = aws.apigateway.MethodResponse(f"{resource_prefix}-options-method-response",
        rest_api=api.id,
        resource_id=resource_id,
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

    options_integration = aws.apigateway.Integration(f"{resource_prefix}-options-integration",
        rest_api=api.id,
        resource_id=resource_id,
        http_method="OPTIONS",
        type="MOCK",
        passthrough_behavior="WHEN_NO_TEMPLATES",
        request_templates={
            "application/json": """{"statusCode": 200}"""
        },
        opts=pulumi.ResourceOptions(depends_on=[options_method]))

    options_integration_response = aws.apigateway.IntegrationResponse(f"{resource_prefix}-options-integration-response",
        rest_api=api.id,
        resource_id=resource_id,
        http_method="OPTIONS",
        status_code="200",
        response_parameters={
            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,Origin,Accept,Referer,User-Agent'",
            "method.response.header.Access-Control-Allow-Methods": f"'{','.join(allowed_methods + ['OPTIONS'])}'",
            "method.response.header.Access-Control-Allow-Origin": "'*'"
        },
        opts=pulumi.ResourceOptions(depends_on=[options_method, options_integration, options_method_response]))
    
    return [options_method, options_integration, options_method_response, options_integration_response]

# Helper function to create a method and integration
def create_method_and_integration(resource_id, method_config, resource_path, parent_path=""):
    http_method = method_config["http_method"]
    function_name = method_config["function"]
    
    # Path identification for resource
    path_identifier = f"{parent_path}/{resource_path}".strip("/").replace("/", "-")
    if http_method == "GET":
        operation_name = f"get-{path_identifier}"
    elif http_method == "POST":
        operation_name = f"create-{path_identifier}"
    elif http_method == "PUT":
        operation_name = f"update-{path_identifier}"
    elif http_method == "DELETE":
        operation_name = f"delete-{path_identifier}"
    else:
        operation_name = f"{http_method.lower()}-{path_identifier}"
    
    # Create request parameters
    request_parameters = {
        "method.request.header.Authorization": method_config.get("requires_auth", True)
    }
    
    # Add query parameters if specified
    for param in method_config.get("query_parameters", []):
        request_parameters[f"method.request.querystring.{param}"] = True
    
    # Add path parameters if it's a nested resource with an ID
    if "{" in resource_path:
        request_parameters["method.request.path.id"] = True
    
    # Create the method
    method = aws.apigateway.Method(operation_name,
        rest_api=api.id,
        resource_id=resource_id,
        http_method=http_method,
        authorization="CUSTOM" if method_config.get("requires_auth", True) and authorizer else "NONE",
        authorizer_id=authorizer.id if method_config.get("requires_auth", True) and authorizer else None,
        request_parameters=request_parameters)
    
    # Create the integration
    integration = aws.apigateway.Integration(f"{operation_name}-integration",
        rest_api=api.id,
        resource_id=resource_id,
        http_method=method.http_method,
        integration_http_method="POST",
        type="AWS_PROXY",
        uri=lambda_functions[function_name].invoke_arn,
        credentials=lambda_role.arn)
    
    return method, integration

# Create API resources and methods
resources = []
methods = []
integrations = []
cors_components = []
lambda_permissions = []

# Process API endpoints
for resource_config in API_ENDPOINTS["resources"]:
    # Create top-level resource
    resource = aws.apigateway.Resource(resource_config["path"],
        rest_api=api.id,
        parent_id=api.root_resource_id,
        path_part=resource_config["path"])
    resources.append(resource)
    
    # Add CORS configuration
    allowed_methods = [method["http_method"] for method in resource_config["methods"]]
    cors_components.extend(create_cors_for_resource(resource.id, allowed_methods))
    
    # Create methods for the resource
    for method_config in resource_config["methods"]:
        method, integration = create_method_and_integration(
            resource.id, 
            method_config, 
            resource_config["path"]
        )
        methods.append(method)
        integrations.append(integration)
        
        # Add Lambda permission for the method
        lambda_permission = aws.lambda_.Permission(
            f"{method_config['function']}-{method_config['http_method']}-permission",
            action="lambda:InvokeFunction",
            function=lambda_functions[method_config["function"]].arn,
            principal="apigateway.amazonaws.com",
            source_arn=pulumi.Output.all(api_id=api.id, stage=API_CONFIG["stage_name"]).apply(
                lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/{args['stage']}/{method_config['http_method']}/{resource_config['path']}"
            ),
            opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions[method_config["function"]]])
        )
        lambda_permissions.append(lambda_permission)
    
    # Process nested resources
    for nested_resource_config in resource_config.get("nested_resources", []):
        nested_resource = aws.apigateway.Resource(
            f"{resource_config['path']}-{nested_resource_config['path']}",
            rest_api=api.id,
            parent_id=resource.id,
            path_part=nested_resource_config["path"]
        )
        resources.append(nested_resource)
        
        # Add CORS configuration for nested resource
        nested_allowed_methods = [method["http_method"] for method in nested_resource_config["methods"]]
        cors_components.extend(create_cors_for_resource(nested_resource.id, nested_allowed_methods))
        
        # Create methods for the nested resource
        for nested_method_config in nested_resource_config["methods"]:
            nested_method, nested_integration = create_method_and_integration(
                nested_resource.id, 
                nested_method_config, 
                nested_resource_config["path"],
                resource_config["path"]
            )
            methods.append(nested_method)
            integrations.append(nested_integration)
            
            # Add Lambda permission for the nested method
            nested_lambda_permission = aws.lambda_.Permission(
                f"{nested_method_config['function']}-{nested_method_config['http_method']}-nested-permission",
                action="lambda:InvokeFunction",
                function=lambda_functions[nested_method_config["function"]].arn,
                principal="apigateway.amazonaws.com",
                source_arn=pulumi.Output.all(api_id=api.id, stage=API_CONFIG["stage_name"]).apply(
                    lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/{args['stage']}/{nested_method_config['http_method']}/{resource_config['path']}/{nested_resource_config['path']}"
                ),
                opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions[nested_method_config["function"]]])
            )
            lambda_permissions.append(nested_lambda_permission)

# Create deployment and stage
deployment_dependencies = methods + integrations + cors_components
deployment = aws.apigateway.Deployment(f"{api_name}-deployment",
    rest_api=api.id,
    opts=pulumi.ResourceOptions(depends_on=deployment_dependencies))

stage = aws.apigateway.Stage(f"{api_name}-stage",
    deployment=deployment.id,
    rest_api=api.id,
    stage_name=API_CONFIG["stage_name"])

# Add Lambda permission for the authorizer
if authorizer:
    auth_permission = aws.lambda_.Permission(
        "authorizer-permission",
        action="lambda:InvokeFunction",
        function=lambda_functions["authorizer"].arn,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.all(api_id=api.id).apply(
            lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/authorizers/*"
        ),
        opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions["authorizer"]])
    )

# Export the API endpoint URL
pulumi.export('api_url', pulumi.Output.concat(
    "https://", api.id, ".execute-api.", region, ".amazonaws.com/", stage.stage_name
))

# Automation API implementation
def pulumi_program():
    """Define the infrastructure using Pulumi's declarative approach.
    This function contains all the infrastructure code above, wrapped in a function.
    """
    # Create S3 buckets
    buckets = {}
    for bucket_config in STORAGE_CONFIG["buckets"]:
        bucket = aws.s3.Bucket(
            bucket_config["name"],
            versioning=aws.s3.BucketVersioningArgs(
                enabled=bucket_config.get("enable_versioning", True),
            )
        )
        buckets[bucket_config["name"]] = bucket

    # Create Lambda execution role
    lambda_role = aws.iam.Role("lambda-exec-role",
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
    aws.iam.RolePolicyAttachment("lambda-basic-execution",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

    aws.iam.RolePolicyAttachment("lambda-s3-access",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess")

    # Add inline policy for API Gateway permissions
    aws.iam.RolePolicy("lambda-api-gateway-policy",
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

    # Create Lambda functions
    lambda_functions = {}

    for function_config in LAMBDA_CONFIG["functions"]:
        # Replace bucket placeholders in environment variables
        env_vars = {}
        for key, value in function_config.get("environment_variables", {}).items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                bucket_name = value[2:-1]
                if bucket_name in buckets:
                    env_vars[key] = buckets[bucket_name].id
            else:
                env_vars[key] = value
                
        # Add timestamp to force updates
        env_vars["DEPLOY_TIMESTAMP"] = str(int(time.time()))

        # Create the Lambda function
        function = aws.lambda_.Function(
            f"{function_config['name']}-function",
            package_type="Image",
            image_uri=f"{account_id}.dkr.ecr.{region}.amazonaws.com/{ecr_repository}:api-{api_name}-{function_config['name']}",
            role=lambda_role.arn,
            timeout=function_config.get("timeout", 30),
            memory_size=function_config.get("memory", 2048),
            environment={
                "variables": env_vars
            }
        )
        
        lambda_functions[function_config['name']] = function

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

    # Create authorizer if it exists
    authorizer = None
    if "authorizer" in lambda_functions:
        authorizer = aws.apigateway.Authorizer(f"{api_name}-authorizer",
            rest_api=api.id,
            type="REQUEST",
            authorizer_uri=lambda_functions["authorizer"].invoke_arn,
            authorizer_credentials=lambda_role.arn,
            identity_source="method.request.header.Authorization",
            authorizer_result_ttl_in_seconds=3600,
            name=f"{api_name}-authorizer"
        )

    # Helper function to create CORS configuration
    def create_cors_for_resource(resource_id, allowed_methods):
        resource_prefix = resource_id.apply(lambda id: id.split("/")[-1])
        
        options_method = aws.apigateway.Method(f"{resource_prefix}-options",
            rest_api=api.id,
            resource_id=resource_id,
            http_method="OPTIONS",
            authorization="NONE",
            request_parameters={
                "method.request.header.Access-Control-Allow-Headers": False,
                "method.request.header.Access-Control-Allow-Methods": False,
                "method.request.header.Access-Control-Allow-Origin": False
            })

        options_method_response = aws.apigateway.MethodResponse(f"{resource_prefix}-options-method-response",
            rest_api=api.id,
            resource_id=resource_id,
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

        options_integration = aws.apigateway.Integration(f"{resource_prefix}-options-integration",
            rest_api=api.id,
            resource_id=resource_id,
            http_method="OPTIONS",
            type="MOCK",
            passthrough_behavior="WHEN_NO_TEMPLATES",
            request_templates={
                "application/json": """{"statusCode": 200}"""
            },
            opts=pulumi.ResourceOptions(depends_on=[options_method]))

        options_integration_response = aws.apigateway.IntegrationResponse(f"{resource_prefix}-options-integration-response",
            rest_api=api.id,
            resource_id=resource_id,
            http_method="OPTIONS",
            status_code="200",
            response_parameters={
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,Origin,Accept,Referer,User-Agent'",
                "method.response.header.Access-Control-Allow-Methods": f"'{','.join(allowed_methods + ['OPTIONS'])}'",
                "method.response.header.Access-Control-Allow-Origin": "'*'"
            },
            opts=pulumi.ResourceOptions(depends_on=[options_method, options_integration, options_method_response]))
        
        return [options_method, options_integration, options_method_response, options_integration_response]

    # Helper function to create a method and integration
    def create_method_and_integration(resource_id, method_config, resource_path, parent_path=""):
        http_method = method_config["http_method"]
        function_name = method_config["function"]
        
        # Path identification for resource
        path_identifier = f"{parent_path}/{resource_path}".strip("/").replace("/", "-")
        if http_method == "GET":
            operation_name = f"get-{path_identifier}"
        elif http_method == "POST":
            operation_name = f"create-{path_identifier}"
        elif http_method == "PUT":
            operation_name = f"update-{path_identifier}"
        elif http_method == "DELETE":
            operation_name = f"delete-{path_identifier}"
        else:
            operation_name = f"{http_method.lower()}-{path_identifier}"
        
        # Create request parameters
        request_parameters = {
            "method.request.header.Authorization": method_config.get("requires_auth", True)
        }
        
        # Add query parameters if specified
        for param in method_config.get("query_parameters", []):
            request_parameters[f"method.request.querystring.{param}"] = True
        
        # Add path parameters if it's a nested resource with an ID
        if "{" in resource_path:
            request_parameters["method.request.path.id"] = True
        
        # Create the method
        method = aws.apigateway.Method(operation_name,
            rest_api=api.id,
            resource_id=resource_id,
            http_method=http_method,
            authorization="CUSTOM" if method_config.get("requires_auth", True) and authorizer else "NONE",
            authorizer_id=authorizer.id if method_config.get("requires_auth", True) and authorizer else None,
            request_parameters=request_parameters)
        
        # Create the integration
        integration = aws.apigateway.Integration(f"{operation_name}-integration",
            rest_api=api.id,
            resource_id=resource_id,
            http_method=method.http_method,
            integration_http_method="POST",
            type="AWS_PROXY",
            uri=lambda_functions[function_name].invoke_arn,
            credentials=lambda_role.arn)
        
        return method, integration

    # Create API resources and methods
    resources = []
    methods = []
    integrations = []
    cors_components = []
    lambda_permissions = []

    # Process API endpoints
    for resource_config in API_ENDPOINTS["resources"]:
        # Create top-level resource
        resource = aws.apigateway.Resource(resource_config["path"],
            rest_api=api.id,
            parent_id=api.root_resource_id,
            path_part=resource_config["path"])
        resources.append(resource)
        
        # Add CORS configuration
        allowed_methods = [method["http_method"] for method in resource_config["methods"]]
        cors_components.extend(create_cors_for_resource(resource.id, allowed_methods))
        
        # Create methods for the resource
        for method_config in resource_config["methods"]:
            method, integration = create_method_and_integration(
                resource.id, 
                method_config, 
                resource_config["path"]
            )
            methods.append(method)
            integrations.append(integration)
            
            # Add Lambda permission for the method
            lambda_permission = aws.lambda_.Permission(
                f"{method_config['function']}-{method_config['http_method']}-permission",
                action="lambda:InvokeFunction",
                function=lambda_functions[method_config["function"]].arn,
                principal="apigateway.amazonaws.com",
                source_arn=pulumi.Output.all(api_id=api.id, stage=API_CONFIG["stage_name"]).apply(
                    lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/{args['stage']}/{method_config['http_method']}/{resource_config['path']}"
                ),
                opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions[method_config["function"]]])
            )
            lambda_permissions.append(lambda_permission)
        
        # Process nested resources
        for nested_resource_config in resource_config.get("nested_resources", []):
            nested_resource = aws.apigateway.Resource(
                f"{resource_config['path']}-{nested_resource_config['path']}",
                rest_api=api.id,
                parent_id=resource.id,
                path_part=nested_resource_config["path"]
            )
            resources.append(nested_resource)
            
            # Add CORS configuration for nested resource
            nested_allowed_methods = [method["http_method"] for method in nested_resource_config["methods"]]
            cors_components.extend(create_cors_for_resource(nested_resource.id, nested_allowed_methods))
            
            # Create methods for the nested resource
            for nested_method_config in nested_resource_config["methods"]:
                nested_method, nested_integration = create_method_and_integration(
                    nested_resource.id, 
                    nested_method_config, 
                    nested_resource_config["path"],
                    resource_config["path"]
                )
                methods.append(nested_method)
                integrations.append(nested_integration)
                
                # Add Lambda permission for the nested method
                nested_lambda_permission = aws.lambda_.Permission(
                    f"{nested_method_config['function']}-{nested_method_config['http_method']}-nested-permission",
                    action="lambda:InvokeFunction",
                    function=lambda_functions[nested_method_config["function"]].arn,
                    principal="apigateway.amazonaws.com",
                    source_arn=pulumi.Output.all(api_id=api.id, stage=API_CONFIG["stage_name"]).apply(
                        lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/{args['stage']}/{nested_method_config['http_method']}/{resource_config['path']}/{nested_resource_config['path']}"
                    ),
                    opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions[nested_method_config["function"]]])
                )
                lambda_permissions.append(nested_lambda_permission)

    # Create deployment and stage
    deployment_dependencies = methods + integrations + cors_components
    deployment = aws.apigateway.Deployment(f"{api_name}-deployment",
        rest_api=api.id,
        opts=pulumi.ResourceOptions(depends_on=deployment_dependencies))

    stage = aws.apigateway.Stage(f"{api_name}-stage",
        deployment=deployment.id,
        rest_api=api.id,
        stage_name=API_CONFIG["stage_name"])

    # Add Lambda permission for the authorizer
    if authorizer:
        auth_permission = aws.lambda_.Permission(
            "authorizer-permission",
            action="lambda:InvokeFunction",
            function=lambda_functions["authorizer"].arn,
            principal="apigateway.amazonaws.com",
            source_arn=pulumi.Output.all(api_id=api.id).apply(
                lambda args: f"arn:aws:execute-api:{region}:{account_id}:{args['api_id']}/authorizers/*"
            ),
            opts=pulumi.ResourceOptions(depends_on=[api, lambda_functions["authorizer"]])
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
    stack_name = f"{api_name}-stack"
    project_name = f"{api_name}-infrastructure"
    
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
        # Try to create a new stack
        stack = auto.create_stack(
            stack_name=stack_name,
            project_name=project_name,
            program=pulumi_program,
            opts=ws_opts
        )
        logger.info(f"Stack '{stack_name}' created successfully")
    except auto.StackAlreadyExistsError:
        # Stack already exists, select it
        logger.info(f"Stack '{stack_name}' already exists; selecting existing stack...")
        stack = auto.select_stack(
            stack_name=stack_name,
            project_name=project_name,
            program=pulumi_program,
            opts=ws_opts
        )

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
    logger.info(f"API URL: {up_res.outputs.get('api_url').value}")
    
    return up_res

if __name__ == "__main__":
    # Check if we should use Automation API or let Pulumi CLI handle it
    if os.getenv("USE_AUTOMATION_API", "true").lower() == "true":
        deploy_infra()
    else:
        # When run via Pulumi CLI, simply expose the resources
        # The pulumi_program function is not used in this path
        pass