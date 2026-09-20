"""AWS Infrastructure Setup Script for LLM Council.

This script creates all required AWS resources:
  1. DynamoDB Table (Phase 1)
  2. S3 Bucket (optional, for file attachments)
  3. Cognito User Pool + App Client (Phase 4)
  4. CloudWatch Log Group (Phase 4)
  5. IAM Policy document (for App Runner / ECS)

Run: python -m backend.aws_setup
"""

import json
import sys
import boto3
from botocore.exceptions import ClientError


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REGION = "us-east-1"
PROJECT_NAME = "llm-council"

DYNAMODB_TABLE = "LLMCouncilConversations"
S3_BUCKET = f"{PROJECT_NAME}-attachments"
COGNITO_POOL_NAME = f"{PROJECT_NAME}-users"
CLOUDWATCH_LOG_GROUP = "/llm-council/api"


def create_dynamodb_table():
    """Create the DynamoDB conversations table."""
    print("\n📦 Phase 1: Creating DynamoDB Table...")
    client = boto3.client("dynamodb", region_name=REGION)

    try:
        client.describe_table(TableName=DYNAMODB_TABLE)
        print(f"  ✅ Table '{DYNAMODB_TABLE}' already exists.")
        return
    except client.exceptions.ResourceNotFoundException:
        pass

    client.create_table(
        TableName=DYNAMODB_TABLE,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
        Tags=[
            {"Key": "Project", "Value": PROJECT_NAME},
            {"Key": "Environment", "Value": "production"},
        ],
    )

    waiter = client.get_waiter("table_exists")
    print("  ⏳ Waiting for table to become active...")
    waiter.wait(TableName=DYNAMODB_TABLE)
    print(f"  ✅ Table '{DYNAMODB_TABLE}' created successfully!")


def create_s3_bucket():
    """Create the S3 bucket for file attachments."""
    print("\n🪣 Creating S3 Bucket...")
    s3 = boto3.client("s3", region_name=REGION)

    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=S3_BUCKET)
        else:
            s3.create_bucket(
                Bucket=S3_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=S3_BUCKET,
            VersioningConfiguration={"Status": "Enabled"},
        )

        # Block public access
        s3.put_public_access_block(
            Bucket=S3_BUCKET,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

        # Enable server-side encryption
        s3.put_bucket_encryption(
            Bucket=S3_BUCKET,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            },
        )

        print(f"  ✅ Bucket '{S3_BUCKET}' created with encryption + versioning!")

    except ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            print(f"  ✅ Bucket '{S3_BUCKET}' already exists.")
        else:
            print(f"  ❌ Error: {e}")


def create_cognito_user_pool():
    """Create the Cognito User Pool and App Client."""
    print("\n🔐 Phase 4: Creating Cognito User Pool...")
    cognito = boto3.client("cognito-idp", region_name=REGION)

    # Check if pool already exists
    pools = cognito.list_user_pools(MaxResults=60)
    for pool in pools.get("UserPools", []):
        if pool["Name"] == COGNITO_POOL_NAME:
            pool_id = pool["Id"]
            print(f"  ✅ User Pool '{COGNITO_POOL_NAME}' already exists (ID: {pool_id})")

            # Get or create app client
            clients = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=10)
            if clients.get("UserPoolClients"):
                client_id = clients["UserPoolClients"][0]["ClientId"]
                print(f"  ✅ App Client already exists (ID: {client_id})")
            else:
                client_resp = _create_app_client(cognito, pool_id)
                client_id = client_resp["UserPoolClient"]["ClientId"]
                print(f"  ✅ App Client created (ID: {client_id})")

            return pool_id, client_id

    # Create new User Pool
    response = cognito.create_user_pool(
        PoolName=COGNITO_POOL_NAME,
        Policies={
            "PasswordPolicy": {
                "MinimumLength": 8,
                "RequireUppercase": True,
                "RequireLowercase": True,
                "RequireNumbers": True,
                "RequireSymbols": False,
            }
        },
        AutoVerifiedAttributes=["email"],
        Schema=[
            {
                "Name": "email",
                "Required": True,
                "Mutable": True,
                "AttributeDataType": "String",
            }
        ],
        MfaConfiguration="OFF",
        UserPoolTags={
            "Project": PROJECT_NAME,
            "Environment": "production",
        },
    )

    pool_id = response["UserPool"]["Id"]
    print(f"  ✅ User Pool created (ID: {pool_id})")

    # Create App Client
    client_resp = _create_app_client(cognito, pool_id)
    client_id = client_resp["UserPoolClient"]["ClientId"]
    print(f"  ✅ App Client created (ID: {client_id})")

    return pool_id, client_id


def _create_app_client(cognito, pool_id):
    """Create a Cognito App Client."""
    return cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=f"{PROJECT_NAME}-web-client",
        GenerateSecret=False,  # No secret for web/SPA apps
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
            "ALLOW_USER_SRP_AUTH",
        ],
        SupportedIdentityProviders=["COGNITO"],
        AllowedOAuthFlows=["code", "implicit"],
        AllowedOAuthScopes=["openid", "email", "profile"],
        AllowedOAuthFlowsUserPoolClient=True,
        CallbackURLs=["http://localhost:5173", "https://localhost:5173"],
        LogoutURLs=["http://localhost:5173", "https://localhost:5173"],
    )


def create_cloudwatch_log_group():
    """Create the CloudWatch Log Group."""
    print("\n📊 Phase 4: Creating CloudWatch Log Group...")
    logs = boto3.client("logs", region_name=REGION)

    try:
        logs.create_log_group(
            logGroupName=CLOUDWATCH_LOG_GROUP,
            tags={
                "Project": PROJECT_NAME,
                "Environment": "production",
            },
        )
        # Set retention to 30 days to save costs
        logs.put_retention_policy(
            logGroupName=CLOUDWATCH_LOG_GROUP,
            retentionInDays=30,
        )
        print(f"  ✅ Log Group '{CLOUDWATCH_LOG_GROUP}' created (30-day retention)")

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
            print(f"  ✅ Log Group '{CLOUDWATCH_LOG_GROUP}' already exists.")
        else:
            print(f"  ❌ Error: {e}")


def generate_iam_policy():
    """Generate the IAM policy document for the backend service."""
    print("\n🔑 Generating IAM Policy Document...")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DynamDBAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:CreateTable",
                    "dynamodb:DescribeTable",
                    "dynamodb:ListTables",
                ],
                "Resource": f"arn:aws:dynamodb:{REGION}:*:table/{DYNAMODB_TABLE}",
            },
            {
                "Sid": "BedrockAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:ListFoundationModels",
                ],
                "Resource": "*",
            },
            {
                "Sid": "S3Access",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                "Resource": [
                    f"arn:aws:s3:::{S3_BUCKET}",
                    f"arn:aws:s3:::{S3_BUCKET}/*",
                ],
            },
            {
                "Sid": "CloudWatchAccess",
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                "Resource": "*",
            },
            {
                "Sid": "CognitoAccess",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:ListUserPools",
                    "cognito-idp:ListUserPoolClients",
                ],
                "Resource": "*",
            },
        ],
    }

    policy_file = "iam-policy.json"
    with open(policy_file, "w") as f:
        json.dump(policy, f, indent=2)

    print(f"  ✅ IAM policy saved to '{policy_file}'")
    print("  📋 Attach this policy to your App Runner / ECS task role using:")
    print(f"     aws iam create-policy --policy-name {PROJECT_NAME}-backend --policy-document file://{policy_file}")

    return policy


def print_env_config(pool_id=None, client_id=None):
    """Print the .env values to use."""
    print("\n" + "=" * 60)
    print("📝 UPDATE YOUR .env FILE WITH THESE VALUES:")
    print("=" * 60)
    print(f"""
# Switch to AWS services
LLM_PROVIDER=bedrock
STORAGE_BACKEND=dynamodb

# AWS Region
AWS_REGION={REGION}

# DynamoDB
DYNAMODB_TABLE_NAME={DYNAMODB_TABLE}
""")

    if pool_id and client_id:
        print(f"""# Cognito Authentication
COGNITO_ENABLED=true
COGNITO_USER_POOL_ID={pool_id}
COGNITO_APP_CLIENT_ID={client_id}
COGNITO_REGION={REGION}
""")

    print(f"""# CloudWatch Metrics
CLOUDWATCH_ENABLED=true
CLOUDWATCH_NAMESPACE=LLMCouncil
CLOUDWATCH_LOG_GROUP={CLOUDWATCH_LOG_GROUP}
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("🚀 LLM Council — AWS Infrastructure Setup")
    print("=" * 60)
    print(f"Region: {REGION}")
    print(f"Project: {PROJECT_NAME}")

    # Phase 1: DynamoDB
    create_dynamodb_table()

    # S3 Bucket
    create_s3_bucket()

    # Phase 4: Cognito
    pool_id, client_id = create_cognito_user_pool()

    # Phase 4: CloudWatch
    create_cloudwatch_log_group()

    # Generate IAM Policy
    generate_iam_policy()

    # Print .env values
    print_env_config(pool_id, client_id)

    print("\n✅ AWS infrastructure setup complete!")
    print("\n💡 Next steps:")
    print("   1. Update your .env file with the values above")
    print("   2. Enable model access in the AWS Bedrock console")
    print("   3. Run: uv run python -m backend.main")
    print("   4. Deploy: docker build -t llm-council . && docker push ...")


if __name__ == "__main__":
    main()
