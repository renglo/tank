import boto3
import argparse
import json
from typing import Dict

def get_aws_account_id(session):
    """Retrieve the AWS account number dynamically."""
    sts_client = session.client("sts")
    return sts_client.get_caller_identity()["Account"]

def create_iam_role(env_name, aws_region, aws_profile):
    """Creates an IAM role for Lambda and attaches the previously created policy."""

    # Initialize Boto3 session with the specified profile
    session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
    iam_client = session.client("iam")

    # Get AWS Account ID dynamically
    aws_account_id = get_aws_account_id(session)

    # Define role name
    role_name = f"{env_name}_tt_role"
    policy_name = f"{env_name}_tt_policy"
    policy_arn = f"arn:aws:iam::{aws_account_id}:policy/{policy_name}"

    # Define the Trust Policy for the Role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "",
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "apigateway.amazonaws.com",
                        "events.amazonaws.com",
                        "lambda.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    # Step 1: Create the Role
    print(f"🛠️ Creating IAM Role: {role_name}...")
    try:
        role_response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"IAM role for {env_name} Lambda functions",
        )
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"⚠️ Role '{role_name}' already exists. Fetching existing role ARN...")
        role_arn = iam_client.get_role(RoleName=role_name)["Role"]["Arn"]
        return role_name, role_arn

    # Get role ARN
    role_arn = role_response["Role"]["Arn"]
    print(f"✅ IAM Role Created Successfully! ARN: {role_arn}")

    # Step 2: Attach the Policy
    print(f"🔗 Attaching Policy: {policy_arn} to Role: {role_name}...")
    try:
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        print("✅ Policy attached successfully!")
    except Exception as e:
        print(f"❌ Failed to attach policy: {str(e)}")

    return role_name, role_arn

def run(env_name: str, aws_region: str, aws_profile: str) -> Dict[str, str]:
    """Programmatic entry point that returns structured data"""
    role_name, role_arn = create_iam_role(env_name, aws_region, aws_profile)
    
    return {
        "role_name": role_name,
        "role_arn": role_arn
    }

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Create an IAM role for Lambda and attach a policy.")
    parser.add_argument("environment_name", type=str, help="The environment name (e.g., dev, prod, test).")
    parser.add_argument("--aws-region", type=str, required=True, help="AWS region (e.g., us-east-1).")
    parser.add_argument("--aws-profile", type=str, default="default", help="AWS profile to use (default: 'default').")

    args = parser.parse_args()

    # Run the deployment
    result = run(args.environment_name, args.aws_region, args.aws_profile)

    # Print results
    print("\n🎯 IAM Role Created Successfully!\n")
    print(f"Role Name: {result['role_name']}")
    print(f"Role ARN : {result['role_arn']}")

if __name__ == "__main__":
    main()