import boto3
import argparse

def create_cognito_user_pool(env_name, aws_profile, aws_region):
    """Creates a Cognito User Pool and an App Client, then returns their IDs."""
    
    # Initialize Boto3 session with the specified profile
    session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
    cognito_client = session.client("cognito-idp")

    print(f"🛠️ Creating Cognito User Pool for environment: {env_name}...")

    # Step 1: Create User Pool
    user_pool_response = cognito_client.create_user_pool(
        PoolName=env_name,
        AutoVerifiedAttributes=["email"],  # Only email as sign-in identifier
        UsernameAttributes=["email"],  # Allow sign-in using email
        Schema=[
            {
                'Name': 'email',
                'AttributeDataType': 'String',
                'Required': True,
                'Mutable': True,
            }
        ],
    )

    user_pool_id = user_pool_response["UserPool"]["Id"]
    user_pool_arn = user_pool_response["UserPool"]["Arn"]

    print(f"✅ User Pool Created! ID: {user_pool_id}")
    print(f"🔗 ARN: {user_pool_arn}")

    # Step 2: Create App Client (Single Page Application, USER_PASSWORD_AUTH)
    print(f"🛠️ Creating App Client for User Pool {user_pool_id}...")
    app_client_response = cognito_client.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=f"{env_name}_app",
        GenerateSecret=False,  # No client secret
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],  # Enable password auth flow
    )

    app_client_id = app_client_response["UserPoolClient"]["ClientId"]
    print(f"✅ App Client Created! ID: {app_client_id}")

    # Return results
    return {
        "UserPoolID": user_pool_id,
        "UserPoolARN": user_pool_arn,
        "AppClientID": app_client_id,
    }

def run(env_name, aws_profile, aws_region):
    """Programmatic entry point that returns structured data"""
    result = create_cognito_user_pool(env_name, aws_profile, aws_region)
    return {
        "user_pool_id": result["UserPoolID"],
        "user_pool_arn": result["UserPoolARN"],
        "app_client_id": result["AppClientID"]
    }

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Create an Amazon Cognito User Pool and App Client.")
    
    parser.add_argument("environment_name", type=str, help="The environment name (e.g., dev, prod, test).")
    parser.add_argument("--aws-profile", type=str, default="default", help="AWS profile to use (default: 'default').")
    parser.add_argument("--aws-region", type=str, required=True, help="AWS region (e.g., us-east-1).")

    args = parser.parse_args()

    # Run the function
    result = run(args.environment_name, args.aws_profile, args.aws_region)

    # Print the results in CLI format
    print("\n🎯 Cognito User Pool & App Client Created Successfully!\n")
    print(f"UserPoolID   : {result['user_pool_id']}")
    print(f"UserPoolARN  : {result['user_pool_arn']}")
    print(f"AppClientID  : {result['app_client_id']}")

if __name__ == "__main__":
    main()