# chat_routes.py

from flask import Blueprint,request,redirect,url_for, jsonify, current_app, session, render_template, make_response
from app_auth.login_required import login_required
from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt
from app_chat.chat_controller import ChatController
from app_agent.agent_controller import AgentController
from app_agent.agent_core import AgentCore
from functools import wraps
import time
import json
import boto3
from decimal import Decimal

from env_config import WEBSOCKET_CONNECTIONS

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

app_chat = Blueprint('app_chat', __name__, url_prefix='/_chat')

CHC = ChatController()
AGC = AgentController()
AGK = AgentCore()



def socket_auth_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            current_app.logger.info("Starting socket authentication process...")
            payload = request.get_json()
            
            if not payload or 'auth' not in payload:
                current_app.logger.error("Missing payload or auth token in request")
                return jsonify({'error': 'Authentication token required'}), 401
            
            auth_token = payload['auth']
            if not isinstance(auth_token, str):
                current_app.logger.error("Invalid auth token format")
                return jsonify({'error': 'Invalid authentication token format'}), 401

            # Set the token in the request headers for cognito authentication
            with current_app.test_request_context(headers={'Authorization': f'Bearer {auth_token}'}):
                try:
                    cognito_auth_required(lambda: None)()
                except Exception as cognito_error:
                    current_app.logger.error(f"Cognito authentication failed: {str(cognito_error)}")
                    return jsonify({'error': 'Invalid or expired authentication token'}), 401

            current_app.logger.info("Socket authentication successful")
            return f(*args, **kwargs)
            
        except ValueError as ve:
            current_app.logger.error(f"Invalid request format: {str(ve)}")
            return jsonify({'error': 'Invalid request format'}), 400
        except Exception as e:
            current_app.logger.error(f"Unexpected error during socket authentication: {str(e)}")
            return jsonify({'error': 'Internal authentication error'}), 500
    return wrapped

   
    
 # Web Socket endpoints
 
@app_chat.route('/message',methods=['POST'])
@socket_auth_required
def real_time_message():
    try:
        current_app.logger.info("WEBSOCKET MESSAGE IN THE CHAT APP")
        payload = request.get_json()
        if not payload:
            current_app.logger.error("No payload received")
            return jsonify({'error': 'No payload received'}), 400
            
        current_app.logger.info(payload)
        
        # Validate required fields
        required_fields = ['action', 'auth', 'data']
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            current_app.logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
        
        response = AGC.triage(payload)
        
        # Handle the case where response is a tuple (response, status)
        if isinstance(response, tuple):
            response_data, status_code = response
        else:
            response_data, status_code = response, 200
            
        current_app.logger.debug('TRACE >>')
        current_app.logger.debug(response_data)
        
        # For WebSocket responses, we need to return a specific format
        try:
            response_body = {
                'ws': True, 
                'input': payload,  
                'output': response_data
            }
            
            return {
                'statusCode': 200,
                'body': json.dumps(response_body, cls=DecimalEncoder)
                
            }
        except Exception as e:
            current_app.logger.error(f"Error handling response: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'details': str(e)
                })
            }
            
    except Exception as e:
        current_app.logger.error(f"Error processing message: {str(e)}")
        if payload.get('connectionId'):
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'details': str(e)
                })
            }
        return jsonify({'error': 'Internal server error (654)', 'details': str(e)}), 500
    


#RESTful endpoints

# Finds conversation threads based on provided entity and entity_id
# The controller will verify if the requester has access to those entities.
# INPUT: Entity, Entity ID
# OUTPUT: List of Conversation Threads (most recent on top) 

@app_chat.route('/')
@cognito_auth_required
def index():
    
    response = True
    return response


# Get a list of threads
# Shows the list of all threads related to an entity.
# SAMPLE URL https://<some_domain/_chat/<entity_type>/<entity_id>
# INPUT: entity_type, entity_id
# OUTPUT: A list of threads that belong to the entity
@app_chat.route('<string:entity_type>/<string:entity_id>', methods=['GET','POST'])
@cognito_auth_required
def chat_threads(entity_type,entity_id):
    
    if request.method == 'GET':
        response = CHC.list_threads(entity_type,entity_id)   
    elif request.method == 'POST':
        response = CHC.create_thread(entity_type,entity_id)
        
    return response




# Get/post messages from a thread
# A conversation thread is a short lived and focused exchange of messages between an agent and a team, user or group of users.
# SAMPLE URL https://<some_domain/_chat/<entity_type>/<entity_id>/<thread_id>/<messages>
# INPUT: entity_type, entity_id, thread_id
# OUTPUT: A list of messages that belong to the conversation thread
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>/messages', methods=['GET','POST'])
@cognito_auth_required
def chat_messages(entity_type,entity_id,thread_id):
    
    
    if request.method == 'GET':
        response = CHC.list_messages(entity_type,entity_id,thread_id)  
    elif request.method == 'POST':
        payload = request.get_json()
        response = CHC.create_message(entity_type,entity_id,thread_id,payload) 
        
        
    return response


# Get/post workspaces from a thread
# A conversation thread is a short lived and focused exchange of messages around workspaces between an agent and a team, user or group of users.
# SAMPLE URL https://<some_domain/_chat/<entity_type>/<entity_id>/<thread_id>
# INPUT: entity_type, entity_id, thread_id
# OUTPUT: A list of messages that belong to the conversation thread
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>/workspaces', methods=['GET','POST'])
@cognito_auth_required
def chat_workspaces(entity_type,entity_id,thread_id):
      
    if request.method == 'GET':
        response = CHC.list_workspaces(entity_type,entity_id,thread_id)  
    elif request.method == 'POST':
        payload = request.get_json()
        response = CHC.create_workspace(entity_type,entity_id,thread_id,payload) 
              
    return response



# Mutate the Workspace
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>/workspaces/<string:workspace_id>', methods=['GET','PUT'])
@cognito_auth_required
def chat_one_workspace(entity_type,entity_id,thread_id,workspace_id):
    
    if request.method == 'GET':
        response = CHC.get_workspace(entity_type,entity_id,thread_id,workspace_id)  
    elif request.method == 'PUT':
        payload = request.get_json()
        response = CHC.update_workspace(entity_type,entity_id,thread_id,workspace_id,payload) 
        
    return response



# TROUBLESHOOT (Please comment out)
@app_chat.route('/tb', methods=['POST'])
@cognito_auth_required
def chat_tb():
    payload = request.get_json()
    response = AGK.run(payload) 
    
    current_app.logger.debug('TRACE >>')
    current_app.logger.debug(response)
        
    return response


