import boto3
import argparse
import os
import configparser
import json
from typing import Dict


'''

Main Functions

api_exists(): Checks if a WebSocket API already exists
create_websocket_api(): Creates the main WebSocket API
create_route(): Creates a route for the API
create_integration(): Creates an HTTP integration
create_stage(): Creates a stage for deployment


Command Line Interface: 

Takes the following arguments:
environment: The environment name (which becomes the API name)
route: The route key for the WebSocket API
integration_target: The HTTP endpoint URL for integration
stage_name: The stage name (e.g., prod, dev)
--aws-profile: Optional AWS profile (defaults to "default")
--region: Optional AWS region (defaults to "us-east-1")

Usage:
python tank/installer/create_websocket_api.py <api_name> "<route>" "<endpoint>" <environment> --aws-profile <profile>


'''

def get_available_aws_profiles():
    """Retrieve available AWS profiles from ~/.aws/credentials and ~/.aws/config."""
    profiles = []
    aws_credentials_path = os.path.expanduser("~/.aws/credentials")
    aws_config_path = os.path.expanduser("~/.aws/config")

    if os.path.exists(aws_credentials_path):
        config = configparser.ConfigParser()
        config.read(aws_credentials_path)
        profiles.extend(config.sections())

    if os.path.exists(aws_config_path):
        config = configparser.ConfigParser()
        config.read(aws_config_path)
        for section in config.sections():
            if section.startswith("profile "):
                profile_name = section.replace("profile ", "")
                if profile_name not in profiles:
                    profiles.append(profile_name)

    return profiles if profiles else ["default"]

def api_exists(apigw, api_name: str) -> str:
    """Check if a WebSocket API exists and return its ID if found."""
    try:
        response = apigw.get_apis()
        for api in response.get('Items', []):
            if api['Name'] == api_name and api['ProtocolType'] == 'WEBSOCKET':
                return api['ApiId']
        return ""
    except Exception as e:
        print(f"Error checking API existence: {e}")
        return ""

def create_websocket_api(apigw, api_name: str, route_selection_expr: str) -> Dict:
    """Create a WebSocket API."""
    print(f"🛠️  Creating WebSocket API: {api_name}...")
    
    try:
        response = apigw.create_api(
            Name=api_name,
            ProtocolType='WEBSOCKET',
            RouteSelectionExpression=route_selection_expr
        )
        print(f"✅ WebSocket API '{api_name}' created successfully.")
        return response
    except Exception as e:
        print(f"❌ Error creating WebSocket API: {e}")
        raise

def create_route(apigw, api_id: str, route_key: str) -> Dict:
    """Create a route for the WebSocket API."""
    print(f"🛠️  Creating route: {route_key}...")
    
    try:
        response = apigw.create_route(
            ApiId=api_id,
            RouteKey=route_key
        )
        print(f"✅ Route '{route_key}' created successfully.")
        return response
    except Exception as e:
        print(f"❌ Error creating route: {e}")
        raise

def update_route(apigw, api_id: str, route_id: str, route_key: str, integration_id: str) -> Dict:
    """Update a route to point to an integration."""
    print(f"🛠️  Updating route target for: {route_key}...")
    
    try:
        response = apigw.update_route(
            ApiId=api_id,
            RouteId=route_id,
            RouteKey=route_key,
            Target=f'integrations/{integration_id}'
        )
        print(f"✅ Route target updated successfully.")
        return response
    except Exception as e:
        print(f"❌ Error updating route target: {e}")
        raise

def create_integration(apigw, api_id: str, route_key: str, integration_uri: str) -> Dict:
    """Create an HTTP integration for the WebSocket API."""
    print(f"🛠️  Creating integration for route: {route_key}...")
    
    try:
        # Remove @ symbol if present at the start of the integration URI
        cleaned_uri = integration_uri.lstrip('@')
        
        # Define the request template
        request_template = '''#set($inputRoot = $input.path('$'))
            {
            "handler": "$inputRoot.handler",
            "portfolio": "$inputRoot.portfolio",
            "org": "$inputRoot.org",
            "entity_type": "$inputRoot.entity_type",
            "entity_id": "$inputRoot.entity_id",
            "thread": "$inputRoot.thread",
            "connectionId": "$context.connectionId"
            }'''

        response = apigw.create_integration(
            ApiId=api_id,
            IntegrationType='HTTP',
            IntegrationMethod='POST',
            IntegrationUri=cleaned_uri,
            PassthroughBehavior='WHEN_NO_MATCH',
            RequestTemplates={
                'application/json': request_template
            }
        )
        print(f"✅ Integration for route '{route_key}' created successfully.")
        return response
    except Exception as e:
        print(f"❌ Error creating integration: {e}")
        raise

def create_stage(apigw, api_id: str, stage_name: str) -> Dict:
    """Create a stage for the WebSocket API."""
    print(f"🛠️  Creating stage: {stage_name}...")
    
    try:
        response = apigw.create_stage(
            ApiId=api_id,
            StageName=stage_name,
            AutoDeploy=True
        )
        print(f"✅ Stage '{stage_name}' created successfully.")
        return response
    except Exception as e:
        print(f"❌ Error creating stage: {e}")
        raise

def create_default_routes(apigw, api_id: str, integration_target: str) -> None:
    """Create default WebSocket routes ($connect, $disconnect)."""
    default_routes = ['$connect', '$disconnect']
    
    for route_key in default_routes:
        print(f"🛠️  Creating default route: {route_key}...")
        try:
            # Create route
            route_response = create_route(apigw, api_id, route_key)
            route_id = route_response['RouteId']

            # Create integration
            integration_response = create_integration(apigw, api_id, route_key, integration_target)
            integration_id = integration_response['IntegrationId']

            # Update route with integration target
            update_route(apigw, api_id, route_id, route_key, integration_id)
            
            print(f"✅ Default route '{route_key}' created successfully.")
        except Exception as e:
            print(f"❌ Error creating default route {route_key}: {e}")
            raise

def run(environment: str, route: str, integration_target: str, stage_name: str, 
        aws_profile: str, region: str = "us-east-1") -> Dict[str, str]:
    """Programmatic entry point that returns structured data"""
    # Initialize Boto3 Session with selected profile
    boto3.setup_default_session(profile_name=aws_profile)
    apigw = boto3.client('apigatewayv2', region_name=region)

    print(f"🔄 Using AWS Profile: {aws_profile} in region {region}")

    api_name = environment
    route_selection_expr = "$request.body.action"
    
    # Check if API already exists
    existing_api_id = api_exists(apigw, api_name)
    if existing_api_id:
        print(f"✅ WebSocket API '{api_name}' already exists with ID: {existing_api_id}")
        # Fetch the complete API details
        api_details = apigw.get_api(ApiId=existing_api_id)
        return {
            "api_id": existing_api_id,
            "api_endpoint": api_details.get('ApiEndpoint', ''),
            "stage_url": f"{api_details.get('ApiEndpoint', '')}/{stage_name}"
        }

    # Create the WebSocket API
    api = create_websocket_api(apigw, api_name, route_selection_expr)
    api_id = api['ApiId']

    # Create default routes ($connect, $disconnect)
    create_default_routes(apigw, api_id, integration_target)

    # Create custom route
    route_response = create_route(apigw, api_id, route)
    route_id = route_response['RouteId']

    # Create integration
    integration_response = create_integration(apigw, api_id, route, integration_target)
    integration_id = integration_response['IntegrationId']

    # Update route with integration target
    update_route(apigw, api_id, route_id, route, integration_id)

    # Create stage
    stage_response = create_stage(apigw, api_id, stage_name)

    return {
        "api_id": api_id,
        "api_endpoint": api.get('ApiEndpoint', ''),
        "stage_url": f"{api.get('ApiEndpoint', '')}/{stage_name}"
    }

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Create WebSocket API for a given environment.")
    parser.add_argument("environment", type=str, help="The environment name (e.g., dev, prod, test).")
    parser.add_argument("route", type=str, help="The route key for the WebSocket API.")
    parser.add_argument("integration_target", type=str, help="The integration target URL.")
    parser.add_argument("stage_name", type=str, help="The stage name (e.g., prod, dev).")
    
    available_profiles = get_available_aws_profiles()
    parser.add_argument(
        "--aws-profile",
        type=str,
        choices=available_profiles,
        default="default",
        help=f"Specify the AWS profile to use (Available: {', '.join(available_profiles)})"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region to create the API in (default: us-east-1)"
    )

    args = parser.parse_args()
    
    # Run the deployment
    result = run(args.environment, args.route, args.integration_target, 
                args.stage_name, args.aws_profile, args.region)
    
    # Print results
    print("\n✅ WebSocket API Created Successfully!\n")
    print(f"API ID: {result['api_id']}")
    print(f"API Endpoint: {result['api_endpoint']}")
    print(f"Stage URL: {result['stage_url']}\n")

if __name__ == "__main__":
    main() 