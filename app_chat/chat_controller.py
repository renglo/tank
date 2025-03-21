# chat_controller.py

from app_chat.chat_model import ChatModel
from flask_cognito import current_cognito_jwt
from datetime import datetime
from common import *
import uuid

class ChatController:

    def __init__(self,tid=None,ip=None):

        self.CHM = ChatModel(tid=tid,ip=ip)
        
        
    def get_current_user(self):

        if "cognito:username" in current_cognito_jwt:
            # IdToken was used
            user_id = create_md5_hash(current_cognito_jwt["cognito:username"],9)
        else:
            # AccessToken was used
            user_id = create_md5_hash(current_cognito_jwt["username"],9)

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
    
    
    def create_message(self,entity_type,entity_id,thread_id,payload):

        index = f"irn:chat:{entity_type}/thread/message:{entity_id}/{thread_id}"
        
        context =  payload['context']
        input =  payload['input']
        output = payload['output']
        message = payload['message']
        tool_invocations = []
        
        
        
        
        data = {
            'author_id' : self.get_current_user(),
            'time' : str(datetime.now().timestamp()),
            'is_active' : True,
            'context' : context,
            'input' : input,
            'output': output,
            'message': message,
            'tool_invocations':tool_invocations,
            'index':index,
            '_id':str(uuid.uuid4()),
        }
        
        response = self.CHM.create_chat(data)
        
        return response
    
    
    
   
    
    
    
    