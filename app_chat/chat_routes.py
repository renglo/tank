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
            
            response_body ={
                "statusCode": 200
            }
            
            # Always return a response, even if it's just an acknowledgment
            return jsonify(response_body), 200
            
        except Exception as e:
            current_app.logger.error(f"Error handling response: {str(e)}")
            return jsonify({
                'error': 'Internal server error (a)',
                'details': str(e)
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error processing message: {str(e)}")
        # Always return a response, even in error cases
        error_response = {
            'error': 'Internal server error (b)',
            'details': str(e)
        }
        if payload and 'connectionId' in payload:
            error_response['connectionId'] = payload['connectionId']
        return jsonify(error_response), 500
    


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
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>/messages', methods=['GET'])
@cognito_auth_required
def chat_messages(entity_type,entity_id,thread_id):
    
    
    if request.method == 'GET':
        response = CHC.list_messages(entity_type,entity_id,thread_id)  

        
    return response


# Get/post workspaces from a thread
# A conversation thread is a short lived and focused exchange of messages around workspaces between an agent and a team, user or group of users.
# SAMPLE URL https://<some_domain/_chat/<entity_type>/<entity_id>/<thread_id>
# INPUT: entity_type, entity_id, thread_id
# OUTPUT: A list of messages that belong to the conversation thread
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>/workspaces', methods=['GET'])
@cognito_auth_required
def chat_workspaces(entity_type,entity_id,thread_id):
      
    if request.method == 'GET':
        response = CHC.list_workspaces(entity_type,entity_id,thread_id)  
      
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
      'action':'chat_message',
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


def extract_gupshup_payload(payload):
    """
    Extract required data from Gupshup webhook payload.
    
    Args:
        payload (dict): The raw Gupshup webhook payload
        
    Returns:
        dict: Extracted data with keys: message, timestamp, sender_name, sender_id, app_id
        or tuple: (False, error_message) if extraction fails
    """
    try:
        # Validate top-level structure
        if 'entry' not in payload or not payload['entry']:
            return False, "Missing 'entry' field in payload"
        
        if 'gs_app_id' not in payload:
            return False, "Missing 'gs_app_id' field in payload"
        
        # Get the first entry
        entry = payload['entry'][0]
        if 'changes' not in entry or not entry['changes']:
            return False, "Missing 'changes' field in entry"
        
        # Get the first change
        change = entry['changes'][0]
        if 'value' not in change:
            return False, "Missing 'value' field in change"
        
        value = change['value']
        
        # Extract contacts and messages
        if 'contacts' not in value or not value['contacts']:
            return False, "Missing 'contacts' field in value"
        
        if 'messages' not in value or not value['messages']:
            return False, "Missing 'messages' field in value"
        
        contact = value['contacts'][0]
        message = value['messages'][0]
        
        # Extract required fields
        try:
            # 1. Message
            message_text = message['text']['body']
            
            # 2. Timestamp
            timestamp = message['timestamp']
            
            # 3. Sender Name
            sender_name = contact['profile']['name']
            
            # 4. Sender ID
            sender_id = contact['wa_id']
            
            # 5. App ID
            app_id = payload['gs_app_id']
            
        except KeyError as e:
            return False, f"Missing required field: {e}"
        
        # Return extracted data
        extracted_data = {
            'message': message_text,
            'timestamp': timestamp,
            'sender_name': sender_name,
            'sender_id': sender_id,
            'app_id': app_id
        }
        
        return True, extracted_data
        
    except Exception as e:
        return False, f"Error extracting data: {str(e)}"



def process_gupshup_message(portfolio, tool_id, payload):
    """
    Process a Gupshup message.

    """
    
    try:
    
        result = []
        
        valid, data = extract_gupshup_payload(payload)
        if not valid:
            current_app.logger.error(f'Invalid gupshup payload')
            return result
        
        msg_content = data['message']
        msg_timestamp = data['timestamp']
        msg_sender = data['sender_id'].strip()  # Remove whitespace and newlines

        
        entity_type = 'portfolio-tool-public'
        entity_id = f'{portfolio}-{tool_id}-{msg_sender}'
        # List threads will return success=true even if the list is empty (no threads)
        threads = CHC.list_threads(entity_type, entity_id) 

        print(f'List Threads:{threads}')
        
        initialize_thread = False
        if 'success' in threads: 
            if len(threads['items'])<1:
                # No threads found
                # ACTION: Set flag to initialize a thread
                print(f'Creating thread because: No threads have been found (List was empty)')
                initialize_thread = True
                
            else:       
                # At least one thread exists. Pick the last thread
                last_thread = threads['items'][0]
                # For the thread to be valid. It needs to belong to the message sender number and be from today. (CONDITION DEPRECATED)
                #if last_thread['author_id'] == msg_sender:
                if datetime.fromtimestamp(float(last_thread['time'])).strftime('%Y-%m-%d') == datetime.fromtimestamp(float(msg_timestamp)).strftime('%Y-%m-%d'):
                    # This user has sent another message today already
                    # Complete the input object and send message to triage . END
                    # ACTION: Capture the message_thread and forward the message to the triage
                    print(f'Writing on existing thread:{last_thread}')
                    
                    input = {
                        'action':'gupshup_message',
                        'portfolio':portfolio,
                        'public_user': msg_sender,
                        'entity_type':entity_type,
                        'entity_id':entity_id,
                        'thread':last_thread['_id'],
                        'data': msg_content
                    }
                    
                    # config_location = <org_id> | '_all'
                    # get_location = [<org_id_1>,<org_id_2>,<org_id_3>]
                    # post_location = 
                        
                    response_1 = AGC.triage(input,core_name='portfolio_public')
                    result.append(response_1)
                    return result

                else:
                    # This user has sent messages before but not today
                    # ACTION: Set flag to initialize a thread
                    print(f'Creating thread because:Last thread is not from today')
                    initialize_thread = True
                        
                
        else:
            # This user has not sent a message before
            # ACTION: Set flag to initialize a thread
            print(f'Creating thread because: no threads found')
            initialize_thread = True
        
        
                    
        if initialize_thread:
            print(f'Calling : create_thread ')
            response_2 = CHC.create_thread(entity_type,entity_id,public_user = msg_sender)
            result.append(response_2)
            if not response_2['success']:
                current_app.logger.error(f'Failed to create thread: {response_2}')
                return result
                
            new_thread_id = response_2['document']['_id'] 
            
            # This object emulates the object received via WebSocket
            input = {
                'action':'gupshup_message', # We don't need this since this is not a websocket
                'portfolio':portfolio,
                'public_user': msg_sender, # The web socket version doesn't have this attribute
                'entity_type':entity_type,
                'entity_id':entity_id,
                'thread':new_thread_id,
                'data': msg_content
            }
                
            response_3 = AGC.triage(input,core_name='portfolio_public')
            result.append(response_3)
            
        return result
            
    except Exception as e:
        current_app.logger.error(f"Error processing gupshup message: {e}")
        return result




# This is the function the WebHook receiving function
@app_chat.route('/gs_in/<string:portfolio>/<string:tool_id>', methods=['POST'])
def gupshup_in(portfolio,tool_id):
    
    # Get the payload first
    gupshup_payload = request.get_json()
    
    current_app.logger.info(f"Load G:{gupshup_payload}")
    
    tool_id = 'ca1a009b27d8' # This is a patch. You need to correct the Gubshup URL 
    
    # Send to EventBridge for async processing
    
    try:
        import boto3
        import json
        
        events = boto3.client('events')
        events.put_events(
            Entries=[
                {
                    'Source': 'custom.gupshup.webhook',
                    'DetailType': 'GupshupMessage',
                    'Detail': json.dumps({
                        'portfolio': portfolio,
                        'tool_id': tool_id,
                        'gupshup_payload': gupshup_payload
                    }),
                    'EventBusName': 'default'
                }
            ]
        )
        current_app.logger.info(f"Event sent to EventBridge for portfolio: {portfolio}, tool: {tool_id}, payload:{gupshup_payload}")
        
    except Exception as e:
        current_app.logger.error(f"Failed to send event to EventBridge: {e}")
        # Still return success to avoid webhook retries
    
    
    # Return acknowledgment immediately
    return "", 200

@app_chat.route('/gs_in/<string:portfolio>/<string:tool_id>/', methods=['POST'])
@cognito_auth_required
def gupshup_in_with_slash(portfolio, tool_id):
    # Call the same function to avoid code duplication
    return gupshup_in(portfolio, tool_id)



#https://apidev.woppi.ai/_chat/gs_in/5038a960fde7/ca1a009b27d8



@app_chat.route('/process-gupshup/', methods=['POST'])
def process_gupshup_event_with_slash():
    # Call the same function to avoid code duplication
    return process_gupshup_event()


# EventBridge processor endpoint
@app_chat.route('/process-gupshup', methods=['POST'])
def process_gupshup_event():
    """
    Process Gupshup messages sent via EventBridge.
    This endpoint is called by EventBridge when a webhook event is received.
    """
    current_app.logger.info("Processing EventBridge Gupshup event")
    
    try:
        # Extract and validate event data
        event_data = request.get_json()
        current_app.logger.info(f"Received EventBridge event: {event_data}")
        
        
        detail = event_data.get('detail', '{}')
        portfolio = detail.get('portfolio')
        tool_id = detail.get('tool_id')
        gupshup_payload = detail.get('gupshup_payload')
        
        if not all([portfolio, tool_id, gupshup_payload]):
            current_app.logger.error("Missing required fields in EventBridge event")
            return "", 400
        
        # Process the message
        response = process_gupshup_message(portfolio, tool_id, gupshup_payload)
        
        current_app.logger.info(f"Gupshup Trace >> {response}")
        
        return response, 200
            
    except Exception as e:
        current_app.logger.error(f"Error processing Gupshup message: {e}")
        return "", 500




