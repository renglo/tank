# Import flask and template operators
from flask import request,Flask,current_app, session, redirect
from default_config import *
import logging
import time
import os
import sys

#SOCKET IO
from flask_socketio import SocketIO
from flask_socketio import disconnect, emit

#CORS
from flask_cors import CORS


#blueprints
from app_blueprint.blueprint_routes import app_blueprint
from app_data.data_routes import app_data
from app_auth.auth_routes import app_auth
from app_docs.docs_routes import app_docs
from app_schd.schd_routes import app_schd
from app_chat.chat_routes import app_chat
from flask_cognito import CognitoAuth, cognito_auth_required
from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt



#from env_config import  TANK_BASE_URL, TANK_FE_BASE_URL,TANK_API_GATEWAY_ARN

from flask import Flask, jsonify

from zappa.handler import LambdaHandler
import requests

# Define the WSGI application object
app = Flask(__name__,static_folder='_tower', static_url_path='/')



app.config.from_object('default_config')

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('zappa').setLevel(logging.WARNING)
app.logger.info('Flask App defined!')

app.logger.info(f'Python Version: {sys.version}')

# Determine if the app is running on AWS Lambda or locally
if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    app.config['IS_LAMBDA'] = True
else:
    app.config['IS_LAMBDA'] = False

#app.config['TANK_BASE_URL'] = TANK_BASE_URL
#app.config['TANK_FE_BASE_URL'] = TANK_FE_BASE_URL
 

if app.config['IS_LAMBDA']:
    app.logger.info('TANK_BASE_URL:'+str(app.config['TANK_BASE_URL']))  
    app.logger.info('TANK_FE_BASE_URL:'+str(app.config['TANK_FE_BASE_URL'])) 
    app.logger.info('RUNNING ON LAMBDA ENVIRONMENT') 
    CORS(app, resources={r"*": {"origins": [app.config['TANK_FE_BASE_URL']]}})
else:
    app.logger.info('RUNNING ON LOCAL ENVIRONMENT')  
    CORS(app, resources={r"/*": {"origins": ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000"]}})


# Initialize CognitoAuth
cognito = CognitoAuth(app)


#Production blueprints
app.register_blueprint(app_data)
app.register_blueprint(app_blueprint)
app.register_blueprint(app_auth)
app.register_blueprint(app_docs)
app.register_blueprint(app_schd)
app.register_blueprint(app_chat)


#Template Filters
@app.template_filter()
def diablify(string): 
    return '666'+str(string)

@app.template_filter()
def nonone(val):
    if not val is None:
        return val
    else:
        return ''

@app.template_filter()
def is_list(val):
    return isinstance(val, list)



# Add this function before the error handler
def get_route_handler(path):
    """Handle routing for API Gateway requests"""
    # Create a new request context with the effective path
    with app.test_request_context(path):
        # Dispatch the request and get response
        try:
            # Add method and other request details from original request
            ctx = app.test_request_context(
                path,
                method=request.method,
                headers=request.headers,
                data=request.get_data(),
                json=request.get_json(silent=True)
            )
            with ctx:
                response = app.full_dispatch_request()
                return response
        except Exception as e:
            app.logger.error(f'Error handling route: {str(e)}')
            return jsonify({'error': str(e)}), 500



# Sample HTTP error handling
# If the api request is using the api gateway url, redirect to correct route. 
#If Route doesn't exist in Flask, redirect to React routes
@app.errorhandler(404)
def not_found(error):
    
    app.logger.info(f'Original URL to be redirected: {request.url}')
    
    '''
    ## IF URL USES THE API GATEWAY URL WE DETECT IT AND REDIRECT IT TO THE MAIN BASE URL
    
    # 1 : Assemble the base url from TANK_API_GATEWAY_ARN
    tank_api_gateway_arn = app.config['TANK_API_GATEWAY_ARN']
    app.logger.info(f'TANK_API_GATEWAY_ARN is:: {tank_api_gateway_arn}')
    if tank_api_gateway_arn is None:
        app.logger.info('TANK_API_GATEWAY_ARN is not set.')
        return app.send_static_file('index.html')  # or handle the error as needed

    parts = tank_api_gateway_arn.split(':')
    
    system_base_url = f'https://{parts[5]}.{parts[2]}.{parts[3]}.amazonaws.com'
      
    # 2 : Get the request_base_url from request.url
    request_base_url = f"{request.scheme}://{request.host}"
    
    # 3 : Get the effective path removing the first position
    effective_path = '/'.join(request.path.split('/')[1:]).rstrip('/')
    
    # 4. Compare system_base_url with request_base_url. If they match, redirect to the route in effective_path in the Flask App.
    if request_base_url.startswith(system_base_url):
        
        #return redirect(f'{app.config['TANK_BASE_URL']}/{effective_path}')
        new_url = f"{app.config['TANK_BASE_URL']}/{effective_path}"
        #app.logger.info(f'Routing to Flask: {new_url}')
        #return redirect(new_url)
        app.logger.info(f'Handling route in Flask: /{effective_path}')
        #app.logger.info(f'Handling route in Flask: /ping')
        return get_route_handler(f'/{effective_path}')
        #return get_route_handler(f'/ping')

    '''
    
    app.logger.info('Routing to React: ' + request.url)
    return app.send_static_file('index.html')





@app.route('/')
def index():
    app.logger.info('Hitting the root')
    return app.send_static_file('index.html')



@app.route('/time')
@cognito_auth_required
def get_current_time():
    return {
        'time': time.time(),      
        }


@app.route('/timex')
def get_current_timex():
    session['current_user'] = '7e5fb15bb'
    return {
        'time': time.time(),      
        }
    
    
@app.route('/ping')
def ping():
    
    app.logger.info("Ping!: %s", time.time())
    
    return {
        'pong':True,
        'time': time.time(),      
        }
    
#NOT USED  
@app.route('/message',methods=['POST'])
def real_time_message():
    
    app.logger.info("WEBSOCKET MESSAGE!: %s", time.time())
    
    payload = request.get_json()
    app.logger.info(payload)
    
    return {
        'ws':True,
        'time': time.time(),  
        'input': payload,    
        }
            
            

if __name__ == "__main__":
    app.logger.info("Starting Flask server with Socket.IO...")
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
    
