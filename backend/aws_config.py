"""AWS service configuration for LLM Council.

Centralizes all AWS SDK (boto3) setup: DynamoDB, Bedrock, Cognito, CloudWatch, S3.
All services are configured using environment variables or default region fallback.
"""

import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# AWS Region & Credentials
# ---------------------------------------------------------------------------
# boto3 reads AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
# automatically from environment variables or ~/.aws/credentials
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# ---------------------------------------------------------------------------
# DynamoDB Configuration (Phase 1)
# ---------------------------------------------------------------------------
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "LLMCouncilConversations")
DYNAMODB_ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL", None)  # For local dev with DynamoDB Local

def get_dynamodb_resource():
    """Get a DynamoDB resource, optionally pointing to a local endpoint."""
    kwargs = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs)

def get_dynamodb_client():
    """Get a DynamoDB client for table management operations."""
    kwargs = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.client("dynamodb", **kwargs)

# ---------------------------------------------------------------------------
# Amazon Bedrock Configuration (Phase 2)
# ---------------------------------------------------------------------------
BEDROCK_ENABLED = os.getenv("BEDROCK_ENABLED", "true").lower() == "true"
BEDROCK_REGION = os.getenv("BEDROCK_REGION", AWS_REGION)

# Bedrock model IDs mapped to friendly names (including Cross-Region Inference Profiles)
BEDROCK_MODELS = {
    "us.amazon.nova-pro-v1:0": "Amazon Nova Pro",
    "us.amazon.nova-lite-v1:0": "Amazon Nova Lite",
    "us.amazon.nova-micro-v1:0": "Amazon Nova Micro",
    "amazon.nova-pro-v1:0": "Amazon Nova Pro (Direct)",
    "amazon.nova-lite-v1:0": "Amazon Nova Lite (Direct)",
    "us.meta.llama3-3-70b-instruct-v1:0": "Meta Llama 3.3 70B",
    "us.meta.llama3-1-8b-instruct-v1:0": "Meta Llama 3.1 8B",
    "meta.llama3-1-8b-instruct-v1:0": "Meta Llama 3.1 8B (Direct)",
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0": "Claude 3.5 Sonnet v2",
    "us.anthropic.claude-3-haiku-20240307-v1:0": "Claude 3 Haiku (CR)",
    "anthropic.claude-3-haiku-20240307-v1:0": "Claude 3 Haiku",
}

# Which Bedrock models to include in the council
BEDROCK_COUNCIL_MODELS = os.getenv(
    "BEDROCK_COUNCIL_MODELS",
    "us.amazon.nova-pro-v1:0,us.amazon.nova-lite-v1:0,us.meta.llama3-3-70b-instruct-v1:0"
).split(",")

BEDROCK_CHAIRMAN_MODEL = os.getenv(
    "BEDROCK_CHAIRMAN_MODEL",
    "us.amazon.nova-pro-v1:0"
)

def get_bedrock_runtime_client():
    """Get the Bedrock Runtime client for model invocations."""
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

def get_bedrock_client():
    """Get the Bedrock management client for listing models."""
    return boto3.client("bedrock", region_name=BEDROCK_REGION)

# ---------------------------------------------------------------------------
# Amazon S3 Configuration (File Attachments)
# ---------------------------------------------------------------------------
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "llm-council-attachments")
S3_ENABLED = os.getenv("S3_ENABLED", "false").lower() == "true"

def get_s3_client():
    """Get an S3 client."""
    return boto3.client("s3", region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# Amazon Cognito Configuration (Phase 4)
# ---------------------------------------------------------------------------
COGNITO_ENABLED = os.getenv("COGNITO_ENABLED", "false").lower() == "true"
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID", "")
COGNITO_REGION = os.getenv("COGNITO_REGION", AWS_REGION)

def get_cognito_client():
    """Get a Cognito Identity Provider client."""
    return boto3.client("cognito-idp", region_name=COGNITO_REGION)

# ---------------------------------------------------------------------------
# Amazon CloudWatch Configuration (Phase 4)
# ---------------------------------------------------------------------------
CLOUDWATCH_ENABLED = os.getenv("CLOUDWATCH_ENABLED", "false").lower() == "true"
CLOUDWATCH_NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "LLMCouncil")
CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", "/llm-council/api")

def get_cloudwatch_client():
    """Get a CloudWatch client for publishing metrics."""
    return boto3.client("cloudwatch", region_name=AWS_REGION)

def get_cloudwatch_logs_client():
    """Get a CloudWatch Logs client."""
    return boto3.client("logs", region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# AWS X-Ray Configuration (Phase 4)
# ---------------------------------------------------------------------------
XRAY_ENABLED = os.getenv("XRAY_ENABLED", "false").lower() == "true"
