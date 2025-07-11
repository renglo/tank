# chat_controller.py
from flask import current_app
from app_chat.chat_model import ChatModel
from flask_cognito import current_cognito_jwt
from datetime import datetime
from common import *
import uuid
import json
import boto3

from env_config import WEBSOCKET_CONNECTIONS


class ChatController:

    def __init__(self,tid=None,ip=None):

        self.CHM = ChatModel(tid=tid,ip=ip)
        
        
    def error_chat(self,error,connection_id):
    
        try:
            self.apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=WEBSOCKET_CONNECTIONS)
        
        except Exception as e:
            print(f"Error initializing WebSocket client: {e}")
            self.apigw_client = None
        
     
        try:
            print(f'Sending Error Message to:{connection_id}')
            
            # WebSocket
            self.apigw_client.post_to_connection(
                ConnectionId=connection_id,
                Data=error
            )
               
            print(f'Error Message has been sent: {error}')
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            return False
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
        
        
    def get_current_user(self):
        
        current_app.logger.debug(f'Getting user')

        if "cognito:username" in current_cognito_jwt:
            # IdToken was used
            user_id = create_md5_hash(current_cognito_jwt["cognito:username"],9)
        else:
            # AccessToken was used
            user_id = create_md5_hash(current_cognito_jwt["username"],9)
            
        current_app.logger.debug(f'User Id:{user_id}')

        return user_id
        
        
    # THREADS
        
    def list_threads(self,entity_type,entity_id):
        
        #TO-DO : Check is this user has access to this tool before returning threads.
             
        index = f"irn:chat:{entity_type}/thread:{entity_id}"
        limit = 10
        sort = 'desc'
        
        response = self.CHM.list_chat(index,limit,sort=sort)
        
        return response
         
    
    def create_thread(self,entity_type,entity_id,public_user=''):
        
        index = f"irn:chat:{entity_type}/thread:{entity_id}"
        
        if public_user:
            author_id = public_user
        else:
            author_id = self.get_current_user()
        
        data = {
            'author_id' : author_id,
            'time' : str(datetime.now().timestamp()),
            'is_active' : True,
            'entity_id' : entity_id,
            'entity_type' : entity_type,
            'language' : 'EN',
            'index' : index,
            '_id':str(uuid.uuid4()),        
        }
        
        response = self.CHM.create_chat(data)
        
        return response
    
    
    
    
    # TURNS
    # There is a document per turn in the database
    # Every turn document contains a list of messages that belong to that turn
    
    def list_turns(self,entity_type,entity_id,thread_id):
              
        index = f"irn:chat:{entity_type}/thread/turn:{entity_id}/{thread_id}"
        limit = 50
        sort = 'asc'
        
        response = self.CHM.list_chat(index,limit,sort=sort)
        
        return response
    
    
    def get_turn(self, entity_type, entity_id, thread_id, turn_id):
        
        index = f"irn:chat:{entity_type}/thread/turn:{entity_id}/{thread_id}" 
        print(f'get_turn > {index} > {turn_id}') 
        response = self.CHM.get_chat(index,turn_id) 
        return response
    
    
    def create_turn(self, entity_type, entity_id, thread_id, payload):
        print('CHC:create_turn')
        try:
            if not all([entity_type, entity_id, thread_id, payload]):
                raise ValueError("Missing required parameters")

            index = f"irn:chat:{entity_type}/thread/turn:{entity_id}/{thread_id}"
            
            current_app.logger.debug(f'create_turn > input > {index}')
            current_app.logger.debug(f'payload: {payload}')
            
            # Validate required payload fields
            required_fields = ['context']
            if not all(field in payload for field in required_fields):
                missing_fields = [field for field in required_fields if field not in payload]
                raise ValueError(f"Missing required payload fields: {missing_fields}")
            
            print('All fields required: OK')
            
            messages = []
            if 'messages' in payload and isinstance(payload['messages'], list):
                messages = payload['messages']
                
            if payload['context']['public_user']:
                author_id = payload['context']['public_user']
            else:
                author_id = self.get_current_user()
            
            data = {
                'author_id': author_id,
                'time': str(datetime.now().timestamp()),
                'is_active': True,
                'context': payload['context'],
                'messages': messages,
                'index': index,
                '_id': str(uuid.uuid4()) # This is the turn ID 
            }
            
            current_app.logger.debug(f'Prepared data for chat creation: {data}')
            
            response = self.CHM.create_chat(data)
            return response
            
        except Exception as e:
            current_app.logger.error(f"Error in create_turn: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating turn: {str(e)}",
                "status": 500
            }
        
        
    def _convert_floats_to_strings(self, obj):
        """
        Recursively converts float values to strings in a dictionary or list structure.
        """
        if isinstance(obj, dict):
            return {k: self._convert_floats_to_strings(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_strings(item) for item in obj]
        elif isinstance(obj, float):
            return str(obj)
        return obj

    
            
    
    def update_turn(self,entity_type, entity_id, thread_id, turn_id, update, call_id=False):
        print(f'CHC:update_turn {entity_type}/{thread_id}/{turn_id}:{update}::{call_id}')
        try:
            data = self.get_turn(entity_type, entity_id, thread_id, turn_id)
            
            if not data['success']:
                return data
            
            item = data['item']
            #print(f'Document retrieved:{item}')
            
            if 'messages' not in item or not isinstance(item['messages'], list):
                item['messages'] = []
            
            
            if call_id: 
                print('Call id found:')  
                print(item['messages'])
                for i in item['messages']:
                    if 'tool_call_id' in i['_out'] and i['_out']['tool_call_id'] == call_id:
                        print(f'Found the message with matching id:{i}')
                        print(f'Replacing with new doc:{update}') 
                        # Find the index of the item in the list
                        index = item['messages'].index(i)
                        # Parse JSON string to Python object and replace content
                        try:
                            parsed_content = json.loads(update['_out']['content'])
                            
                            # Validate and normalize the parsed content
                            if isinstance(parsed_content, dict):
                                # If it's a single object, wrap it in a list
                                parsed_content = [parsed_content]
                            elif isinstance(parsed_content, list):
                                # If it's a list, validate that all items are dictionaries
                                if not all(isinstance(item, dict) for item in parsed_content):
                                    # If any item is not a dict, use original content
                                    parsed_content = update['_out']['content']
                            else:
                                # If it's neither dict nor list, use original content
                                parsed_content = update['_out']['content']
                                
                            parsed_content = self._convert_floats_to_strings(parsed_content)
                            item['messages'][index]['_out']['content'] = parsed_content
                            
                            if '_interface' in update:
                                item['messages'][index]['_interface'] = update['_interface']
                                
                            print(item['messages'][index])
                            
                            
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON content: {e}")
                            # If JSON parsing fails, keep the original string
                            parsed_content = self._convert_floats_to_strings(update['content'])
                            item['messages'][index]['_out']['content'] = parsed_content
            else:
                    
                # Convert any float values in the update to strings
                update = self._convert_floats_to_strings(update)
                item['messages'].append(update)
            
            #current_app.logger.debug(f'Prepared data for chat update: {item}')
            print(f'Store modified item:{item}')
            response = self.CHM.update_chat(item)
            print(response) 
            return response
        
        except Exception as e:
            current_app.logger.error(f"Error in update_turn: {str(e)}")
            return {
                "success": False,
                "message": f"Error updating message: {str(e)}",
                "status": 500
            }
        
        
        
    # WORKSPACE
    
    def list_workspaces(self,entity_type,entity_id,thread_id):
              
        index = f"irn:chat:{entity_type}/thread/workspace:{entity_id}/{thread_id}"
        limit = 50
        sort = 'asc'
        
        response = self.CHM.list_chat(index,limit,sort=sort)
        
        return response
    
    
    def get_workspace(self, entity_type, entity_id, thread_id, workspace_id):
        
        index = f"irn:chat:{entity_type}/thread/workspace:{entity_id}/{thread_id}" 
        print(f'get_workspace > {index} > {workspace_id}') 
        response = self.CHM.get_chat(index,workspace_id) 
        return response
    
    
    def create_workspace(self, entity_type, entity_id, thread_id, payload):
        print('CHC:create_workspace')
        try:
            
            if not all([entity_type, entity_id, thread_id]):
                raise ValueError("Missing required parameters")

            index = f"irn:chat:{entity_type}/thread/workspace:{entity_id}/{thread_id}"
            
            current_app.logger.debug(f'create_workspace > input > {index}')
            current_app.logger.debug(f'payload: {payload}')
            
            # Validate required payload fields
            '''required_fields = ['context']
            if not all(field in payload for field in required_fields):
                missing_fields = [field for field in required_fields if field not in payload]
                raise ValueError(f"Missing required payload fields: {missing_fields}")'''
            
            context = {
                'entity_type':entity_type,
                'entity_id':entity_id,
                'thread_id':thread_id
            }
            
            state = {
                "beliefs": {},
                "goals": [],            # prioritized list of pending goals
                "intentions": [],       # current committed plans 
                "history": [],          # log of completed intentions
                "in_progress": None     # the current active plan (intention)
            }
            

            print('All fields required: OK')
            
            cache = {}
            if 'cache' in payload and isinstance(payload['cache'], dict):
                cache = payload['cache']
                
            config = {}
            if 'config' in payload and isinstance(payload['config'], dict):
                config = payload['config']
                
            type = 'json'
            if 'type' in payload and isinstance(payload['type'], str):
                type = payload['type']
            
            #Check if this is a Public user
            if payload.get('context', {}).get('public_user'):
                author_id = payload['context']['public_user']
            else:
                author_id = self.get_current_user()
            
            data = {
                'author_id':author_id,
                'time': str(datetime.now().timestamp()),
                'is_active': True,
                'context': context,
                'state': state,
                'type': type,
                'config' : config,
                'cache':cache,
                'index': index,
                '_id': str(uuid.uuid4())
            }
            
            current_app.logger.debug(f'Prepared data for chat creation: {data}')
            
            response = self.CHM.create_chat(data)
            return response
            
        except Exception as e:
            current_app.logger.error(f"Error in create_workspace: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating workspace: {str(e)}",
                "status": 500
            }
        
        
    def update_workspace(self,entity_type, entity_id, thread_id, workspace_id, payload):
        print(f'CHC:update_workspace {entity_type}/{thread_id}/{workspace_id}:{payload}')
        
        try:
        
            response_0 = self.get_workspace(entity_type, entity_id, thread_id, workspace_id)
            
            print('Updating the obtained workspace document...')
            
            if not response_0['success']:
                return response_0
            
            item = response_0['item']
            changed = False
            
            if 'state' in payload:
                item['state'] = payload['state']
                changed = True
                
            if 'cache' in payload:
                if 'cache' not in item:
                    item['cache'] = {}
                item['cache'] = payload['cache']
                changed = True
                
            if changed:
                current_app.logger.debug(f'Prepared data for workspace update: {item}')
                response = self.CHM.update_chat(item)
                print(response)
                return response
        
        except Exception as e:
            current_app.logger.error(f"Error in update_workspace: {str(e)}")
            return {
                "success": False,
                "message": f"Error updating workspace: {str(e)}",
                "status": 500
            }
                
            
    
    

            
        
        
        
        
        
        
        
    
        
        
    
    
    
   
    
    
    
    