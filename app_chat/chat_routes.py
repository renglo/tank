# chat_routes.py

from flask import Blueprint,request,redirect,url_for, jsonify, current_app, session, render_template, make_response
from app_auth.login_required import login_required
from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt
from app_chat.chat_controller import ChatController
from flask_socketio import disconnect, emit
from functools import wraps
import logging

app_chat = Blueprint('app_chat', __name__, url_prefix='/_chat')
logger = logging.getLogger(__name__)

CHC = ChatController()

def socket_auth_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            logger.info("Attempting socket authentication...")
            # Get the token from the socket auth
            auth = request.args.get('auth')
            if not auth:
                logger.error("No authentication token provided")
                disconnect()
                return

            # Use the same authentication as REST endpoints
            cognito_auth_required()(lambda: None)()
            logger.info("Socket authentication successful")
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            disconnect()
    return wrapped

# Socket IO
def app_chat_socketio_init(socketio):
    logger.info("Initializing chat socket handlers...")
    
    # Use a specific namespace for chat events (e.g. '/chat')
    @socketio.on('connect', namespace='/_chat')
    @socket_auth_required
    def handle_connect():
        try:
            logger.info(f"User connected: {current_user.username}")
        except Exception as e:
            logger.error(f"Error in handle_connect: {str(e)}")
            disconnect()

    @socketio.on('disconnect', namespace='/_chat')
    def handle_disconnect():
        logger.info("User disconnected")

    @socketio.on('connect_error', namespace='/_chat')
    def handle_connect_error(error):
        logger.error(f"Connection error: {str(error)}")

    @socketio.on('chat_message')
    def handle_chat_message(data):
        try:
            logger.info(f"Received chat message: {data}")
            # Broadcast the received message back to all connected clients.
            emit('chat_response', {'message': f"Message received: {data}"}, broadcast=True)
        except Exception as e:
            logger.error(f"Error handling chat message: {str(e)}")

    logger.info("Chat socket handlers initialized successfully")

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
def list_threads(entity_type,entity_id):
    
    if request.method == 'GET':
        response = CHC.list_threads(entity_type,entity_id)   
    elif request.method == 'POST':
        response = CHC.create_thread(entity_type,entity_id)
        
    return response




# Get messages from a thread
# A conversation thread is a short lived and focused exchange of messages between an agent and a team, user or group of users.
# SAMPLE URL https://<some_domain/_chat/<entity_type>/<entity_id>/<thread_id>
# INPUT: entity_type, entity_id, thread_id
# OUTPUT: A list of messages that belong to the conversation thread
@app_chat.route('<string:entity_type>/<string:entity_id>/<string:thread_id>', methods=['GET','POST'])
@cognito_auth_required
def list_messages(entity_type,entity_id,thread_id):
    
    
    if request.method == 'GET':
        response = CHC.list_messages(entity_type,entity_id,thread_id)  
    elif request.method == 'POST':
        payload = request.get_json()
        response = CHC.create_message(entity_type,entity_id,thread_id,payload) 
        
        
    return response


