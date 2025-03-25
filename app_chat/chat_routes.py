# chat_routes.py

from flask import Blueprint,request,redirect,url_for, jsonify, current_app, session, render_template, make_response
from app_auth.login_required import login_required
from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt
from app_chat.chat_controller import ChatController
from app_schd.schd_controller import SchdController
from flask_socketio import disconnect, emit #DEPRECATED
from functools import wraps

app_chat = Blueprint('app_chat', __name__, url_prefix='/_chat')


CHC = ChatController()
SHC = SchdController()


def socket_auth_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            current_app.logger.info("Attempting socket authentication...")
            payload = request.get_json() #Token is sent in every message because lambdas are volatile and we can't rely in 'on connection' socket auth.
            auth = payload['auth']
            if not auth:
                current_app.logger.error("No authentication token provided")
                #disconnect()
                return jsonify({'error': 'Authentication failed'}), 401

            # Set the token in the request headers so cognito_auth_required can access it
            with current_app.test_request_context(headers={'Authorization': f'Bearer {auth}'}):
                cognito_auth_required(lambda: None)()
            current_app.logger.info("Socket authentication successful")
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"Socket authentication error: {str(e)}")
            return jsonify({'error': 'Socket authentication failed'}), 401
            #disconnect()
    return wrapped



#DEPRECATED
# Socket IO
# You would need to include "app_chat_socketio_init(socketio)" in app.py to initialize these routes. 
def app_chat_socketio_init(socketio):
    current_app.logger.info("Initializing chat socket handlers...")
    
    # Use a specific namespace for chat events (e.g. '/chat')
    @socketio.on('connect', namespace='/_chat')
    @socket_auth_required
    def handle_connect():
        try:
            current_app.logger.info(f"User connected: {current_user.username}")
        except Exception as e:
            current_app.logger.error(f"Error in handle_connect: {str(e)}")
            disconnect()

    @socketio.on('disconnect', namespace='/_chat')
    def handle_disconnect():
        current_app.logger.info("User disconnected")

    @socketio.on('connect_error', namespace='/_chat')
    def handle_connect_error(error):
        current_app.logger.error(f"Connection error: {str(error)}")

    @socketio.on('chat_message')
    def handle_chat_message(data):
        try:
            current_app.logger.info(f"Received chat message: {data}")
            # Broadcast the received message back to all connected clients.
            emit('chat_response', {'message': f"Message received: {data}"}, broadcast=True)
        except Exception as e:
            current_app.logger.error(f"Error handling chat message: {str(e)}")

    current_app.logger.info("Chat socket handlers initialized successfully")
    
   
   
   
    
    
 # Web Socket endpoints
 
@app_chat.route('/message',methods=['POST'])
@socket_auth_required
def real_time_message():
    
    current_app.logger.info("WEBSOCKET MESSAGE IN THE CHAT APP")
    payload = request.get_json() 
    current_app.logger.info(payload)
    
    
    '''
    payload =
    {
        'action':'message',
        'auth':<The access token>,
        'data':<message>, 
        'handler':<tool/handler_name>
        'entity_type':<entity_type>,
        'entity_id':<entity_id>,
        'thread_id':<thread_id>,
        'portfolio':<portfolio>,
        'org':<org>
    }
    '''
    
    # Call handler
    handler = payload['handler']
    tool, handler_name = handler.split('/')
    response, status = SHC.direct_run(tool, handler_name, payload)
    
    current_app.logger.debug(response)
    
    '''
    response = 
    {
       'entity_type':<entity_type>,
       'entity_id':<entity_id>,
       'thread_id':<thread_id>,
       'context':{
           'portfolio':<portfolio>,
           'org':<org>
           },
       'input': <object sent to the handler>,
       'output': <object showing results of handler run>,
       'message': <message>
    }
    '''
    
        
    
    
    
    '''
    THIS IS TO BE IMPLEMENTED IN THE HANDLERS AND REMOVED FROM HERE
    - The handler will emit the broadcast messages to the WebHook in real time
      you don't need to do it here 
    - How are we going to deliver the right message updates to the right chats?
    - Do We need to keep track of the conversation id to do that. Or the user id or the combination?
    - All state should exist in the DB. 
    '''
    # Create a client for the API Gateway Management API.
    '''
    apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)
      
    # Broadcast message to chat group   
    connections = conn_table.scan().get("Items", []) # conn_table keeps track of all current connections to the chat
    for connection in connections:
        try:
            apigw_client.post_to_connection(
                ConnectionId=connection["connectionId"],
                Data=json.dumps(message_item)
            )
        except apigw_client.exceptions.GoneException:
            conn_table.delete_item(Key={"connectionId": connection["connectionId"]})

    '''
    
    
    return {
        'ws':True, 
        'input': payload,  
        'output':response  
        }  
    


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
# SAMPLE URL https://<some_domain/_chat/<entity_type>/<entity_id>/<thread_id>
# INPUT: entity_type, entity_id, thread_id
# OUTPUT: A list of messages that belong to the conversation thread
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>', methods=['GET','POST'])
@cognito_auth_required
def chat_messages(entity_type,entity_id,thread_id):
    
    
    if request.method == 'GET':
        response = CHC.list_messages(entity_type,entity_id,thread_id)  
    elif request.method == 'POST':
        payload = request.get_json()
        response = CHC.create_message(entity_type,entity_id,thread_id,payload) 
        
        
    return response


