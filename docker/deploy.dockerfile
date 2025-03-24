# docker/deploy.dockerfile
FROM python:3.12

WORKDIR /code

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl git

# Install system dependencies and AWS CLI
RUN apt-get update && \
    apt-get install -y curl git unzip && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip

# Install Pulumi
RUN curl -fsSL https://get.pulumi.com | sh && \
    mv ~/.pulumi /usr/local
ENV PATH="$PATH:/usr/local/.pulumi/bin"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for local Pulumi state
RUN mkdir -p /root/.pulumi/workspaces

# Copy infrastructure code
COPY ./pulumi /code/infrastructure

# Deployment script
COPY deploy.sh /code/deploy.sh
RUN chmod +x /code/deploy.sh

ENTRYPOINT ["/code/deploy.sh"]