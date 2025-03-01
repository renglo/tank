import argparse
from typing import Dict, Any
import create_dynamodb_tables
import create_cognito_user_pool
import create_iam_policy
import create_iam_role
import upload_blueprints

class DeploymentResult:
    def __init__(self):
        self.environment_name: str = ""
        self.aws_profile: str = ""
        self.aws_region: str = ""
        self.dynamodb_tables: Dict[str, str] = {}
        self.cognito: Dict[str, str] = {}
        self.iam_policy: Dict[str, str] = {}
        self.iam_role: Dict[str, str] = {}
        self.status_blueprints: Dict[str, str] = {}

def deploy_environment(env_name: str, aws_profile: str, aws_region: str) -> DeploymentResult:
    """
    Deploy all resources for an environment and return structured results
    """
    result = DeploymentResult()
    result.environment_name = env_name
    result.aws_profile = aws_profile
    result.aws_region = aws_region

    # Step 1: Create DynamoDB Tables
    print("\n📦 Creating DynamoDB tables...")
    result.dynamodb_tables = create_dynamodb_tables.run(
        env_name=env_name,
        aws_profile=aws_profile
    )

    # Step 2: Create Cognito User Pool
    print("\n👥 Creating Cognito User Pool...")
    result.cognito = create_cognito_user_pool.run(
        env_name=env_name,
        aws_profile=aws_profile,
        aws_region=aws_region
    )

    # Step 3: Create IAM Policy
    print("\n🔒 Creating IAM Policy...")
    result.iam_policy = create_iam_policy.run(
        env_name=env_name,
        cognito_user_pool_id=result.cognito['user_pool_id'],
        aws_profile=aws_profile,
        aws_region=aws_region
    )

    # Step 4: Create IAM Role
    print("\n👔 Creating IAM Role...")
    result.iam_role = create_iam_role.run(
        env_name=env_name,
        aws_profile=aws_profile,
        aws_region=aws_region
    )
    
    # Step 5: Add default Blueprints
    print("\nAdding default blueprints to DB...")
    result.status_blueprints = upload_blueprints.run(
        env_name=env_name,
        aws_profile=aws_profile
    )

    return result

def print_deployment_summary(result: DeploymentResult):
    """Print a summary of all deployed resources"""
    print("\n✅ Environment Deployment Complete!")
    print("\nDeployment Summary")
    print("=================")
    print(f"Environment Name: {result.environment_name}")
    print(f"AWS Profile    : {result.aws_profile}")
    print(f"AWS Region     : {result.aws_region}")
    
    print("\nDynamoDB Tables")
    print("--------------")
    for table_name, table_arn in result.dynamodb_tables.items():
        print(f"Table: {table_name}")
        print(f"ARN  : {table_arn}")
    
    print("\nCognito User Pool")
    print("----------------")
    print(f"User Pool ID  : {result.cognito['user_pool_id']}")
    print(f"User Pool ARN : {result.cognito['user_pool_arn']}")
    print(f"App Client ID : {result.cognito['app_client_id']}")
    
    print("\nIAM Resources")
    print("-------------")
    print(f"Policy Name : {result.iam_policy['policy_name']}")
    print(f"Policy ARN  : {result.iam_policy['policy_arn']}")
    print(f"Role Name   : {result.iam_role['role_name']}")
    print(f"Role ARN    : {result.iam_role['role_arn']}")
    
    print("\nS3")
    print("-------------")
    print(f"Bucket ARN : {result.iam_policy['s3_bucket_arn']}")
    
    
    print("\nBlueprints uploaded")
    print("-------------")
    print(f"Success : {len(result.status_blueprints['success'])} blueprints")
    print(f"Failed  : {len(result.status_blueprints['failed'])} blueprints")


def main():
    parser = argparse.ArgumentParser(description="Deploy complete environment")
    parser.add_argument("environment_name", help="Name of the environment to deploy")
    parser.add_argument("--aws-profile", default="default", help="AWS profile to use")
    parser.add_argument("--aws-region", default="us-east-1", help="AWS region to deploy to")
    
    args = parser.parse_args()
    
    try:
        result = deploy_environment(
            env_name=args.environment_name,
            aws_profile=args.aws_profile,
            aws_region=args.aws_region
        )
        print_deployment_summary(result)
    except Exception as e:
        print(f"\n❌ Deployment failed: {str(e)}")
        raise

if __name__ == "__main__":
    main() 