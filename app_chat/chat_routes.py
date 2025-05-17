# chat_routes.py

from flask import Blueprint,request,redirect,url_for, jsonify, current_app, session, render_template, make_response
from app_auth.login_required import login_required
from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt
from app_chat.chat_controller import ChatController
from app_agent.agent_controller import AgentController
from app_auth.auth_controller import AuthController
from functools import wraps
import time
import json
import boto3
from decimal import Decimal
from datetime import datetime

from env_config import WEBSOCKET_CONNECTIONS

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

app_chat = Blueprint('app_chat', __name__, url_prefix='/_chat')

CHC = ChatController()
AGC = AgentController()
AUC = AuthController()


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
    
    '''
    Payload format
    {
      'action':'message',
      'portfolio':<portfolio_id>,
      'org':<org_id>,
      'entity_type':<entity_type>,
      'entity_id':<entity_id>,
      'thread':<thread_id>,
      'data': <raw_message>
    }
    '''
    payload = request.get_json()
    response = AGC.triage(payload)
    
    current_app.logger.debug('TRACE >>')
    current_app.logger.debug(response)
        
    return response



# PROTOTYPE FUNCTION. IT CONTAINS MANY HARDCODED DEPENDENCIES
@app_chat.route('/gs_in/<string:portfolio>', methods=['POST'])
@cognito_auth_required
def gupshup_in(portfolio):
    
    
    org_id = ''
    entity_id = ''
    thread_id = ''
    
    '''
    EXAMPLE OF GUPSHUP INBOUND MESSAGE
    It states that a customer has sent a message to your WhatsApp Business API phone number. 
     
        {   
        "app": "DemoApp", 
        "timestamp": 1580227766370,   
        "version": 2, 
        "type": "message",    
        "payload": {  
            "id": "ABEGkYaYVSEEAhAL3SLAWwHKeKrt6s3FKB0c",   
            "source": "918x98xx21x4",   
            "type": "text"|"image"|"file"|"audio"|"video"|"contact"|"location"|"button_reply"|"list_reply", 
            "payload": {    
            // Varies according to the type of payload.    
            },  
            "sender": { 
            "phone": "918x98xx21x4",  
            "name": "Drew",   
            "country_code": "91", 
            "dial_code": "8x98xx21x4" 
            },  
            "context": {    
            "id": "gBEGkYaYVSEEAgnPFrOLcjkFjL8",  
            "gsId": "9b71295f-f7af-4c1f-b2b4-31b4a4867bad"    
            }   
        } 
        }
    '''
    
    gupshup_payload = request.get_json()
    
    msg_content ='Reservation for 5 please' # This should be extracted from the gupshup_payload
    msg_timestamp = gupshup_payload['payload']['timestamps']
    msg_sender = gupshup_payload['payload']['source'] # This is the sender number


    # The origin_number in the route will help you identify portfolio_id,
    # The origin number will help you identify org_id if the number is unique for that org. 
    # Otherwise, the agent would need to operate on a portfolio level to ask the user what org they are referring to. 
    # The org selection needs to be stored somewhere for subsequent messages to be directed to the right org.
    # At the beginning of the message processing, the agent will have to consult this memory to figure out what org the user is referring to. 
    # entity_id if formed from three components: org (which we already inferred in the last step), tool (which we can acquire from the tree for this portfolio), section which is constant: 'wa'
    # thread_id we can just use the most recent one. A new thread will be created automatically on the first message of the day. 
    
    
    #IMPLEMENTATION STEPS:
    
    # Check that Portfolio sent in the callback url is legit.
    
    # Search for tools in this portfolio. The Woppi tool should be installed
    tool_id = None
    tools = AUC.list_entity('tool',{'portfolio_id':portfolio})
    for tool in tools['document']['items']:
        if tool['handle'] == 'woppi':  
            tool_id = tool['_id']
            break
        
    if not tool_id:
        # If woppi is not installed return an error.
        return False, 400

    initialize_thread = False
    # Getting all the orgs under the portfolio
    orgs = AUC.list_entity('org',{'portfolio_id':portfolio}) 
    for org_object in orgs['document']['items']:  
        
        # In every org, look for threads that are part of the portfolio and tool submitted by the sender 
        entity_type = 'portfolio-tool-sender'
        entity_id = f'{portfolio}-{tool_id}-{msg_sender}'
        threads = CHC.list_threads(entity_type,entity_id) 
        
        '''
        EXAMPLE , Threads
        
        {
            "items": [
                {
                    "_id": "8fcdd1f4-7eb8-4720-875e-3058b96867af",
                    "author_id": "9177697760",
                    "entity_id": "5038a960fde7-ca1a009b27d8-9177697760",
                    "entity_type": "portfolio-tool-sender",
                    "index": "irn:chat:portfolio-tool-sender/thread:5038a960fde7-ca1a009b27d8-9177697760",
                    "is_active": true,
                    "language": "ES",
                    "time": "1747404175.06456"
                }
            ],
            "success": true
        }
        
        '''
        
        if 'success' in threads: 
            if len(threads['items'])<1:
                # No threads found
                # ACTION: Set flag to initialize a thread
                return False
                
            # Pick the last thread
            last_thread = threads['items'][-1]
            # For the thread to be valid. It needs to belong to the message sender number and be from today.
            if last_thread['author_id'] == gupshup_payload['payload']['source']:
                if datetime.fromtimestamp(float(last_thread['time'])).strftime('%Y-%m-%d') == datetime.fromtimestamp(float(msg_timestamp)/1000).strftime('%Y-%m-%d'):
                    # This user has sent another message today already
                    # Complete the input object and send message to triage . END
                    # ACTION: Capture the message_thread and forward the message to the triage
                    input = {
                        'action':'message',
                        'portfolio':portfolio,
                        'org':org_object['_id'],
                        'entity_type':entity_type,
                        'entity_id':entity_id,
                        'thread':last_thread['_id'],
                        'data': raw_message
                    }
                        
                    response = AGC.triage(input)
                    initialize_thread = False
                    break
    
                else:
                    # This user has sent messages before but not today
                    # ACTION: Set flag to initialize a thread
                    initialize_thread = True
            else:
                # This user has not sent a message before
                # ACTION: Set flag to initialize a thread
                initialize_thread = True
        
                
            
    if initialize_thread:
        
        pass
        
        # 1. You need to ask the user what org they refer to. Provide a list of orgs from the portfolio.
        
        
    
    #2b. If not, then 
    
    

    
    

     
    
    
    current_app.logger.debug('TRACE >>')
    current_app.logger.debug(response)
        
    return response


