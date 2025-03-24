# docker/lambda.dockerfile
FROM public.ecr.aws/lambda/python:3.12

# Install dependencies using dnf instead of yum
RUN dnf update -y && \
    dnf install -y gcc python3-devel

# Argument for specifying which Lambda function to build
ARG FUNCTION_NAME=authorizer

# Create working directory
WORKDIR /var/task

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all contents from src to the root directory of the container
COPY src /var/task

# Create an entrypoint script
RUN echo "#!/bin/bash" > /entrypoint.sh && \
    echo "HANDLER_PATH=functions.api-\${API_NAME:-template}-\${FUNCTION_NAME}.handler" >> /entrypoint.sh && \
    echo "echo \"Using handler: \$HANDLER_PATH\"" >> /entrypoint.sh && \
    echo "exec python -m awslambdaric \$HANDLER_PATH" >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]