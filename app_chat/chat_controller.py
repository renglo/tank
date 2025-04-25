# chat_controller.py
from flask import current_app
from app_chat.chat_model import ChatModel
from flask_cognito import current_cognito_jwt
from datetime import datetime
from common import *
import uuid



class ChatController:

    def __init__(self,tid=None,ip=None):

        self.CHM = ChatModel(tid=tid,ip=ip)
        
        
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
         
    
    def create_thread(self,entity_type,entity_id):
        
        index = f"irn:chat:{entity_type}/thread:{entity_id}"
        
        data = {
            'author_id' : self.get_current_user(),
            'time' : str(datetime.now().timestamp()),
            'is_active' : True,
            'entity_id' : entity_id,
            'entity_type' : entity_type,
            'language' : 'ES',
            'index' : index,
            '_id':str(uuid.uuid4()),        
        }
        
        response = self.CHM.create_chat(data)
        
        return response
    
    
    
    
    # MESSAGES
    
    def list_messages(self,entity_type,entity_id,thread_id):
              
        index = f"irn:chat:{entity_type}/thread/message:{entity_id}/{thread_id}"
        limit = 50
        sort = 'asc'
        
        response = self.CHM.list_chat(index,limit,sort=sort)
        
        return response
    
    
    def get_message(self, entity_type, entity_id, thread_id, message_id):
        
        index = f"irn:chat:{entity_type}/thread/message:{entity_id}/{thread_id}" 
        print(f'get_message > {index} > {message_id}') 
        response = self.CHM.get_chat(index,message_id) 
        return response
    
    
    def create_message(self, entity_type, entity_id, thread_id, payload):
        print('CHC:create_message')
        try:
            if not all([entity_type, entity_id, thread_id, payload]):
                raise ValueError("Missing required parameters")

            index = f"irn:chat:{entity_type}/thread/message:{entity_id}/{thread_id}"
            
            current_app.logger.debug(f'create_message > input > {index}')
            current_app.logger.debug(f'payload: {payload}')
            
            # Validate required payload fields
            required_fields = ['context', 'input', 'message']
            if not all(field in payload for field in required_fields):
                missing_fields = [field for field in required_fields if field not in payload]
                raise ValueError(f"Missing required payload fields: {missing_fields}")
            

            print('All fields required: OK')
            
            output = []
            if 'output' in payload and isinstance(payload['output'], list):
                output = payload['output']
            
            data = {
                'author_id': self.get_current_user(),
                'time': str(datetime.now().timestamp()),
                'is_active': True,
                'context': payload['context'],
                'input': payload['input'],
                'output': output,
                'message': payload['message'],
                'index': index,
                '_id': str(uuid.uuid4())
            }
            
            current_app.logger.debug(f'Prepared data for chat creation: {data}')
            
            response = self.CHM.create_chat(data)
            return response
            
        except Exception as e:
            current_app.logger.error(f"Error in create_message: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating message: {str(e)}",
                "status": 500
            }
        
        
    def update_message(self,entity_type, entity_id, thread_id, message_id, update):
        print(f'CHC:update_message {entity_type}/{thread_id}/{message_id}:{update}')
        try:
        
            data = self.get_message(entity_type, entity_id, thread_id, message_id)
            
            if not data['success']:
                return data
            
            item = data['item']
                
            print(f'Document retrieved:{item}')
            
            
            if 'output' not in item or not isinstance(item['output'], list):
                item['output'] = []
                
            item['output'].append(update)
            
            current_app.logger.debug(f'Prepared data for chat update: {item}')
            response = self.CHM.update_chat(item)
            print(response)
            return response
        
        except Exception as e:
            current_app.logger.error(f"Error in update_message: {str(e)}")
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
            
            data = []
            if 'data' in payload and isinstance(payload['data'], list):
                data = payload['data']
                
            config = {}
            if 'config' in payload and isinstance(payload['config'], dict):
                config = payload['config']
                
            type = 'json'
            if 'type' in payload and isinstance(payload['config'], str):
                type = payload['type']
            
            # CHANGE THIS TO FIT THE WORKSPACE SCHEMA
            data = {
                'author_id': self.get_current_user(),
                'time': str(datetime.now().timestamp()),
                'is_active': True,
                'context': context,
                'state': state,
                'type': type,
                'config' : config,
                'data':data,
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
        
            data = self.get_workspace(entity_type, entity_id, thread_id, workspace_id)
            
            print('Updating the obtained workspace document...')
            
            if not data['success']:
                return data
            
            item = data['item']
            changed = False
            
            if 'state' in payload:
                item['state'] = payload['state']
                changed = True
                
            if 'data' in item:
                item['data'] = payload['data']
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
                "message": f"Error updating message: {str(e)}",
                "status": 500
            }
                
            
    
    

            
        
        
        
        
        
        
        
    
        
        
    
    
    
   
    
    
    
    