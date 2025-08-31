#
from app_data.data_controller import DataController
from app_docs.docs_controller import DocsController
from app_chat.chat_controller import ChatController
from app_schd.schd_controller import SchdController


from openai import OpenAI

import random
import json
import boto3
from datetime import datetime
from typing import List, Dict, Any, Callable
import re
from decimal import Decimal
from contextvars import ContextVar
from dataclasses import dataclass, field
import time
import uuid

from env_config import OPENAI_API_KEY,WEBSOCKET_CONNECTIONS

# Optional imports with default values
try:
    from env_config import AGENT_API_OUTPUT
except ImportError:
    AGENT_API_OUTPUT = None

try:
    from env_config import AGENT_API_HANDLER
except ImportError:
    AGENT_API_HANDLER = None

@dataclass
class RequestContext:
    """Request-scoped context for agent operations."""
    connection_id: str = ''
    portfolio: str = ''
    org: str = ''
    public_user: str = ''
    entity_type: str = ''
    entity_id: str = ''
    thread: str = ''
    workspace_id: str = ''
    chat_id: str = ''
    workspace: Dict[str, Any] = field(default_factory=dict)
    belief: Dict[str, Any] = field(default_factory=dict)
    desire: str = ''
    action: str = ''
    plan: Dict[str, Any] = field(default_factory=dict)
    execute_intention_results: Dict[str, Any] = field(default_factory=dict)
    execute_intention_error: str = ''
    completion_result: Dict[str, Any] = field(default_factory=dict)
    list_handlers: Dict[str, Any] = field(default_factory=dict)
    message_history: List[Dict[str, Any]] = field(default_factory=list)
    list_actions: List[Dict[str, Any]] = field(default_factory=list)
    list_tools: List[Dict[str, Any]] = field(default_factory=list)

# Create a context variable to store the request context
request_context: ContextVar[RequestContext] = ContextVar('request_context', default=RequestContext())

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

class AgentCore:
    def __init__(self):
        
        #OpenAI Client
        try:    
            openai_client = OpenAI(api_key=OPENAI_API_KEY,)
            print(f"OpenAI client initialized")
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            openai_client = None

        self.AI_1 = openai_client
        #self.AI_1_MODEL = "gpt-4" // This model does not support json_object response format
        self.AI_1_MODEL = "gpt-3.5-turbo" # Baseline model. Good for multi-step chats
        self.AI_2_MODEL = "gpt-4o-mini" # This model is not very smart
        
        
        self.DAC = DataController()
        self.DCC = DocsController()
        self.CHC = ChatController()
        self.SHC = SchdController()
        
        try:
        
            self.apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=WEBSOCKET_CONNECTIONS)
        
        except Exception as e:
            print(f"Error initializing WebSocket client: {e}")
            self.apigw_client = None
        
        
       

    def _get_context(self) -> RequestContext:
        """Get the current request context."""
        return request_context.get()

    def _set_context(self, context: RequestContext):
        """Set the current request context."""
        request_context.set(context)

    def _update_context(self, **kwargs):
        """Update specific fields in the current request context."""
        context = self._get_context()
        for key, value in kwargs.items():
            setattr(context, key, value)
        self._set_context(context)
        
        
    
    def get_message_history(self):
        
        action = 'get_message_history'
        #print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        try:
            
            print(f'type :{self._get_context().entity_type}')
            print(f'entity_id :{self._get_context().entity_id}')
            print(f'thread :{self._get_context().thread}')
        
            # Thead was not included, create a new one?
            if not self._get_context().thread:
                return {'success':False,'action':action,'output':f'Error: No thread provided'}
                
                
        
            response = self.CHC.list_turns(
                            self._get_context().portfolio,
                            self._get_context().org,
                            self._get_context().entity_type,
                            self._get_context().entity_id,
                            self._get_context().thread
                        )
            
            if 'success' not in response:
                print(f'Something failed during message list: {response}')
                return {'success':False,'action':action,'input':self._get_context().thread,'output':response}
            
            
            # Prepare messages to look like an OpenAI message array
            # Also remove messages that don't belong to an approved type
            message_list = []
            for turn in response['items']: 
                for m in turn['messages']:
                    out_message = m['_out']
                    if m['_type'] in ['user','system','text','tool_rq','tool_rs']: #OK to show to LLM
                        message_list.append(out_message)      
            
            
            return {'success':True,'action':action,'input':self._get_context().thread,'output':message_list}
        
        except Exception as e:
            print(f'Update chat message failed: {str(e)}')
            return {'success':False,'action':action,'output':f'Error:{str(e)}'}
        
        
        
    
    def update_chat_message_document(self,update,call_id=False):
        
        action = 'update_chat_message_document'
        print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        try:
        
            response = self.CHC.update_turn(
                            self._get_context().portfolio,
                            self._get_context().org,
                            self._get_context().entity_type,
                            self._get_context().entity_id,
                            self._get_context().thread,
                            self._get_context().chat_id,
                            update,
                            call_id=call_id
                        )
            
            if 'success' not in response:
                print(f'Something failed during update chat message {response}')
                return {'success':False,'action':action,'input':update,'output':response}
            
            #print(f'All good during update chat message {response}')
            return {'success':True,'action':action,'input':update,'output':response}
        
        except Exception as e:
            print(f'Update chat message failed: {str(e)}')
            return {'success':False,'action':action,'output':f'Error:{str(e)}'}



    def update_workspace_document(self,portfolio,org,update,workspace_id):
        
        action = 'update_workspace_document'
        print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        response = self.CHC.update_workspace(
                        self._get_context().portfolio,
                        self._get_context().org,
                        self._get_context().entity_type,
                        self._get_context().entity_id,
                        self._get_context().thread,
                        workspace_id,
                        update
                    )
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':update,'output':response}
        
        return {'success':True,'action':action,'input':update,'output':response}
    
    
    def update_chat_message_context(self,doc,reset=False):
        
        if reset:
            # Instead of trying to update the volatile context, just get the messages 
            # from the Database
            message_history = self.get_message_history()
            self._update_context(message_history=message_history['output'])
            
        else:
            # Adding to the context without having to call the DB
            current_history = self._get_context().message_history
            current_history.append(doc['_out'])
            self._update_context(message_history=current_history)
        
    
    
    def save_chat(self,output,interface=False):
        

        if  output['tool_calls']  and output['role']=='assistant':
            # This is a tool call
            message_type = 'tool_rq'
            doc = {'_out':self.sanitize(output),'_type':'tool_rq'}
             # Memorize to permanent storage
            self.update_chat_message_document(doc)
            self.update_chat_message_context(doc)
            
            for tool_call in output['tool_calls']:
                
                rs_template = {
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": []
                    }
                doc_rs_placeholder = {'_out':rs_template,'_type':'tool_rs'}
                self.update_chat_message_document(doc_rs_placeholder)
                self.update_chat_message_context(doc_rs_placeholder)
            
            
        elif output['content'] and output['role']=='assistant':
            # This is a human readable message from the agent to the user
            message_type = 'text'
            doc = {'_out':self.sanitize(output),'_type':message_type}
            # Memorize to permanent storage
            self.update_chat_message_document(doc)
            self.update_chat_message_context(doc)
            # Print to live chat
            self.print_chat(output,message_type)
            # Print to API
            self.print_api(output['content'],message_type)
            
        elif 'tool_call_id' in output and 'role' in output and output['role']=='tool':
            # This is a response from the tool
                        
            print(f'Including Tool Response in the chat: {output}')
            # This is the tool response
            message_type = 'tool_rs'            
            doc = {'_out':self.sanitize(output),'_type':message_type,'_interface':interface}
            # Memorize to permanent storage
            self.update_chat_message_document(doc,output['tool_call_id'])
            self.update_chat_message_context(doc,reset=True)
              
            if interface:  
                self.print_chat(doc,message_type,True)
                           
     
          
    
    def print_api(self,message,type='text'):
        
        action = 'print_api'
         
        try:
            if AGENT_API_OUTPUT and AGENT_API_HANDLER:
                
                context = self._get_context()
                if context.public_user:
                    target = context.public_user
                else:
                    return {'success':False,'action':action,'input':message,'output':'This is an internal call, no API output is needed'}
               
                
                params = {'message':message,'type':type,'target':target}  
                
                parts = AGENT_API_HANDLER.split('/')
                if len(parts) != 2:
                    error_msg = f"{AGENT_API_HANDLER} is not a valid tool."
                    print(error_msg)
                    self.print_chat(error_msg, 'text')
                    raise ValueError(error_msg)
                
                portfolio = self._get_context().portfolio
                org = self._get_context().org
                
                print(f'Calling {AGENT_API_HANDLER} ') 
                response = self.SHC.handler_call(portfolio,org,parts[0],parts[1],params)
                
                return response
            else:
                return {'success':False,'action':action,'input':message,'output':'AGENT_API_OUTPUT or AGENT_API_HANDLER not configured'}
                
        except ValueError as ve:
            print(f"ValueError in {action}: {ve}")
            return {'success':False,'action':action,'input':message,'output':str(ve)}
        except Exception as e:
            print(f"Error in {action}: {e}")
            return {'success':False,'action':action,'input':message,'output':str(e)}
        
 
        

    def print_chat(self,output,type='text',as_is=False):
        
        print(f'Running: Print Chat:{output}')
        
        if as_is:
            doc = output  
        elif isinstance(output, dict) and 'role' in output and 'content' in output and output['role'] and output['content']: 
            # Content responses from LLM  
            doc = {'_out':{'role':output['role'],'content':self.sanitize(output['content'])},'_type':type}      
        elif isinstance(output, str):
            # Any text response
            doc = {'_out':{'role':'assistant','content':str(output)},'_type':type}     
        else:
            # Everything else
            doc = {'_out':{'role':'assistant','content':self.sanitize(output)},'_type':type} 
            
            
        context = self._get_context()
        if not context.connection_id or not self.apigw_client:
            print(f'WebSocket not configured or this is a RESTful post to the chat.')
            return False
             
        try:
            print(f'Sending Real Time Message to:{context.connection_id}')
            
            # WebSocket
            self.apigw_client.post_to_connection(
                ConnectionId=context.connection_id,
                Data=json.dumps(doc, cls=DecimalEncoder)
            )
               
            print(f'Message has been updated')
            
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            self._update_context(connection_id='')  # Clear the connection ID
            return False
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
                
                
                
    def mutate_workspace(self,changes):

        context = self._get_context()
        if not context.thread:
            return False
        
        if context.public_user:
            payload = {'context':{'public_user':context.public_user}}
        else:
            payload = {}
        

        print("MUTATE_WORKSPACE>>",changes)
       
        #1. Get the workspace in this thread
        workspaces_list = self.CHC.list_workspaces(
            context.portfolio,
            context.org,
            context.entity_type,
            context.entity_id,
            context.thread
            ) 
        print('WORKSPACES_LIST >>',workspaces_list) 
        
        if not workspaces_list['success']:
            return False
        
        if len(workspaces_list['items'])==0:
            #Create a workspace as none exist
            
            response = self.CHC.create_workspace(
                context.portfolio,
                context.org,
                context.entity_type,
                context.entity_id,
                context.thread,payload
                ) 
            if not response['success']:
                return False
            # Regenerate workspaces_list
            workspaces_list = self.CHC.list_workspaces(
                context.portfolio,
                context.org,
                context.entity_type,
                context.entity_id,
                context.thread
                ) 

            print('UPDATED WORKSPACES_LIST >>>>',workspaces_list) 
            
            
        if not context.workspace_id:
            workspace = workspaces_list['items'][-1]
        else:
            for w in workspaces_list['items']:
                if w['_id'] == context.workspace_id:
                    workspace = w
                    
        print('Selected workspace >>>>',workspace) 
        if 'state' not in workspace:
            workspace['state'] = {
                "beliefs":{},
                "desire": '',           
                "intent": [],       
                "history": [],          
                "in_progress": None    
            }
            
        #2. Store the output in the workspace
        
        for key,output in changes.items():
            
            if key == 'belief':
                # output = {"date":"345"}
                if isinstance(output, dict):
                    workspace['state']['beliefs'] = {**workspace['state']['beliefs'], **output} #Creates a new dictionary that combines both dictionaries
                    
            
            if key == 'desire':
                if isinstance(output, str):
                    #workspace['state']['desires'].insert(0, output) # The inserted object goes to the first position (this will work as a stack)
                    workspace['state']['desire'] = output
                    
            if key == 'intent':
                if isinstance(output, dict):
                    workspace['state']['intent'] = output 
                    
            if key == 'belief_history':
                if isinstance(output, dict):
                    # Now update the belief history
                    for k, v in output.items():
                        history_event = {
                            'type':'belief',
                            'key': k,
                            'val': self.sanitize(v),
                            'time': datetime.now().isoformat()
                        }
                        workspace['state']['history'].append(history_event)
                        # The inserted object goes to the last position
                            
            if key == 'cache':
                print(f'Updating workspace cache:{output}')
                if 'cache' not in workspace : 
                    workspace['cache'] = {}
                if isinstance(output, dict):
                    for k,v in output.items():
                        workspace['cache'][k] = v
            
            if key == 'is_active':
                if isinstance(output, bool):
                    workspace['data'] = output # Output overrides existing data
                    
            if key == 'action':
                if isinstance(output, str):
                    workspace['state']['action'] = output # Output overrides existing data
                    
            if key == 'follow_up':
                if isinstance(output, dict):
                    workspace['state']['follow_up'] = output # Output overrides existing data
                    
            if key == 'slots':
                if isinstance(output, dict):
                    workspace['state']['slots'] = output # Output overrides existing data
                        
        #3. Broadcast updated workspace
        
        '''
            # WebSocket
            self.apigw_client.post_to_connection(
                ConnectionId=self.bridge['conn'],
                Data=json.dumps(doc)
            )
        '''
        
        
        try:
            #print(f'Sending Real Time Message to:{context.connection_id}')
            #doc = {'_out':workspace,'_type':'json'}
            #self.print_chat(doc,'json')
            
            #self.print_chat('Updating the workspace document...','text')
            # Update document in DB
            self.update_workspace_document(
                context.portfolio,
                context.org,
                workspace,
                workspace['_id']
                )
            
            return True
        
        
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
        
    
    
    def llm(self, prompt):
          
        try:
            
            # Create base parameters
            params = {
                'model': prompt['model'],
                'messages': prompt['messages'],
                'temperature': prompt['temperature']
            }
        
            # Add optional parameters if they exist
            if 'tools' in prompt:
                params['tools'] = prompt['tools']
            if 'tool_choice' in prompt:
                params['tool_choice'] = prompt['tool_choice']
                
            response = self.AI_1.chat.completions.create(**params) 
            
            # chat.completions.create might return an error if you include Decimal() as values
            # Object of type Decimal is not JSON serializable
            
            return response.choices[0].message
 
        
        except Exception as e:
            print(f"Error running LLM call: {e}")
            # Only print raw response if it exists 
            return False
    

    
    def new_chat_message_document(self,message):
        
        action = 'new_chat_message_document'
        print(f'Running: {action}')  
        #self.print_chat('Creating new chat document...','text')
        
        message_context = {}
        message_context['portfolio'] = self._get_context().portfolio
        message_context['org'] = self._get_context().org
        message_context['public_user'] = self._get_context().public_user
        message_context['entity_type'] = self._get_context().entity_type
        message_context['entity_id'] = self._get_context().entity_id
        message_context['thread'] = self._get_context().thread
          
        new_message = { "role": "user", "content": message }
        msg_wrap = {
            "_out":new_message,
            "_type":"text",
            "_id":str(uuid.uuid4()) # This is the Message ID
        }
        
        # Append new message to volatile context
        current_history = self._get_context().message_history
        current_history.append(new_message)
        self._update_context(message_history=current_history)
        
        # Append new message to permanent storage
        message_object = {}
        #message_object['message'] = message
        message_object['context'] = message_context
        #message_object['input'] = message
        #message_object['output'] = [msg_wrap]
        message_object['messages'] = [msg_wrap]
                 
        response = self.CHC.create_turn(
                        self._get_context().portfolio,
                        self._get_context().org,
                        self._get_context().entity_type,
                        self._get_context().entity_id,
                        self._get_context().thread,
                        message_object
                    )
        
        self._update_context(chat_id=response['document']['_id'])       
        print(f'Response:{response}')
    
        if 'success' not in response:
            return {'success':False,'action':action,'input':message,'output':response}
        
        return {'success':True,'action':action,'input':message,'output':response}
    
    
    
    def get_active_workspace(self):
        
        workspaces_list = self.CHC.list_workspaces(
            self._get_context().portfolio,
            self._get_context().org,
            self._get_context().entity_type,
            self._get_context().entity_id,
            self._get_context().thread
            ) 
        
        if not workspaces_list['success']:
            return False
        
        if len(workspaces_list['items'])==0:
            return False
        
        if not self._get_context().workspace_id:
            workspace = workspaces_list['items'][-1]
        else:
            for w in workspaces_list['items']:
                if w['_id'] == self._get_context().workspace_id:
                    workspace = w
                    
        return workspace
    
    
    def sanitize(self,obj):
        if isinstance(obj, list):
            return [self.sanitize(x) for x in obj]
        elif isinstance(obj, dict):
            return {k: self.sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            # Convert Decimal to int if it's a whole number, otherwise float
            return int(obj) if obj % 1 == 0 else float(obj)
        elif isinstance(obj, float):
            # Convert float to string
            return str(obj)
        elif isinstance(obj, int):
            # Keep integers as is
            return obj
        else:
            return obj
        
        
    def prune_history(self, history):
        """
        Prunes the history list to keep only the most recent value for each key while maintaining chronological order.
        Objects at the bottom of the list are newer.
        
        Args:
            history (list): List of belief objects with key, val, time, and type fields
            
        Returns:
            list: Pruned history list with only the most recent value for each key
        """
        # Create a dictionary to track the most recent value for each key
        latest_values = {}
        
        # First pass: identify the most recent value for each key
        for item in history:
            key = item['key']
            latest_values[key] = item
        
        # Second pass: create new list maintaining original order but only including latest values
        pruned_history = []
        seen_keys = set()
        
        # Iterate through history in reverse to maintain chronological order
        for item in reversed(history):
            key = item['key']
            if key not in seen_keys:
                pruned_history.append(item)
                seen_keys.add(key)
        
        # Reverse back to maintain original order (newest at bottom)
        return list(reversed(pruned_history))
    
    
    def string_from_object(self, object: dict) -> str:
        """
        Converts a dictionary into a formatted string.
        
        Args:
            object (dict): Dictionary containing key-value pairs
            
        Returns:
            str: Formatted string with key-value pairs separated by commas
            
        Example:
            Input: {"origin": "NYC", "destination": "SF", "departure_date": "2025-06-20", "guest_count": 4}
            Output: "origin = NYC, destination = SF, departure_date = 2025-06-20, guest_count = 4"
        """
        if not object:
            return ""
            
        formatted_pairs = []
        for key, value in object.items():
            # Convert value to string and handle different types appropriately
            if isinstance(value, (int, float)):
                formatted_value = str(value)
            elif isinstance(value, str):
                formatted_value = value
            else:
                formatted_value = str(value)
                
            formatted_pairs.append(f"{key} = {formatted_value}")
            
        return ", ".join(formatted_pairs)
    
    #NOT USED
    def format_object_to_slash_string(self, obj: dict) -> str:
        """
        Converts an object into a string with values separated by slashes.
        If a value is not a string, it will be replaced with an empty space.
        Keys are sorted alphabetically to ensure consistent output regardless of input order.
        
        Args:
            obj (dict): Dictionary containing key-value pairs
            
        Returns:
            str: Formatted string with values separated by slashes
            
        Example:
            Input: {"people": "4", "time": "16:00", "date": "2025-06-04"}
            Output: "2025-06-04/4/16:00"
        """
        if not obj:
            return ""
            
        values = []
        # Sort keys alphabetically
        for key in sorted(obj.keys()):
            value = obj[key]
            if isinstance(value, str):
                values.append(value)
            else:
                values.append("")
                
        return "/".join(values)
    
    def clean_json_response(self, response):
        """
        Cleans and validates a JSON response string from LLM.
        
        Args:
            response (str): The raw JSON response string from LLM
            
        Returns:
            dict: The parsed JSON object if successful
            None: If parsing fails
            
        Raises:
            json.JSONDecodeError: If the response cannot be parsed as JSON
        """
        try:
            # Clean the response by ensuring property names are properly quoted
            #cleaned_response = response.strip() 
            cleaned_response = response
            # Remove any comments (both single-line and multi-line)
            cleaned_response = re.sub(r'//.*?$', '', cleaned_response, flags=re.MULTILINE)  # Remove single-line comments
            cleaned_response = re.sub(r'/\*.*?\*/', '', cleaned_response, flags=re.DOTALL)  # Remove multi-line comments
            
            # First try to parse as is
            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError:
                pass
                
            # If that fails, try to fix common issues
            # Handle unquoted property names at the start of the object
            cleaned_response = re.sub(r'^\s*{\s*(\w+)(\s*:)', r'{"\1"\2', cleaned_response)
            
            # Handle unquoted property names after commas
            cleaned_response = re.sub(r',\s*(\w+)(\s*:)', r',"\1"\2', cleaned_response)
            
            # Handle unquoted property names after newlines
            cleaned_response = re.sub(r'\n\s*(\w+)(\s*:)', r'\n"\1"\2', cleaned_response)
            
            # Replace single quotes with double quotes for property names
            cleaned_response = re.sub(r'([{,]\s*)\'(\w+)\'(\s*:)', r'\1"\2"\3', cleaned_response)
            
            # Replace single quotes with double quotes for string values
            # This regex looks for : 'value' pattern and replaces it with : "value"
            cleaned_response = re.sub(r':\s*\'([^\']*)\'', r': "\1"', cleaned_response)
            
            # Remove spaces between colons and boolean values
            cleaned_response = re.sub(r':\s+(true|false|True|False)', r':\1', cleaned_response)
            
            # Remove trailing commas in objects and arrays
            # This regex will match a comma followed by whitespace and then a closing brace or bracket
            cleaned_response = re.sub(r',(\s*[}\]])', r'\1', cleaned_response)
            
            # Remove any timestamps in square brackets
            cleaned_response = re.sub(r'\[\d+\]\s*', '', cleaned_response)
            
            # Try to parse the cleaned response
            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                print(f"First attempt failed. Error: {e}")
                #print(f"Cleaned response type: {type(cleaned_response)}")
                #print(f"Cleaned response length: {len(cleaned_response)}")
                #print(f"Cleaned response content: '{cleaned_response}'")
                
                # If first attempt fails, try to fix the raw field specifically
                # Find the raw field and ensure it's properly formatted
                raw_match = re.search(r'"raw":\s*({[^}]+})', cleaned_response)
                if raw_match:
                    raw_content = raw_match.group(1)
                    # Convert single quotes to double quotes in the raw content
                    raw_content = raw_content.replace("'", '"')
                    # Replace the raw field with the cleaned version
                    cleaned_response = cleaned_response[:raw_match.start(1)] + raw_content + cleaned_response[raw_match.end(1):]
                
                #print(f"After raw field cleanup - content: '{cleaned_response}'")
                return json.loads(cleaned_response)
        
                
        except json.JSONDecodeError as e:
            print(f"Error parsing cleaned JSON response: {e}")
            #print(f"Original response: {response}")
            #print(f"Cleaned response: {cleaned_response}")
            raise

    def _convert_to_dict(self, obj):
        """
        Recursively converts an OpenAI response object to a dictionary.
        
        Args:
            obj: The object to convert (can be ChatCompletionMessage, ChatCompletionMessageToolCall, etc.)
            
        Returns:
            dict: The converted dictionary
        """
        if hasattr(obj, '__dict__'):
            return {key: self._convert_to_dict(value) for key, value in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [self._convert_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._convert_to_dict(value) for key, value in obj.items()}
        else:
            return obj
        
        
    def remove_outer_escape(self, double_escaped_string):
        """
        Removes the outer escape from a double-escaped JSON string.
        
        Args:
            double_escaped_string (str): A string that has been escaped twice
            
        Returns:
            str: The cleaned JSON string, or None if parsing fails
            
        Example:
            Input: '"{\\"raw_document\\":\\"Wood Property\\\\n1/25 Wellington Street...\\"}"'
            Output: '{"raw_document": "Wood Property\n1/25 Wellington Street..."}'
        """
        try:
            # First, parse the outer JSON string to get the inner escaped string
            outer_parsed = json.loads(double_escaped_string)
            
            # Then parse the inner string to get the actual JSON object
            if isinstance(outer_parsed, str):
                inner_parsed = json.loads(outer_parsed)
                # Return the cleaned JSON as a string
                return json.dumps(inner_parsed)
            else:
                # If it's already a dict, convert back to string
                return json.dumps(outer_parsed)
                
        except json.JSONDecodeError as e:
            print(f"Error parsing double-escaped JSON: {e}")
            return None
        

    def validate_interpret_openai_llm_response(self, raw_response: dict) -> tuple[bool, str]:
        """
        Validates that the LLM response follows the expected format.
        
        Args:
            response (dict): The parsed JSON response from the LLM
        """
        action = 'validate_interpret_openai_llm_response'
        # Convert OpenAI response object to dictionary if needed
        response = self._convert_to_dict(raw_response)     
        
        # Check if response has required 'role' field
        if 'role' not in response:
            return {"success":False,"action":action,"input":response,"output": "Response missing required 'role' field"}
            
        # Check if role is 'assistant'
        if response['role'] != 'assistant':
            return {"success":False,"action":action,"input":response,"output":"Response role must be 'assistant'"}
            
        # Check if response has either 'content' or 'tool_calls'
        has_content = 'content' in response and response['content'] is not None
        has_tool_calls = 'tool_calls' in response and response['tool_calls'] is not None
        
        if not (has_content or has_tool_calls):
            return {"success":False,"action":action,"input":response,"output": "Response must have either non-null 'content' or non-null 'tool_calls'"}
            
        if has_content and has_tool_calls:
            # If this happens, remove content so the message is still compliant
            response['content'] = ''
            #return {"success":False,"action":action,"input":response,"output": "Response cannot have both 'content' and 'tool_calls'"}
            
        # If it's a tool call, validate the tool_calls structure
        if has_tool_calls:
            if not isinstance(response['tool_calls'], list):
                return {"success":False,"action":action,"input":response,"output": "'tool_calls' must be a list"}
                
            for tool_call in response['tool_calls']:
                if not isinstance(tool_call, dict):
                    return {"success":False,"action":action,"input":response,"output": "Each tool call must be a dictionary"}
                    
                required_fields = ['id', 'type', 'function']
                for field in required_fields:
                    if field not in tool_call or tool_call[field] is None:
                        return {"success":False,"action":action,"input":response,"output": f"Tool call missing required field '{field}' or field is null"}
                        
                if tool_call['type'] != 'function':
                    return {"success":False,"action":action,"input":response,"output": "Tool call type must be 'function'"}
                    
                if not isinstance(tool_call['function'], dict):
                    return {"success":False,"action":action,"input":response,"output": "Tool call 'function' must be a dictionary"}
                    
                function_required_fields = ['name', 'arguments']
                for field in function_required_fields:
                    if field not in tool_call['function'] or tool_call['function'][field] is None:
                        return {"success":False,"action":action,"input":response,"output": f"Tool call function missing required field '{field}' or field is null"}
                        
                # Validate that arguments is a valid JSON string
                try:
                    if isinstance(tool_call['function']['arguments'], str):
                        json.loads(tool_call['function']['arguments'])
                except json.JSONDecodeError:
                    # Try to fix double-escaped JSON
                    escape_result = self.remove_outer_escape(tool_call['function']['arguments'])
                    if escape_result:
                        # Validate the cleaned result
                        try:
                            json.loads(escape_result)
                            tool_call['function']['arguments'] = escape_result
                        except json.JSONDecodeError:
                            return {"success":False,"action":action,"input":response,"output": "Tool call arguments must be a valid JSON string after cleaning"}
                    else:
                        return {"success":False,"action":action,"input":response,"output": "Tool call arguments must be a valid JSON string"}
                    
        # If it's a content response, validate content is a string
        if has_content and not isinstance(response['content'], str):
            return {"success":False,"action":action,"input":response,"output":"Content must be a string"}
            
        return {"success":True,"action":action,"output":response}

    def clear_tool_message_content(self, message_list, recent_tool_messages=1):
        """
        Clear content from all tool messages except the last x ones.
        This prevents overwhelming the LLM with tool output history.
        
        Args:
            message_list: List of messages to process
            recent_tool_messages: Number of recent tool messages to keep with content (default: 1)
        """
        print(f'Raw message_list:{message_list}')
        # {'success': True, 'action': 'get_message_history', 'input': '531fdfa8-9f60-4c8d-b046-6fa06d6f2a76', 'output': [{'content': "I'm looking for a hotel", 'role': 'user'}]}
        # Find the indices of the last x tool messages
        tool_indices = []
        for i in range(len(message_list) - 1, -1, -1):
            if message_list[i].get('role') == 'tool':
                tool_indices.append(i)
                if len(tool_indices) >= recent_tool_messages:
                    break
        
        # Clear content from all tool messages except the last x ones
        for i, message in enumerate(message_list):
            if message.get('role') == 'tool' and i not in tool_indices:
                print(f'Found a tool message:{message}')
                # Actually clear the content (set to empty string)
                message['content'] = ""
            else:
                # Convert complex content to string format for OpenAI API
                if isinstance(message.get('content'), list):
                    # If content is an array, sanitize and convert it to a JSON string
                    sanitized_content = self.sanitize(message['content'])
                    message['content'] = json.dumps(sanitized_content)
                elif isinstance(message.get('content'), dict):
                    # If content is an object, sanitize and convert it to a JSON string
                    sanitized_content = self.sanitize(message['content'])
                    message['content'] = json.dumps(sanitized_content)
                else:
                    # If content is already a string or other type, sanitize and convert to string
                    sanitized_content = self.sanitize(message.get('content', ''))
                    message['content'] = str(sanitized_content)
                
        print(f'Cleared tool message content:{message_list}')
        
        return message_list

    # -------------------------------------------------------- LOOP FUNCTIONS
    
    
    def pre_process_message(self, message):
        """
        Combined function that processes a message through multiple stages in a single LLM call:
        1. Perception and interpretation
        2. Information processing
        3. Fact extraction
        4. Desire detection
        5. Action matching
        """
        action = 'pre_process_message'
        self.print_chat('Pre-processing message...', 'text')
        
        try:        
            # Get current time and date
            current_time = datetime.now().strftime("%Y-%m-%d")
            
            # Get available actions
            list_actions = self._get_context().list_actions
             
            dict_actions = {}
            for a in list_actions:
                dict_actions[a['key']] = {
                    'goal': a.get('goal', ''),
                    'key': a.get('key', ''),
                    'utterances': a.get('utterances', ''),
                    'slots': a.get('slots', '')
                }
            
            # Get current workspace
            workspace = self.get_active_workspace()
            current_action = workspace.get('state', {}).get('action', '') if workspace else ''
            last_belief = workspace.get('state', {}).get('belief', {}) if workspace else {}
            belief_history = workspace.get('state', {}).get('history', []) if workspace else []
                    
            # Clean and prepare belief history if provided
            cleaned_belief_history = self.sanitize(belief_history) if belief_history else []
            pruned_belief_history = self.prune_history(cleaned_belief_history) if cleaned_belief_history else []
            prompt_text = f"""
            You are a comprehensive message processing module for a BDI agent. Your task is to process a user message through multiple stages in a single pass.

            STAGE 1 - PERCEPTION AND INTERPRETATION:
            Extract structured information from the raw message:
            - Identify the user's intent
            - Extract key entities mentioned
            - Note any tools that might be needed
            - For each entity detected, create a belief history entry with:
            * type: "belief"
            * key: entity name
            * val: entity value
            * time: current timestamp

            STAGE 2 - INFORMATION PROCESSING:
            Enrich and normalize the extracted information:
            - Normalize values (e.g., convert "tomorrow" to full date)
            - Add derived information
            - Validate and standardize formats
            - Compare available beliefs with the slots required by the matched action
            - Identify missing beliefs by:
            * Checking each required slot from the matched action
            * Verifying if we have corresponding values in current beliefs
            * Considering both exact matches and semantic equivalents
            * Including slots that are required but not yet provided
            - Track missing beliefs that are essential for completing the current task

            STAGE 3 - FACT EXTRACTION:
            From the belief history, extract the most up-to-date facts:
            - Use the most recent value for each key
            - Combine with newly extracted information
            - Maintain chronological order

            STAGE 4 - DESIRE DETECTION:
            Analyze the combined information to determine the user's goal:
            - Consider the current action: {current_action}
            - Review the entire belief history to understand the ongoing conversation context
            - Consider the chronological progression of user's statements and preferences
            - Only change the previously detected desire if:
            * The new message explicitly states a different intention
            * The new message provides critical information that fundamentally changes the goal
            * The user explicitly requests to change their previous intention
            - If the new message only adds facts without changing intent, maintain the previous desire
            - Summarize the user's desire in a natural language sentence
            - Focus on the primary objective that has been consistent throughout the conversation

            STAGE 5 - ACTION MATCHING:
            Match the processed information with available actions:
            - Consider the current action: {current_action}
            - Only change the current action if:
            * The new message explicitly requests a different action
            * The new message's intent clearly conflicts with the current action
            * The user explicitly states they want to do something else
            - If the new message only adds information without changing intent:
            * Keep the current action
            * Use the message to fill missing slots
            * Update any relevant beliefs
            - Compare intent and beliefs with action descriptions
            - Consider the full belief history when matching
            - Select the most appropriate action
            - Provide confidence score

            Today's date is {current_time}

            ### Available Actions:
            {json.dumps(dict_actions, indent=2)}

            ### Current Belief:
            {json.dumps(last_belief, indent=2) if last_belief else "{}"}

            ### Belief History:
            {json.dumps(pruned_belief_history, indent=2) if pruned_belief_history else "[]"}

            ### User Message:
            {message}

            Return a JSON object with the following structure:
            {{
                "perception": {{
                    "intent": "string",
                    "entities": {{}},
                    "raw_text": "string",
                    "needs_tools": []
                }},
                "processed_info": {{
                    "enriched_entities": {{}},
                    "missing_beliefs": [],
                    "normalized_values": {{}}
                }},
                "facts": {{
                    // Key-value pairs of extracted facts
                }},
                "desire": "string",
                "action_match": {{
                    "confidence": 0-100,
                    "action": "string" // Use the key of the action,
                    "reasoning": "string",
                    "action_changed": boolean,
                    "change_reason": "string"
                }},
                "belief_history_updates": [
                    {{
                        "type": "belief",
                        "key": "string",
                        "val": "any",
                        "time": "ISO timestamp"
                    }}
                ]
            }}

            IMPORTANT RULES:
            1. Always use the most recent value for each fact
            2. Maintain all original information while enriching it
            3. Provide clear reasoning for action matching
            3b. Use the action key to indicate what action has been selected.
            4. Return valid JSON with all strings properly quoted
            5. For each new entity detected, create a belief history entry
            6. Use the belief history to inform action matching
            7. Include timestamps in ISO format for belief history entries
            8. Consider historical context when matching actions
            9. Only change the current action when explicitly requested or necessary
            10. Use new information to fill missing slots in the current action
            """
            prompt = {
                "model": self.AI_1_MODEL,
                "messages": [{ "role": "user", "content": prompt_text}],
                "temperature":0
            }
            response = self.llm(prompt)
            
            if not response.content:
                raise Exception('LLM response is empty')
                
            
            #print(f'PROCESS MESSAGE PROMPT >> {prompt}')
            result = self.clean_json_response(response.content)
            sanitized_result = self.sanitize(result)
            
            # Update workspace with the results
            if 'facts' in sanitized_result:
                self.mutate_workspace({'belief': sanitized_result['facts']})
            
            if 'desire' in sanitized_result:
                self.mutate_workspace({'desire': sanitized_result['desire']})
            
            if 'action_match' in sanitized_result and 'action' in sanitized_result['action_match']:
                # Check if action.key is used instead of action.name  
                self.mutate_workspace({'action': sanitized_result['action_match']['action']})
            
            # Update belief history with new entities
            if 'belief_history_updates' in sanitized_result:
                for update in sanitized_result['belief_history_updates']:
                    self.mutate_workspace({'belief_history': {update['key']: update['val']}})
            
            #self.print_chat(sanitized_result, 'json')
             
            return {
                'success': True,
                'action': action, 
                'input': message,
                'output': sanitized_result
            }
            
        except Exception as e:
            print(f"Error Pre-Processing message: {e}")
            # Only print raw response if it exists
            
            return {
                'success': False,
                'action': action,
                'input': message,
                'output': str(e)
            }
    
    
    
    def interpret(self,no_tools=False):
        
        action = 'interpret'
        self.print_chat('Interpreting message...', 'text')
        print('interpret')
        
        try:
            # We get the message history directly from the source of truth to avoid missing tool id calls. 
            message_list = self.get_message_history()
            
            print(f'Raw Message History: {message_list}')
            
            # Go through the message_list and replace the value of the 'content' attribute with an empty object when the role is 'tool'
            # Unless the last message it a tool response which the interpret function needs to process. 
            # The reason is that we don't want to overwhelm the LLM with the contents of the history of tool outputs. 
            
            # Clear content from all tool messages except the last one
            message_list = self.clear_tool_message_content(message_list['output'])
            
            print(f'Cleared Message History: {message_list}')
            
            
            # Get current time and date
            current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            
            # Workspace
            workspace = self.get_active_workspace()
            
            # Action  
            current_action = workspace.get('state', {}).get('action', '') if workspace else ''
            print(f'Current Action:{current_action}')
            
            action_instructions = '' 
            action_tools = ''
            list_actions = self._get_context().list_actions
            
            for a in list_actions:
                if a['key'] == current_action:
                    action_instructions = a['prompt_3_reasoning_and_planning']
                    if 'tools_reference' in a and a['tools_reference'] and a['tools_reference'] not in ['_','-','.']: 
                        action_tools = a['tools_reference']
                    break

            # Belief  
            current_beliefs = workspace.get('state', {}).get('beliefs', {}) if workspace else {}
            belief_str = 'Current beliefs: ' + self.string_from_object(current_beliefs)
            print(f'Current Belief:{belief_str}')
                
            #belief_history = workspace.get('state', {}).get('history', []) if workspace else []             
            #cleaned_belief_history = self.sanitize(belief_history) if belief_history else []
            #pruned_belief_history = self.prune_history(cleaned_belief_history) if cleaned_belief_history else []

            # Desire
            current_desire = workspace.get('state', {}).get('desire', '') if workspace else ''
            print(f'Current Desire:{current_desire}')
            
            # Meta Instructions
            meta_instructions = {}
            # Initial instructions
            meta_instructions['opening_message'] = "You are an AI assistant. You can reason over conversation history, beliefs, and goals."
            # Provide the current time
            meta_instructions['current_time'] = f'The current time is: {current_time}'
            # Message to answer questions from the belief system
            meta_instructions['answer_from_belief'] = "You can reason over the message history and known facts (beliefs) to answer user questions. If the user asks a question, check the history or beliefs before asking again."
                  
            # Message array
            messages = [
                { "role": "system", "content": meta_instructions['opening_message']}, # META INSTRUCTIONS
                { "role": "system", "content": meta_instructions['current_time']}, # CURRENT TIME         
                { "role": "system", "content": action_instructions}, # CURRENT ACTIONS
                { "role": "system", "content": belief_str }, # BELIEF SYSTEM
                { "role": "system", "content": meta_instructions['answer_from_belief']}
            ]
            
            # Add the incoming messages
            for msg in message_list:      
                messages.append(msg)       
                
            # Initialize approved_tools with default empty list
            approved_tools = []
                
            # Request asking the recommended tools for this action
            if action_tools and not no_tools:
                messages.append({ "role": "system", "content":f'In case you need them, the following tools are recommended to execute this action: {json.dumps(action_tools)}'})  
                
                approved_tools = [tool.strip() for tool in action_tools.split(',')]
                    
            # Tools           
            '''   
            tool.input should look like this in the database:
                
                {
                    "origin": { 
                        "type": "string",
                        "description": "The departure city code or name",
                        "required":true
                    },
                    "destination": { 
                        "type": "string", 
                        "description": "The arrival city code or name",
                        "required":true
                    }
                }
            '''
            
            
            if no_tools:                
                list_tools = None      
                   
            else:         
                list_tools_raw = self._get_context().list_tools
                
                print(f'List Tools:{list_tools_raw}')
                
                list_tools = [] 
                for t in list_tools_raw:
                    
                    if t.get('key') in approved_tools:
                        # Parse the escaped JSON string into a Python object
                        try:
                            tool_input = json.loads(t.get('input', '[]'))
                        except json.JSONDecodeError:
                            print(f"Invalid JSON in tool input for tool {t.get('key', 'unknown')}. Using empty array.")
                            tool_input = []
                        
                        dict_params = {}
                        required_params = []
                        
                        # Handle new format: array of objects with name, hint, required
                        if isinstance(tool_input, list):
                            for param in tool_input:
                                if isinstance(param, dict) and 'name' in param and 'hint' in param:
                                    param_name = param['name']
                                    param_hint = param['hint']
                                    param_required = param.get('required', False)
                                    
                                    dict_params[param_name] = {
                                        'type': 'string',
                                        'description': param_hint
                                    }
                                    
                                    if param_required:
                                        required_params.append(param_name)
                        # Handle old format for backward compatibility
                        elif isinstance(tool_input, dict):
                            for key, val in tool_input.items():
                                dict_params[key] = {'type': 'string', 'description': val}
                                required_params.append(key)
                                
                        print(f'Required parameters:{required_params}')
                            
                        tool = {
                            'type': 'function',
                            'function': {
                                'name': t.get('key', ''),
                                'description': t.get('goal', ''),
                                'parameters': {
                                    'type': 'object',
                                    'properties': dict_params,
                                    'required': required_params
                                }
                            }    
                        }
                        
                        #print(f'Tool:{tool}')       
                        list_tools.append(tool)          
                        #print(f'List Tools:{list_tools}')
                    
                    
            # Prompt
            prompt = {
                    "model": self.AI_1_MODEL,
                    "messages": messages,
                    "tools": list_tools,
                    "temperature":0,
                    "tool_choice": "auto"
                }
            
            
            prompt = self.sanitize(prompt)
            
            print(f'RAW PROMPT >> {prompt}')
    
            response = self.llm(prompt)
            
            print(f'RAW RESPONSE >> {response}')
          
            
            if not response:
                return {
                    'success': False,
                    'action': action,
                    'input': '',
                    'output': response
                }
                
            
            validation = self.validate_interpret_openai_llm_response(response)
            if not validation['success']:
                return {
                    'success': False,
                    'action': action,
                    'input': response,
                    'output': validation
                }
            
            validated_result = validation['output']
           
            # Saving : A) The tool call, or B) The message to the user
            self.save_chat(validated_result)  
                      
            return {
                'success': True,
                'action': action,
                'input': prompt,
                'output': validated_result
            }
            
        except Exception as e:
            print(f"Error in interpret() message: {e}")
            return {
                'success': False,
                'action': action,
                'input': '',
                'output': str(e)
            }
    
        
        
    ## Execution of Intentions
    def act(self,plan):
        action = 'act'
        
       
        '''
        
        'plan' is the response from the LLM. 
        'plan' has this format:
        
         plan = {
            'tool_calls':[
                {
                  'id': STRING
                  'function':{
                      'name': STRING
                      'arguments': OBJECT
                  }  
                }
                
            ] 
        }
        
        '''
        
        
        
        list_tools_raw = self._get_context().list_tools
        
        list_handlers = {}
        for t in list_tools_raw:
            list_handlers[t.get('key', '')] = t.get('handler', '')
            
        self._update_context(list_handlers=list_handlers)
    
        """Execute the current intention and return standardized response"""
        try:
            
            tool_name = plan['tool_calls'][0]['function']['name']
            params = plan['tool_calls'][0]['function']['arguments']
            if isinstance(params, str):
                params = json.loads(params)
            tid = plan['tool_calls'][0]['id']
            
            print(f'tid:{tid}')

            if not tool_name:
                raise ValueError("❌ No tool name provided in tool selection")
                
            print(f"Selected tool: {tool_name}")
            self.print_chat(f'Calling tool {tool_name} with parameters {params} ', 'text')
            #print(f"Reasoning: {reasoning}")
            print(f"Parameters: {params}")
            #print(f"Filter: {filter}")
            #print(f"special_request: {special_request}")
            
            # Send the filter along the parameters. The handler will use it. 
            #params['_filter'] = filter

            #list_handlers = self._get_context().list_handlers
            
            # Check if handler exists
            if tool_name not in list_handlers:
                error_msg = f"❌ No handler found for tool '{tool_name}'"
                print(error_msg)
                self.print_chat(error_msg, 'text')
                raise ValueError(error_msg)
            
            # Check if handler is an empty string
            if list_handlers[tool_name] == '':
                error_msg = f"❌ Handler is empty"
                print(error_msg)
                self.print_chat(error_msg, 'text')
                raise ValueError(error_msg)
                
            # Check if handler has the right format
            handler_route = list_handlers[tool_name]
            parts = handler_route.split('/')
            if len(parts) != 2:
                error_msg = f"❌ {tool_name} is not a valid tool."
                print(error_msg)
                self.print_chat(error_msg, 'text')
                raise ValueError(error_msg)
            

            portfolio = self._get_context().portfolio
            org = self._get_context().org
            
            params['_portfolio'] = self._get_context().portfolio
            params['_org'] = self._get_context().org
            params['_entity_type'] = self._get_context().entity_type
            params['_entity_id'] = self._get_context().entity_id
            params['_thread'] = self._get_context().thread
            
  
            #self.print_chat(f'Calling {handler_route} ','text') 
            print(f'Calling {handler_route} ') 
            
            response = self.SHC.handler_call(portfolio,org,parts[0],parts[1],params)
            
            print(f'Handler response:{response}')

            if not response['success']:
                return {'success':False,'action':action,'input':params,'output':response}

            # The response of every handler always comes nested 
            clean_output = response['output']['output']['output'][-1]['output']
            clean_output_str = json.dumps(clean_output, cls=DecimalEncoder)
            
            interface = None
            # The handler determines the interface
            if 'interface' in response['output']['output']['output'][-1]:
                interface = response['output']['output']['output'][-1]['interface']

               
            
            tool_out = {
                    "role": "tool",
                    "tool_call_id": f'{tid}',
                    "content": clean_output_str,
                    "tool_calls":False
                }
            

            # Save the message after it's created
            if interface:
                self.save_chat(tool_out,interface=interface)
            else:
                self.save_chat(tool_out)
                
            
            print(f'flag3')
            
            # Results coming from the handler
            self._update_context(execute_intention_results=tool_out)
            
            print(f'flag4')
            
            # Save handler result to workspace
            
            # Turn an object like this one: {"people":"4","time":"16:00","date":"2025-06-04"}
            # Into a string like this one: "4/16:00/2026-06-04"
            # If the value of each key is not a string just output an empty space in its place
            #params_str = self.format_object_to_slash_string(params)
            index = f'irn:tool_rs:{handler_route}' 
            tool_input = plan['tool_calls'][0]['function']['arguments'] 
            #input is a serialize json, you need to turn it into a python object before inserting it into the value dictionary
            tool_input_obj = json.loads(input) if isinstance(input, str) else tool_input
            value = {'input': tool_input_obj, 'output': clean_output}
            self.mutate_workspace({'cache': {index:value}})
            
            print(f'flag5')
            
            #print(f'message output: {tool_out}')
            print("✅ Tool execution complete.")
            
            return {"success": True, "action": action, "input": plan, "output": tool_out}
                    
        except Exception as e:

            error_msg = f"❌ Execute Intention failed. @act trying to run tool:'{tool_name}': {str(e)}"
            self.print_chat(error_msg,'text') 
            print(error_msg)
            self._update_context(execute_intention_error=error_msg)
            
            error_result = {
                "success": False, "action": action,"input": plan,"output": str(e)    
            }
            
            self._update_context(execute_intention_results=error_result)
            return error_result
        
        
        
    
    
    
    
    
    
    
    # EXAMPLE: PROMPT TO EXTRACT BELIEFS 
    '''
    You are an AI assistant that extracts the user's intent and relevant information from a conversation.

    Below is the message history between the user and assistant. Your task is to return a list of beliefs — each belief is a key-value pair that represents something the user has stated or implied.

    Only extract **factual and relevant** information that could help accomplish a task. Do not include the assistant's own responses unless they reflect a confirmed fact.

    Use this JSON format:
    [
    { "key": "origin", "value": "São Paulo", "source": "user" },
    { "key": "destination", "value": "Recife", "source": "user" },
    { "key": "departure_date", "value": "2025-06-12", "source": "user" }
    ]

    If a value is unknown or missing, do not include it.

    Conversation:
    ---
    User: Quero um voo barato para Recife.
    Assistant: Claro! De onde você está saindo e para qual data?
    User: De São Paulo, dia 12 de junho.
    ---
        '''
        
        
        # EXAMPLE: PROMPT THAT SHOWS OPTIMAL FLOW
    '''
    `
            - answer in brazilian portuguese
            - you help users book flights!
            - keep your responses limited to a sentence.
            - DO NOT output lists.
            - after every tool call, pretend you're showing the result to the user and keep your response limited to a phrase.
            - today's date is ${new Date().toLocaleDateString()}.
            - ask follow up questions to nudge user into the optimal flow
            - ask for any details you don't know, like name of passenger, etc.'
            - C and D are aisle seats, A and F are window seats, B and E are middle seats
            - assume the most popular airports for the origin and destination
            - here's the optimal flow
            - search for flights
            - choose flight
            - select seats
            - create reservation (ask user whether to proceed with payment or change reservation)
            - authorize payment (requires user consent, wait for user to finish payment and let you know when done)
            - display boarding pass (DO NOT display boarding pass without verifying payment)
            '
        `
    '''
    
    
    
    def run(self,payload):
        # Initialize a new request context
        action = 'run'
        print(f'Running: {action}')
        print(f'Payload: {payload}')  
        
        context = RequestContext()
        
        # Update context with payload data
        if 'connectionId' in payload:
            context.connection_id = payload["connectionId"]
                  
        if 'portfolio' in payload:
            context.portfolio = payload['portfolio']
        else:
            return {'success':False,'action':action,'input':payload,'output':'No portfolio provided'}
        
        if 'org' in payload:
            context.org = payload['org']
        else:
            context.org = '_all' #If no org is provided, we switch the Agent to portfolio level
            
        if 'public_user' in payload:
            context.public_user = payload['public_user']
                    
        if 'entity_type' in payload:
            context.entity_type = payload['entity_type']
        else:
            return {'success':False,'action':action,'input':payload,'output':'No entity_type provided'}
        
        if 'entity_id' in payload:
            context.entity_id = payload['entity_id']
        else:
            return {'success':False,'action':action,'input':payload,'output':'No entity_id provided'}
        
        if 'thread' in payload:
            context.thread = payload['thread']
        else:
            return {'success':False,'action':action,'input':payload,'output':'No thread provided'}
            
        if 'workspace' in payload:
            context.workspace_id = payload['workspace']
            
        # Get available actions and tools
        actions = self.DAC.get_a_b(context.portfolio, context.org, 'schd_actions')
        context.list_actions = actions['items']
        
        tools = self.DAC.get_a_b(context.portfolio, context.org, 'schd_tools')
        context.list_tools = tools['items']
        
        # Set the initial context for this turn
        self._set_context(context)
        
        results = []
         
        # Get the initial chat message history and put it in the context
        message_history = self.get_message_history()
        if not message_history['success']:
            return {'success':False,'action':action,'output':message_history}
            
        # Update context with message history
        self._update_context(message_history=message_history['output'])
        #print(f'FULL message history:{message_history}')
           
        try:
            
            # Step 0: Create thread/message document
            response_0 = self.new_chat_message_document(payload['data'])
            results.append(response_0)
            if not response_0['success']: 
                return {'success':False,'action':action,'output':results}
             
            # Step 0b: Pre-process message
            response_0b = self.pre_process_message(payload['data'])
            results.append(response_0b)
            if not response_0b['success']: 
                return {'success':False,'action':action,'output':results}
            
            
            loops = 0
            loop_limit = 6
            while loops < loop_limit:
                loops = loops + 1
                print(f'Loop iteration {loops}/{loop_limit}')
                
                # Step 1: Interpret. We receive the message from the user and we issue a tool command or another message       
                response_1 = self.interpret()
                results.append(response_1)
                if not response_1['success']:
                    # Something went wrong during message interpretation
                    return {'success':False,'action':action,'output':results}         
                
                # Check whether we need to run a tool
                if 'tool_calls' not in response_1['output'] or not response_1['output']['tool_calls']:
                    # No tool needs execution. 
                    # Most likely the agent is asking for more information to fill tool parameters. 
                    # Or agent is answering questions directly from the belief system.
                    self.print_chat(f'🤖','text')
                    return {'success':True,'action':action,'input':payload,'output':results}
                                
                else:
                    # Step 2: Act. Agent runs the tool
                    response_2 = self.act(response_1['output'])
                    results.append(response_2)
                    
                    
                    # Step 3: Check if answer needs to go out without LLM interpretation
                    #if 'direct_out' in response_2:
                        
                    
                    
                    
                    if not response_2['success']:
                        # Something went wrong during tool execution
                        return {'success':False,'action':action,'output':results}
                    
                    
                    
            
            #Gracious exit. Analyze the last tool run (act()) but you can't issue a new tool_call. 
            response_1 = self.interpret(no_tools=True)
            results.append(response_1)
            if not response_1['success']:
                    # Something went wrong during message interpretation
                    return {'success':False,'action':action,'output':results} 
            
            
            # If we reach here, we hit the loop limit
            print(f'Warning: Reached maximum loop limit ({loop_limit})')
            #self.print_chat(f'🤖⚠️  Can you re-formulate your request please?','text')
            return {'success':True,'action':action,'input':payload,'output':results}
                    

            
        except Exception as e:
            self.print_chat(e,'text')
            self.print_chat(f'🤖❌','text')
            return {'success':False,'action':action,'message':f'Run failed. Error:{str(e)}','output':results}

    

# Test block
if __name__ == '__main__':
    # Creating an instance
    pass

    
    
    
 
