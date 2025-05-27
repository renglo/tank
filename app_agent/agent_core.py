#
from app_data.data_controller import DataController
from app_docs.docs_controller import DocsController
from app_chat.chat_controller import ChatController
from app_schd.schd_controller import SchdController
from app_agent.agent_tools import ToolRegistry

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

from env_config import OPENAI_API_KEY,WEBSOCKET_CONNECTIONS

@dataclass
class RequestContext:
    """Request-scoped context for agent operations."""
    connection_id: str = ''
    portfolio: str = ''
    org: str = ''
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
        #if True:
        try:   
            
            openai_client = OpenAI(api_key=OPENAI_API_KEY,)
            print(f"OpenAI client initialized")
            #print(OPENAI_API_KEY)
        #else:
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            #print(OPENAI_API_KEY)
            openai_client = None
            
        self.DAC = DataController()
        self.DCC = DocsController()
        self.CHC = ChatController()
        self.SHC = SchdController()
        
        
        self.AI_1 = openai_client
        #self.AI_1_MODEL = "gpt-4" // This model does not support json_object response format
        self.AI_1_MODEL = "gpt-3.5-turbo" # Baseline model. Good for multi-step chats
        self.AI_2_MODEL = "gpt-4o-mini" # This model is not very smart
        
        try:
        
            self.apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=WEBSOCKET_CONNECTIONS)
        
        except Exception as e:
            print(f"Error initializing WebSocket client: {e}")
            self.apigw_client = None
        
        
        self.tools = ToolRegistry()

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

    def print_chat(self,output,type):
        # DataBase
        doc = {'_out':self.sanitize(output),'_type':type}
        self.update_chat_message_document(doc)
        
        context = self._get_context()
        if not context.connection_id:
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
        

        print("MUTATE_WORKSPACE>>",changes)
       
        #1. Get the workspace in this thread
        workspaces_list = self.CHC.list_workspaces(context.entity_type,context.entity_id,context.thread) 
        print('WORKSPACES_LIST >>',workspaces_list) 
        
        if not workspaces_list['success']:
            return False
        
        if len(workspaces_list['items'])==0:
            #Create a workspace as none exist
            response = self.CHC.create_workspace(context.entity_type,context.entity_id,context.thread,{}) 
            if not response['success']:
                return False
            # Regenerate workspaces_list
            workspaces_list = self.CHC.list_workspaces(context.entity_type,context.entity_id,context.thread) 

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
                            
            if key == 'data':
                if isinstance(output, dict):
                    workspace['data'].append(output) # The inserted object goes to the last position            
            
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
            print(f'Sending Real Time Message to:{context.connection_id}')
            #doc = {'_out':workspace,'_type':'json'}
            #self.print_chat(doc,'json')
            
            #self.print_chat('Updating the workspace document...','text')
            # Update document in DB
            self.update_workspace_document(workspace,workspace['_id'])
            
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            self._update_context(connection_id='')  # Clear the connection ID
            return False
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
        
        
         
        
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
                    

  
    # NOT USED  
    def run_prompt(self,payload):
        
        action = 'run_prompt'
        

        if not self.AI_1:
            return {'success':False,'message':'No LLM client found.'}
        
        
        query = {
            'portfolio':self._get_context().portfolio,
            'org':self._get_context().org,
            'ring':'agent_feedback',
            'operator':'begins_with',
            'value': payload['feedback_key'],
            'filter':{},
            'limit':999,
            'lastkey':None,
            'sort':'asc'
        }
        feedback_list = self.DAC.get_a_b_query(query)
        
        prompt_parts = {'system':{},'user':{}}
        prompt_parts['system']['content'] = payload['system_content']
        prompt_parts['user']['content'] = payload['user_content']
        
        # Get current time and date
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt_parts['system']['now'] = f'The current time and date is {current_time}'
          
        
        feedback_string = ""
        for fb in feedback_list['items']:
            if 'feedback' in fb:
                feedback_string += fb['feedback']+'\n'
                              
        prompt_parts['user']['feedback'] = feedback_string
        prompt_parts['user']['input'] = payload['user_input']
        
        prompt_parts['system']['input'] = f'The INPUT format is:{payload['input_template']}'
        prompt_parts['system']['output'] = f'The OUTPUT format is:{payload['output_template']}'
        
        
        messages = [
            {
                "role": "system",
                "content": f"{prompt_parts['system']['content']} \n {prompt_parts['system']['now']} "
            },
            {
                "role": "user",
                "content": f"{prompt_parts['user']['content']} \n {prompt_parts['user']['feedback']} \n {prompt_parts['user']['input']} "
            },
        ]
        
        print(f"PROMPT: {messages}")
        
        try: 
            chat_completion = self.AI_1.chat.completions.create(
                model=self.AI_1_MODEL, 
                messages=messages, 
                temperature=0,
                response_format={"type": "json_object"}
            )
        
            print(f'RAW LLM RESPONSE: {chat_completion}')        
            raw_content = chat_completion.choices[0].message.content.strip()
            try:
                self._update_context(completion_result=self.clean_json_response(raw_content))
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing LLM response: {e}"
                print(error_msg)
                return {'success':False,'action':action,'input':messages,'message':error_msg,'output':e}
                 
        except Exception as e:
            error_msg = f"Error occurred while calling LLM: {e}"
            print(error_msg)
            return {'success':False,'action':action,'input':messages,'message':error_msg,'output':e}
            
        return {'success':True,'action':action,'message':'Completion executed','input':messages,'output':self._get_context().completion_result}
    
    
    
    def llm(self, prompt):
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        response = self.AI_1.chat.completions.create(
            model=self.AI_1_MODEL, 
            messages=messages, 
            temperature=0
        )
        
        return response.choices[0].message.content.strip()
    
    
    
    # 1 NOT USED, 
    # Integrated into process_message()
    def perception_and_interpretation(self, message,last_belief):
        
        action = 'perception_and_interpretation'
        self.print_chat('Interpreting message and extracting information from it...','text')
        
        prompt = f"""
            You are a perception module for an intelligent agent. Your job is to interpret raw user input and extract structured information from it.

            Given the user's message, return a structured JSON object with the following fields:

            - "intent": what the user is trying to do (e.g., "book_flight", "cancel_reservation", etc.)
            - "entities": key pieces of information mentioned (e.g., destination, date, number of people)
            - "raw_text": the original message
            - "needs_tools": list of tools that might be needed to process this message, from:
                - "calendar": for normalizing dates like "tomorrow" or "next friday"
                - "calculator": for calculating total people including user
                - "web_search": for validating destinations
                - "knowledge_base": for looking up user preferences
                - "geolocation": for inferring location from IP

            Use the existing belief object as a reference. If there is a similar key in the belief for a piece of information, use it in the intent object
            Do not perform reasoning or fill in missing values. Just extract what is directly mentioned.
            Make sure to return valid JSON with all strings properly quoted.
            
            Current belief object: '{last_belief}' 

            User message: '{message}'
        """
        
        response = self.llm(prompt)
        try:
            result = self.clean_json_response(response)
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            print(f"perception_and_interpretation > Prompt: {prompt}")
            print(f"Perception_and_interpretation > Raw response: {response}")
            # Return a basic structure if parsing fails
            default_result = {
                "intent": "unknown",
                "entities": {},
                "raw_text": message,
                "needs_tools": []
            }
            
            return {'success':False,'action':action,'next':'finishing','input':message,'output':default_result}
            
            
        
        # If tools are needed, try to resolve them
        if "needs_tools" in result:
            for tool in result["needs_tools"]:
                if tool == "calendar" and "date" in result["entities"]:
                    normalized_date = self.tools.resolve("checkin_date", {"raw_date": result["entities"]["date"]})
                    if normalized_date:
                        result["entities"]["date"] = normalized_date
                
                elif tool == "calculator" and "people" in result["entities"]:
                    total_people = self.tools.resolve("num_people", {"raw_people": result["entities"]["people"]})
                    if total_people:
                        result["entities"]["total_people"] = total_people
                
                elif tool == "web_search" and "destination" in result["entities"]:
                    is_valid = self.tools.resolve("valid_destination", {"destination": result["entities"]["destination"]})
                    if is_valid is not None:
                        result["entities"]["is_valid_destination"] = is_valid
                
                elif tool == "knowledge_base" and "user_id" in result["entities"]:
                    preferences = self.tools.resolve("user_preferences", {"user_id": result["entities"]["user_id"]})
                    if preferences:
                        result["entities"]["preferences"] = preferences
                
                elif tool == "geolocation" and "ip_address" in result["entities"]:
                    location = self.tools.resolve("departure_city", {"ip_address": result["entities"]["ip_address"]})
                    if location:
                        result["entities"]["departure_city"] = location
        
        
        self.print_chat(result,'json')       
        next = 'process_information'
        return {'success':True,'action':action,'next':next,'input':message,'output':result}
    
    
    
    # 2 NOT USED
    # Integrated into process_message()
    def process_information(self, input):
        
        action = 'process_information'   
        print(f'Running:{action}')  
        self.print_chat('Enriching and normalizing the beliefs...','text')
          
        # Get current time and date
        current_time = datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
            You are an internal reasoning module for a BDI agent. Your input is a parsed perception output from a user's message.

            Your job is to:
            1. Preserve the original structure with intent, entities, raw_text, needs_tools, and date
            2. Enrich the entities by:
               - Normalizing values (e.g., convert "tomorrow" into a full date)
               - Adding derived information (e.g., if date is given, add day_of_week)
               - Validating and standardizing formats
            3. Identify any missing information required to act on the intent
            4. Return a JSON object with:
               - All original fields preserved
               - Enriched entities
               - List of missing_beliefs
               - Intent of this iteration
               - beliefs inside of a belief attribute

            Today's date is {current_time}.

            Example input:
            {{
                "intent": "order_food",
                "entities": {{
                    "food_item": "pizza",
                    "toppings": ["cheese", "anchovies"]
                }},
                "raw_text": "I want a pizza with cheese and anchovies",
                "needs_tools": ["web_search"],
                "date": "2025-04-19"
            }}
            
            

            Example output:
            {{
                "intent":"order_food"
                "beliefs": {{
                    "entities": {{
                        "food_item": "pizza",
                        "toppings": ["cheese", "anchovies"],
                        "order_type": "delivery",
                        "estimated_time": "30 minutes"
                    }},
                    "raw_text": "I want a pizza with cheese and anchovies",
                    "needs_tools": ["web_search"],
                    "date": "2025-04-19"
                }},
                "missing_beliefs": ["delivery_address"]
            }}

            IMPORTANT: Return ONLY valid JSON. Do not include any comments or explanations.
            Input: {input}
        """
        
        response = self.llm(prompt)
        try:
            parsed_response = self.clean_json_response(response)
            
            # Ensure the response has the required structure
            if not isinstance(parsed_response, dict):
                raise ValueError("Response is not a dictionary")
                
            if "beliefs" not in parsed_response:
                raise ValueError("Response missing 'beliefs' key")
            
            self.print_chat(parsed_response,'json')
            self.print_chat('Now, I will update the beliefs in the workspace','text')
            self.mutate_workspace({'belief_history':parsed_response['beliefs']['entities']})
            
            next = 'reasoning'
            return {'success':True,'action':action,'next':next,'input':input,'output':parsed_response}
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response in process_information: {e}")
            print(f"Raw response: {response}")
            return {'success':False,'action':action,'next':'finishing','input':input,'output':None}
    


    
    def detect_desire(self, belief):
        
        action = 'detect_desire'
        print(f'Running:{action}')
        
        
        prompt = f"""
        You are a desire detection module inside a BDI agent.

        You are given a belief object — a list of key-value updates representing user-provided information.

        Analyze the belief object and summarize the user's **desire** (their goal or objective) in a short natural language sentence.

        ### Belief:
        {json.dumps(belief, indent=2)}

        Return only the user's desire.
        """
        return self.llm(prompt).strip()
    
    
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
    
    
    def extract_facts(self, belief_history):
        
        action = 'extract_facts'
        print(f'Running:{action}')
        
        action = 'extract_facts'
        self.print_chat('Extracting facts from belief_history','text')
        
        cleaned_belief_history = self.sanitize(belief_history)
        pruned_belief_history = self.prune_history(cleaned_belief_history)
        
        prompt = f"""
        You are a fact extractor inside a BDI agent.

        Given the belief history (a sequence of user inputs), extract the structured information 
        that is relevant to getting the most accurate and up to date state of the belied system. 
        Return your result as a JSON object with key-value pairs.


        ### Belief History:
        {json.dumps(pruned_belief_history, indent=2)}

        IMPORTANT RULES:
        1. The belief history is ordered chronologically, with the most recent entries at the bottom
        2. When the same key appears multiple times, ALWAYS use the value from the most recent entry (the last one in the list)
        3. For example, if the history shows:
           - departure_city: "New York City" (earlier)
           - departure_city: "Denver" (later)
           You should use "Denver" as the departure_city value
        4. Don't leave fact behind. Every piece of information is important.
        

        Return a JSON object with accurate data, always using the most recent value for each key.
        """
        llm_result = self.llm(prompt)
        print('extract_facts>llm_prompt:',prompt)
        print('extract_facts>llm_result:',llm_result)
        try:
            facts = self.clean_json_response(llm_result)
            s_facts = self.sanitize(facts)
            print('extract_facts> sanitized facts:',s_facts)
            return s_facts
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response in extract_facts: {e}")
            return {}
    
    
    
    def match_action(self, belief, desire):
        
        action = 'match_action'
        print(f'Running:{action}')
        
        self.print_chat('Matching actions with beliefs...','text')
        
        #Trying to match an approved action to the current belief
        
        # Get an actions list from DB and include it in the desire detection prompt. 
        # Ask the agent to match the beliefs and history with an Action. 
        # If there is a match, try to pair beliefs with the action slots. 
        # Explicitly declare missing slots. Still capture additional data. 
        # If there is no Action match, keep gathering beliefs until there is a match.
        
        
        actions = self.DAC.get_a_b(self._get_context().portfolio, self._get_context().org, 'schd_actions')
        
        #Accumulate all actions in a single prompt that we are going to send to the LLM. 
        list_actions = {}
        for a in actions['items']:
            list_actions[a['key']] = {
                'goal':a.get('goal', ''),
                'name':a.get('name', ''),
                'utterances':a.get('utterances', ''),
                'slots':a.get('slots', '')
            }
            
        prompt = f"""
        You are a classifier agent in charge of selecting the Action that most closely matches the belief and desire.

        You are given a list of actions from which you are going to select the match (in a JSON object) — the key is the name of the action, the value is the object that describes the action.
        Each action object has the following attributes: 
            goal : A sentence explaining what the action accomplishes in the format "This action helps x achieve Y"
            name : The descriptive name of the action
            utterance: A series of examples of messages that would use this action
            slots: The data that is needed to be able to use this action. The agent compares the belief object with the slots to find a match.
        
        
        Analyze all available data and return the key of the action that matches the intent and beliefs. 
        
        Return a structured JSON object with the following fields:
         - confidence : A number from 0 to 100 indicating how confident you are on the action classification 0 = No confidence, 100 = Full confidence.
         - action : The action key
         
         
        Example output:
        {{
            "confidence: 80,
            "action":"book_a_flight"
        }}
        
        
        ### List of actions: 
        {json.dumps(list_actions)}
        
        ### Beliefs: 
        {json.dumps(belief)}
        
        ### Desire:
        {desire}
  
         
        
        """
        #print('Match Action prompt:',prompt)
        #response = self.llm(prompt).strip()
        #return response
    
    
        llm_result = self.llm(prompt)
       
        
        try:
            action = self.clean_json_response(llm_result)
            s_action = self.sanitize(action)
            print('match_action> sanitized facts:',s_action)
            return s_action
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response in match_action: {e}")
            return {'confidence': 0, 'action': None}
    
    
    

       
    #3
    def reasoning(self):
        
        action = 'reasoning'
        print(f'Running:{action}')
        
        try:
        
            workspace = self.get_active_workspace()
            print(workspace)
            

            
            # Extract facts from history based on detected desire
            belief = self.extract_facts(workspace['state']['history'])
            self.print_chat(belief,'json')
            self._update_context(belief=belief)
            self.mutate_workspace({'belief':belief})
            
            
            # Detect Desire based on belief history
            desire = self.detect_desire(belief)
            self.print_chat(desire,'text')
            self._update_context(desire=desire)
            self.mutate_workspace({'desire':desire})
                
            
            # Match Action with detected belief and desire
            act = self.match_action(belief,desire)
            self.print_chat(act,'json')
            self._update_context(action=act['action'])
            self.mutate_workspace({'action':act['action']})
            #next = 'complete_slots' if int(act['confidence']) > 80 else 'finishing'
            next = 'complete_slots'
            
            # Getting slots
            #response = self.load_action()
            #workspace_changes['slots'] = response['output']['slots']
        
            # Ask user to confirm that matched action is correct
            '''
            request = f'Can you confirm that the action you want to perform is to {action}?'
            self.print_chat(request,'text')
            follow_up = {
                'expected' : True,
                'callback' : 'complete_slots',
                'options' : ['yes','no'],
                'request' : request
            }           
            workspace_changes['follow_up'] = follow_up
            '''  
            
            
            return {'success':True,'action':action,'next':next,'input':workspace['state']['history'],'output':{'desire':desire,'belief':belief,'action':act}}
            
            
        except Exception as e:
            print(f"Error during reasoning: {e}")
            return {'success':False,'action':action,'input':workspace['state']['history'],'output':e}
            
    
            
        
    def confirm_action(self,user_response):
        
        action = "confirm_action"
        self.print_chat('Validating your response...','text')
        
        try:
            question = self._get_context().workspace['state']['follow_up']['request'] # THIS OBJECT IS NOT ACTIVELY UPDATED!!!! BE CAREFUL
            options = self._get_context().workspace['state']['follow_up']['options']
            
            prompt = f"""
                You are an agent that requests information via chat to help users complete tasks. 
                When the responses from the users come back to you, you need to figure out the following
                
                1. If the user answered the question you asked (instead of something different)
                2. If the answer makes sense. 
                
                Sometimes the user will answer in a different way than expected but the answer will still be valid. 
                For example:
                - Instead of "yes", they might say "Sure", "ok", "that's fine", "absolutely", "of course", "as long as the sun comes out", etc.
                - Instead of "no", they might say "nope", "never", "not at all", "if hell freezes", "over my dead body", etc.
                
                For context, here is the question that you asked: {question}
                And here is the list of generic answers that the user is expected to respond with: {options}
                
                The **status** declares the state of the response according to the following rules:
                a. If it was possible to match the response to an item in the list of generic answers (yes or no)
                   status = 'valid'
                b. If it was not possible to match the response
                   status = 'invalid'
                
                The **sentiment** declares what is the tone of the answer. For example: formal, ironic, violent, etc
                
                Given the user's response and status, return a structured JSON object with the following fields:
                
                - "status": **Status** of the response according to the rules indicated above
                - "normalized_answer": The match to the existing list of generic answers (must be either "yes" or "no")
                - "sentiment": The **sentiment** detected in the response
                - "raw_answer": {user_response}

                Do not perform reasoning or fill in missing values. Just answer what is directly mentioned.
                Make sure to return valid JSON with all strings properly quoted.

                User response: '{user_response}'
            """
            
            response = self.llm(prompt)
        
            print(f"confirm_action > Raw prompt: {prompt}")
            print(f"confirm_action > Raw response: {response}")
            result = self.clean_json_response(response)
            
            workspace_changes = {}
            
            # Resetting follow_up object
            if result['status']=='valid':    
                workspace_changes['follow_up'] = {
                    'expected' : False,
                    'callback' : '',
                    'options' : '',
                    'request' : ''
                }  
            else:
                workspace_changes['action'] = ''    
                 

            #self.print_chat('Updating workspace with response result','text')
            self.mutate_workspace(workspace_changes)
            
         
            
        except json.JSONDecodeError as e:
            print(f"Error creating prompt or parsing LLM response: {e}")
            return {'success':False,'action':action,'input':user_response,'output':e}
        
        self.print_chat(result,'json')
        
        
            
        
        return {'success':True,'action':action,'input':user_response,'output':result}
            
        
        
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
            cleaned_response = response.strip() 
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
                print(f"Cleaned response type: {type(cleaned_response)}")
                print(f"Cleaned response length: {len(cleaned_response)}")
                print(f"Cleaned response content: '{cleaned_response}'")
                
                # If first attempt fails, try to fix the raw field specifically
                # Find the raw field and ensure it's properly formatted
                raw_match = re.search(r'"raw":\s*({[^}]+})', cleaned_response)
                if raw_match:
                    raw_content = raw_match.group(1)
                    # Convert single quotes to double quotes in the raw content
                    raw_content = raw_content.replace("'", '"')
                    # Replace the raw field with the cleaned version
                    cleaned_response = cleaned_response[:raw_match.start(1)] + raw_content + cleaned_response[raw_match.end(1):]
                
                print(f"After raw field cleanup - content: '{cleaned_response}'")
                return json.loads(cleaned_response)
        
                
        except json.JSONDecodeError as e:
            print(f"Error parsing cleaned JSON response: {e}")
            print(f"Original response: {response}")
            print(f"Cleaned response: {cleaned_response}")
            raise

    def complete_slots(self):
        
        action = 'complete_slots'
        self.print_chat('Looking for missing data...','text')
        
        # Get current workspace
        workspace = self.get_active_workspace()
        if not workspace:
            return {'success': False, 'action': action, 'message': 'No active workspace found'}
        
        # Get current action and its details
        current_action = workspace.get('state', {}).get('action', '')
        if not current_action:
            return {'success': False, 'action': action, 'message': 'No action found in workspace'}
            
        # Get action details from database
        actions = self.DAC.get_a_b(self._get_context().portfolio, self._get_context().org, 'schd_actions')
        action_details = None
        for a in actions['items']:
            if a['key'] == current_action:
                action_details = a
                break
                
        if not action_details:
            error_msg = f'Action: {current_action} not found in database'
            self.print_chat(error_msg,'text')
            return {'success': False, 'action': action, 'message': error_msg}
            
        # Get current beliefs and history
        current_beliefs = workspace.get('state', {}).get('beliefs', {})
        belief_history = workspace.get('state', {}).get('history', [])
        
        # Clean and prepare belief history
        cleaned_current_beliefs = self.sanitize(current_beliefs)
        
        cleaned_belief_history = self.sanitize(belief_history)
        pruned_belief_history = self.prune_history(cleaned_belief_history)
        
        try:
            prompt = f"""
                You are an agent that checks if all required slots (parameters) for an action are filled with valid data.

                CURRENT CONTEXT:
                - Action: {current_action}
                - Action Description: {action_details.get('goal', '')}
                - Required slots: {json.dumps(action_details.get('slots', {}), indent=2)}
                - Current Beliefs: {json.dumps(cleaned_current_beliefs, indent=2)}
                - Belief History: {json.dumps(pruned_belief_history, indent=2)}

                SLOT MATCHING RULES:
                1. Look for semantic matches between slot names and belief keys, not just exact matches
                2. Consider variations and synonyms (e.g., "number_of_passengers" matches "number_of_people", "passengers", "people_count")
                3. Look for related concepts (e.g., "departure_city" matches "origin", "from_city", "starting_location")
                4. Consider plural/singular forms and compound words (e.g., "departure_date" matches "departure", "date", "departuredate")
                5. Check both current beliefs and belief history for values
                6. Use the most recent value when multiple matches are found

                A slot is considered "filled" if:
                - It has an exact match in the current beliefs
                - It has a semantic match in the current beliefs
                - It has a match in the belief history
                - The value is not null, empty, or undefined
                - The value is in the correct format for the slot type

                RESPONSE FORMAT:
                Return a JSON object with these fields:
                {{
                    "slots": {{
                        // Dictionary mapping slot names to their values from beliefs
                        // Use semantic matching to find appropriate values
                    }},
                    "raw": {{
                        // The original belief object (for reference)
                    }},
                    "missing_slots": [
                        // List of slots that still need data
                        // Only include if complete=false
                    ],
                    "complete": true/false,
                    "human_prompt": "A natural language message explaining the status"
                }}

                HUMAN PROMPT RULES:
                1. If complete=true: 
                   - Acknowledge the information received
                   - Confirm readiness to proceed
                   - Example: "Great! I have all the information I need to proceed with next steps."
                
                2. If complete=false:
                   - Acknowledge what information you already have
                   - Ask for missing information in a conversational way
                   - Use natural transitions
                   - Examples:
                     * "Thanks for providing the date and number of guests. Could you also let me know what time you'd like to make the reservation for?"
                     * "I see you want to book a flight to Paris. I have your departure city, but could you tell me when you'd like to travel?"
                     * "I've got your name and contact information. To complete your profile, could you share your preferred payment method?"
                
                3. Never say "We have all the data" if there are missing slots
                
                4. When asking for missing information:
                   - Be specific about what's missing
                   - Provide context for why you need it
                   - Make it feel like a natural conversation
                   - Examples:
                     * "I have your arrival date, but I'll need to know your preferred check-in time to ensure we have your room ready."
                     * "To help you find the best flight options, could you tell me your preferred departure time?"
                
                5. When acknowledging filled slots:
                   - Show understanding of the information provided
                   - Connect it to the overall goal
                   - Examples:
                     * "I see you're planning a trip to Tokyo in December. That's a great time to visit!"
                     * "Perfect, I've got your party size of 4 people. Now, could you tell me your preferred seating area?"
                
                6. General tone guidelines:
                   - Be friendly and helpful
                   - Show understanding of the user's needs
                   - Make the conversation flow naturally
                   - Avoid technical or robotic language
                   - Use contractions (I've, you're, we'll, etc.)
                   - Keep responses concise but warm
            """
        
            response = self.llm(prompt)
        
            print(f"complete_slots > Raw prompt: {prompt}")
            print(f"complete_slots > Raw response: {response}")
            
            try:
                result_raw = self.clean_json_response(response)
                result = self.sanitize(result_raw)
                
            except json.JSONDecodeError as e:
                return {'success':False,'action':action,'input':{'slots':action_details.get('slots', {}),'beliefs':cleaned_current_beliefs},'output':str(e)}
                
        except Exception as e:
            print(f"Error in complete_slots: {e}")
            return {'success':False,'action':action,'input':{'slots':action_details.get('slots', {}),'beliefs':cleaned_current_beliefs},'output':str(e)}
        
        self.print_chat(result,'json')
        self.print_chat(result['human_prompt'],'text')
        
        next = 'form_intention' if result.get('complete', False) else 'finishing'
        
        return {'success':True,'action':action,'next':next,'input':{'action':current_action,'slots':action_details.get('slots', {}),'beliefs':cleaned_current_beliefs,'belief_history':pruned_belief_history},'output':result}
        
    
    
    # Intention Formation (Planning)
    def form_intention(self):
        
        action = 'form_intention'
        
        self.print_chat('Deciding next step...','text')
        
        # Get current workspace
        workspace = self.get_active_workspace()
        current_action = workspace.get('state', {}).get('action', '') if workspace else ''
        current_beliefs = workspace.get('state', {}).get('beliefs', {}) if workspace else {}
        current_desire = workspace.get('state', {}).get('desire', '') if workspace else ''
        
        current_beliefs = self.sanitize(current_beliefs)
        
        tools = self.DAC.get_a_b(self._get_context().portfolio, self._get_context().org, 'schd_tools')
        
        list_tools = {}
        
        for t in tools['items']:
            list_tools[t.get('key', '')] = {
                'key':t.get('key', ''),
                'goal':t.get('goal', ''),
                'instructions':t.get('instructions', ''),
                'input':t.get('input', ''),
                'output':t.get('output', '')
            } 
            
            
          
        # UNDER CONSTRUCTION
        # I need to get the current action document and get the examples from it to show the agent
        # how to create the plan. The example shows what tools can be used. 
        # The current action is already in this variable: current_action . The issue is that such variable might contain 
        # the name of the action instead of its key. Is this indexed? Yes, but 
        
        action_doc = self.load_action(current_action)
            # Using the loop to extract the examples of the current tool  
        examples = ''     
        if 'examples' in action_doc:
            examples = action_doc['tools_reference']
                
        # UNDER CONSTRUCTION ENDS
            
        
        inputs = {'belief':current_beliefs,'desire':current_desire,'action':current_action}
        
        
        prompt = f"""
        You are a tool selection module inside a BDI agent.

        Your task is to select the next tool to use based on:
        1. The current action being executed
        2. The available information (beliefs)
        3. The desired outcome
        4. Previous examples of how this action was executed
        
        ### Available Tools:
        {json.dumps(list_tools, indent=2)}

        ### Current Action:
        {current_action or 'No action selected'}

        ### Available Information:
        {json.dumps(current_beliefs, indent=2)}

        ### Desired Outcome:
        {current_desire or 'No desired outcome specified'}

        ### Action Examples:
        {examples or 'No examples available'}
        
        ### Special Requests
        - Look in the Current Information whether the user has requested something in specific. 
        - We are going to filter out the API results to provide only relevant information. 
        - You can see the special requests as the filter part of a query. 
        - Examples: 
            a) the minimum or maximum value of something, 
            b) to include or not include something, 
            c) To be close to a location, 
            d) For something to be greater or less than or equal to
            e) To provide a limited amount of results, etc.
            f) Whether the results need to be organized in a certain way
            
        ### Filter
        - The filter is a projection that will be applied to the raw output of the tool to filter out the results. 
        - The projection lets you extract, filter, and reshape JSON/dict data using a concise, declarative **projection** syntax.
        
        | Key            | Type           | Description                                                                 |
        |----------------|----------------|-----------------------------------------------------------------------------|
        | `field`: `True` | bool          | Include the field                                                           |
        | `"!field"`: `True` | bool       | Exclude the field                                                           |
        | `"*"`: `True`   | bool          | Include all fields                                                          |
        | `$filter`       | str or lambda | Filter list elements (e.g. `"price < 500"` or `lambda x: x["x"] > 1`)       |
        | `$sort_by`      | str           | Sort list by this field                                                     |
        | `$reverse`      | bool          | Reverse the sorted list                                                     |
        | `$limit`        | int           | Limit number of list elements returned                                      |
        | `$min`          | str           | Return only the item with the smallest value for a field                    |
        | `$max`          | str           | Return only the item with the largest value for a field                     |
        | `items`         | dict          | Apply a nested projection to list elements                                  |

        ---
        
        Filter example 1: Include Specific Fields
            data = {{ "name": "Alice", "age": 30, "city": "NY" }}
            projection = {{ "name": True, "age": True }}
            
        Filter example 2: Exclude Fields
            projection = {{ "*": True, "!age": True }}
            
        Filter example 3: Wildcard
            projection = {{ "*": True }}
            
        Filter example 4: Filter List with DSL
        
            data = {{ "flights": [ {{"price": 400}}, {{"price": 300}}, {{"price": 600}} ] }}
            projection = {{
                "flights": {{
                    "$filter": "price < 500",
                    "items": {{ "price": True }}
                }}
            }}
            
        Filter example 5: Sort and Limit
        
            projection = {{
                "flights": {{
                    "$sort_by": "price",
                    "$limit": 2,
                    "items": {{ "price": True }}
                }}
            }}
            
        Filter example 6: Get cheapest Flight
        
            projection = {{
                "flights": {{
                    "$min": "price",
                    "items": {{ "price": True }}
                }}
            }}
        
        Filter example 7: Get Most expensive Flight
        
            projection = {{
                "flights": {{
                    "$max": "price",
                    "items": {{ "price": True }}
                }}
            }}
            
        
        Filter example 8: Combine Filter + Sort + Limit
        
            projection = {{
                "flights": {{
                    "$filter": "price < 600",
                    "$sort_by": "price",
                    "$limit": 1,
                    "items": {{ "price": True }}
                }}
            }}
            
        Additional Tips for filters: 
        - Use `items` to apply sub-filters to list elements.
        - `$min` / `$max` returns a single-item list.
        - You can use lambdas instead of DSL:  
        `$filter`: `lambda x: x["price"] < 500`
        
        

        Return a JSON object with:
        {{
            "tool": "key_of_the_next_tool_to_use",
            "params": {{
                // Parameters needed for the tool
                // Use values from the available information when possible
            }},
            "filter": {{
                // Filter for this specific tools based on the belief special requirements. 
            }}
            "reasoning": "Brief explanation of why this tool was selected as the next step",
            "special_requests": "Human readable version of the filter"
        }}

        IMPORTANT:
        - Only select ONE tool that should be used next
        - Use the examples to understand the typical sequence of tools
        - Make sure all required parameters are provided
        - If you're unsure, select the most basic tool that can make progress
        """
        try:
            response = self.clean_json_response(self.llm(prompt))
            print(f"form_intention > Prompt: {prompt}")
            print(f"form_intention > Raw response: {response}")
            self._update_context(plan=response)
            self.mutate_workspace({'intent':response})
            self.print_chat(response,'json')
            self.print_chat(response['reasoning'],'text')
            
            if response['tool'] not in list_tools:
                next = 'finishing'
                return {'success':False,'action':action,'next':next,'input':inputs,'output':'No tool'}

            next = 'execute_intention' 
            #next = 'finishing' 
            return {'success':True,'action':action,'next':next,'input':inputs,'output':response}
            
        except json.JSONDecodeError as e: 
                 
            print(f"Error parsing LLM response in form_intention: {e}")
            next = 'finishing'
            return {'success':False,'action':action,'next':next,'input':'','output':e}
    
    

    ## Execution of Intentions
    def execute_intention(self):
        
        action = 'execute_intention'
        self.print_chat(f"Reached execute_intention ...",'text') 
        
        tools = self.DAC.get_a_b(self._get_context().portfolio, self._get_context().org, 'schd_tools')
        list_handlers = {}
        for t in tools['items']:
            list_handlers[t.get('key', '')] = t.get('handler', '')
            
        self._update_context(list_handlers=list_handlers)
        
    
        """Execute the current intention and return standardized response"""
        try:
        
            # Get current intention
            intention = self._get_context().plan
            if not intention:
                return {
                    'success': False,
                    'action': action,
                    'input': intention,
                    'output': 'No intention to execute'
                }

            # Get action and inputs
            tool_name = intention.get('tool')
            params = intention.get('params', {})
            reasoning = intention.get('reasoning', "")
            filter = intention.get('filter', "")
            special_request = intention.get('special_request', "")

            if not tool_name:
                raise ValueError("❌ No tool name provided in tool selection")
                
            print(f"Selected tool: {tool_name}")
            print(f"Reasoning: {reasoning}")
            print(f"Parameters: {params}")
            print(f"Filter: {filter}")
            print(f"special_request: {special_request}")
            
            # Send the filter along the parameters. The handler will use it. 
            params['_filter'] = filter

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
  
            #self.print_chat(f'Calling {handler_route} ','text') 
            print(f'Calling {handler_route} ') 
            
            response = self.SHC.handler_call(portfolio,org,parts[0],parts[1],params)
            
            if not response['success']:
                return {'success':False,'action':action,'input':params,'output':response}
            
            #print('FLATTEN THIS:')
            #print(response)
            #self.print_chat('Flattening response...','text')
            
            #Flatten output
            result = {}
            result['action']= parts[1]
            result['input']= response['output']['output']['output'][0]['input']
            result['output']= response['output']['output']['output'][0]['output']
            #result['flag1'] = 'red'
            
            
            # Results coming from the handler
            
            self.print_chat(result,'json')
            self._update_context(execute_intention_results=result)
            
            print("✅ Tool execution complete.")
            
            return {"success": True,"action":action,"input": intention,"output": result}
                    
        except Exception as e:

            error_msg = f"❌ Execute Intention failed. @'{tool_name}': {str(e)}"
            self.print_chat(error_msg,'text') 
            print(error_msg)
            self._update_context(execute_intention_error=error_msg)
            
            error_result = {
                "success": False, "action": action,"input": intention,"output": str(e)    
            }
            
            self._update_context(execute_intention_results=error_result)
            return error_result
    
    
    
    ## Reflection and Adaptive Replanning
    def reflect_on_success(self) -> str:
        
        action = 'reflected_on_success'
        
        try:
            prompt = f"""
            You are a reflection module inside a BDI agent.

            The previous intention (plan) succeeded during execution. Figure out if the goal has been achieved yet or we need to form more intentions.

            ### Current Action:
            {self._get_context().action}

            ### Desired Outcome:
            {self._get_context().desire}
            
            ### Plan
            {json.dumps(self._get_context().plan, indent=2)}
            
            ### Available Information:
            {json.dumps(self._get_context().belief, indent=2)}
    

            Return a short analysis and advice for next steps.
            """
            
            input ={
                'intention':self._get_context().plan,
                'belief':self._get_context().belief,
                'desire':self._get_context().desire,
                'action':self._get_context().action,
                }
            
            reflection = self.llm(prompt).strip()
            #print(f"🧠 Reflection:\n{reflection}\n")
            #self.print_chat(f"🧠 Reflection:\n{reflection}\n",'text') 
            
            next = 'finishing'
            return {'success':True,'action':action,'next':next,'input':input,'output':reflection}
        
        except Exception as e:
            next = 'finishing'
            return {'success':False,'action':action,'next':next,'input':input,'output':e}
        
        
    
    
    ## Reflection and Adaptive Replanning
    def reflect_on_failure(self) -> str:
        
        action = 'reflect_on_failure'
        
        
        try:
            
            error = str(self._get_context().execute_intention_error)
            
            prompt = f"""
            You are a reflection module inside a BDI agent.

            The previous intention (plan) failed during execution. Analyze what went wrong, and suggest what to adjust in future planning.

            ### Plan:
            {json.dumps(self._get_context().plan, indent=2)}

            ### Error:
            {error}

            Return a short analysis and advice for replanning.
            """
            
            input ={'intention':self._get_context().plan,'error':error}
            
            reflection = self.llm(prompt).strip()
            #print(f"🧠 Reflection:\n{reflection}\n")
            #self.print_chat(f"🧠❌ Reflection:\n{reflection}\n",'text') 
            
            next = 'finishing'
            return {'success':True,'action':action,'next':next,'input':input,'output':reflection}
                   
        except Exception as e:
            next = 'finishing'
            return {'success':False,'action':action,'next':next,'input':input,'output':e}
        
        
    
        
    
    #4  
    #NOT USED YET
    def planning(self):
    
        action = 'planning'
        
        try:
        
            print("📋 Forming intention (planning)...")
            plan = self.form_intention()
            print(f"  → Plan:\n{json.dumps(plan, indent=2)}")
            self.print_chat(plan,'json')
            self.mutate_workspace({'intent':plan})
            self._update_context(intent=plan)
            
            return {'success':True,'action':action,'input':{'desire':self._get_context().desire,'belief':self._get_context().belief},'output':plan}
                   
        except Exception as e:
            return {'success':False,'action':action,'input':{'desire':self._get_context().desire,'belief':self._get_context().belief},'output':e}
        
        


    
    def new_chat_message_document(self,message):
        
        action = 'new_chat_message_document'
        print(f'Running: {action}')  
        #self.print_chat('Creating new chat document...','text')
        
        context = {}
        context['portfolio'] = self._get_context().portfolio
        context['org'] = self._get_context().org
        context['entity_type'] = self._get_context().entity_type
        context['entity_id'] = self._get_context().entity_id
        context['thread'] = self._get_context().thread
                    
        message_object = {}
        message_object['message'] = message
        message_object['context'] = context
        message_object['input'] = message
         
        response = self.CHC.create_message(
                        self._get_context().entity_type,
                        self._get_context().entity_id,
                        self._get_context().thread,
                        message_object
                    ) 
        
        self._update_context(chat_id=response['document']['_id'])       
        print(f'Response:{response}')
    
        if 'success' not in response:
            return {'success':False,'action':action,'input':message_object,'output':response}
        
        return {'success':True,'action':action,'input':message_object,'output':response}
    

    
    def update_chat_message_document(self,update):
        
        action = 'update_chat_message_document'
        print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        try:
        
            response = self.CHC.update_message(
                            self._get_context().entity_type,
                            self._get_context().entity_id,
                            self._get_context().thread,
                            self._get_context().chat_id,
                            update
                        )
            
            if 'success' not in response:
                print(f'Something failed during update chat message {response}')
                return {'success':False,'action':action,'input':update,'output':response}
            
            #print(f'All good during update chat message {response}')
            return {'success':True,'action':action,'input':update,'output':response}
        
        except Exception as e:
            print(f'Update chat message failed: {str(e)}')
            return {'success':False,'action':action,'output':f'Error:{str(e)}'}

    
    
    
    def update_workspace_document(self,update,workspace_id):
        
        action = 'update_workspace_document'
        print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        response = self.CHC.update_workspace(
                        self._get_context().entity_type,
                        self._get_context().entity_id,
                        self._get_context().thread,
                        workspace_id,
                        update
                    )
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':update,'output':response}
        
        return {'success':True,'action':action,'input':update,'output':response}
        
        
        
    def new_chat_workspace_document(self,workspace_type,config,data):
        
        action = 'new_chat_workspace_document'
        print(f'Running: {action}')  
        #self.print_chat('Creating new chat document...','text')
        
        context = {}
        context['portfolio'] = self._get_context().portfolio
        context['org'] = self._get_context().org
        context['entity_type'] = self._get_context().entity_type
        context['entity_id'] = self._get_context().entity_id
        context['thread'] = self._get_context().thread
                    
        message_object = {}
        message_object['context'] = context
        message_object['type'] = workspace_type  # Using doc_type instead of type since type is a built-in Python function
        message_object['config'] = config
        message_object['data'] = data
         
        response = self.CHC.create_message(self._get_context().entity_type,self._get_context().entity_id,self._get_context().thread,message_object) 
        
        self._update_context(chat_id=response['document']['_id'])       
        print(f'Response:{response}')
    
        if 'success' not in response:
            return {'success':False,'action':action,'input':message_object,'output':response}
        
        return {'success':True,'action':action,'input':message_object,'output':response}
    
    
    
    def get_active_workspace(self):
        
        workspaces_list = self.CHC.list_workspaces(self._get_context().entity_type,self._get_context().entity_id,self._get_context().thread) 
        
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
    
    
    
    def load_action(self,act):
        
        action = 'load_action'            
        #Get action document 
        
        # Look for the document that belongs to the action : payload[action]
        # You might get back a list. Select the most recent one (you can select other ways, e.g by author)
        # The premise is that there might be more than one way to run an action.
        query = {
            'portfolio':self._get_context().portfolio,
            'org':self._get_context().org,
            'ring':'schd_actions',
            'operator':'begins_with',
            'value': act,
            'filter':{},
            'limit':999,
            'lastkey':None,
            'sort':'asc'
        }
        print(f'Query: {query}')
        response = self.DAC.get_a_b_query(query)
        print(f'Query: {response}')
        if not response['success']:return {'success':False,'action':'load_action','input':act,'output':response}
        
        
        if isinstance(response['items'], list) and len(response['items']) > 0:
            self._update_context(action_obj=response['items'][0])
            return {'success':True,'action':action,'input':act,'output':response['items'][0]}
        else:
            return {'success':False,'action':action,'input':act}
    
    
    def process_message(self, message, last_belief=None, belief_history=None):
        """
        Combined function that processes a message through multiple stages in a single LLM call:
        1. Perception and interpretation
        2. Information processing
        3. Fact extraction
        4. Desire detection
        5. Action matching
        """
        action = 'process_message'
        self.print_chat('Processing message...', 'text')
        
        # Get current time and date
        current_time = datetime.now().strftime("%Y-%m-%d")
        
        # Get available actions
        actions = self.DAC.get_a_b(self._get_context().portfolio, self._get_context().org, 'schd_actions')
        list_actions = {}
        for a in actions['items']:
            list_actions[a['key']] = {
                'goal': a.get('goal', ''),
                'key': a.get('key', ''),
                'utterances': a.get('utterances', ''),
                'slots': a.get('slots', '')
            }
        
        # Get current workspace action
        workspace = self.get_active_workspace()
        current_action = workspace.get('state', {}).get('action', '') if workspace else ''
        
        # Clean and prepare belief history if provided
        cleaned_belief_history = self.sanitize(belief_history) if belief_history else []
        pruned_belief_history = self.prune_history(cleaned_belief_history) if cleaned_belief_history else []
        
        prompt = f"""
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
        {json.dumps(list_actions, indent=2)}

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
        
        try:
            response = self.llm(prompt)
            print(f'PROCESS MESSAGE PROMPT >> {prompt}')
            result = self.clean_json_response(response)
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
            
            self.print_chat(sanitized_result, 'json')
            #next = 'complete_slots' if sanitized_result.get('action_match', {}).get('confidence', 0) > 80 else 'finishing' ## Eliminate this
            next = 'complete_slots'
            
            return {
                'success': True,
                'action': action,
                'next': next,
                'input': message,
                'output': sanitized_result
            }
            
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response in process_message: {e}")
            print(f"Raw response: {response}")
            return {
                'success': False,
                'action': action,
                'next': 'finishing',
                'input': message,
                'output': str(e)
            }
    
  
    
    def run(self,payload):
        # Initialize a new request context
        context = RequestContext()
        
        # Update context with payload data
        if 'connectionId' in payload:
            context.connection_id = payload["connectionId"]      
        if 'portfolio' in payload:
            context.portfolio = payload['portfolio']
        if 'org' in payload:
            context.org = payload['org']
        if 'entity_type' in payload:
            context.entity_type = payload['entity_type']
        if 'entity_id' in payload:
            context.entity_id = payload['entity_id']
        if 'thread' in payload:
            context.thread = payload['thread']
        if 'workspace' in payload:
            context.workspace_id = payload['workspace']
            
        # Set the context for this request
        self._set_context(context)
            
        results = []
        action = 'run'
        print(f'Running: {action}')
        
        print(f'Payload: {payload}')   
            
        try:
            # Step 0: Create thread/message document
            response_0 = self.new_chat_message_document(payload['data'])
            results.append(response_0)
            if not response_0['success']: 
                return {'success':False,'action':action,'output':results}
            
            # Get the latest workspace and make it available via the context
            workspace = self.get_active_workspace() 
            self._update_context(workspace=workspace)
            
            # Check if there is a follow up item pending
            last_belief = {}
            belief_history = []
            if workspace:    
                if workspace.get('state', {}).get('follow_up', {}).get('expected', False):
                    next_step = 'confirm_action'
                if workspace.get('state', {}).get('belief', {}):
                    last_belief = workspace['state']['belief']
                if workspace.get('state', {}).get('history', []):
                    belief_history = workspace['state']['history']
            
            # Process the message through all stages in one call
            response_1 = self.process_message(payload['data'], last_belief, belief_history)
            results.append(response_1)
            if not response_1['success']:
                return {'success':False,'action':action,'output':results}
            
            next_step = response_1['next']
            
            # Add protection against infinite loops
            MAX_ITERATIONS = 10  # Maximum number of steps allowed
            step_counter = 0
            previous_steps = set()  # Track previous steps to detect cycles
            
            while True:
                step_counter += 1
                
                #self.print_chat(f"Next Step:{next_step}",'text') 
                
                # Check if we've exceeded the maximum number of iterations
                if step_counter > MAX_ITERATIONS:
                    error_msg = f"❌ Maximum number of iterations ({MAX_ITERATIONS}) exceeded. Possible infinite loop detected."
                    print(error_msg)
                    return {'success':False, 'action':action, 'output':error_msg}
                
                # Check for cycles in the state machine
                if next_step in previous_steps:
                    error_msg = f"❌ Cycle detected in state machine. Step '{next_step}' was already visited."
                    print(error_msg)
                    return {'success':False, 'action':action, 'output':error_msg}
                
                previous_steps.add(next_step)
                print(f"Step {step_counter}: {next_step}")
                
                if next_step == 'complete_slots':
                    response_5 = self.complete_slots()
                    results.append(response_5)
                    if not response_5['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = response_5['next']
                    continue
                    
                if next_step == 'form_intention':
                    response_6 = self.form_intention()
                    results.append(response_6)
                    if not response_6['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = response_6['next'] 
                    continue
                    
                if next_step == 'execute_intention':  
                    response_7 = self.execute_intention()
                    results.append(response_7)
                    if not response_7['success']: 
                        next_step = 'reflect_on_failure'  # If execution fails, go to reflection
                    else:
                        next_step = 'reflect_on_success'  # If execution succeeds, finish
                    continue     
                
                if next_step == 'reflect_on_success':
                    response_8 = self.reflect_on_success()
                    results.append(response_8)
                    if not response_8['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = response_8['next']
                    continue
               
                if next_step == 'reflect_on_failure':
                    response_9 = self.reflect_on_failure()
                    results.append(response_9)
                    if not response_9['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = response_9['next']
                    continue
                
                if next_step == 'finishing': 
                    # Finishing 
                    break
                    
                # If we reach here, we have an unknown step
                error_msg = f"❌ Unknown step '{next_step}' encountered"
                print(error_msg)
                return {'success':False, 'action':action, 'error':error_msg, 'output':results}

            self.print_chat(f'🤖','text')
            
            #All went well, report back
            return {'success':True,'action':action,'message':'Run completed','input':payload,'output':results}
         
        except Exception as e:
            return {'success':False,'action':action,'message':f'Run failed. Error:{str(e)}','output':results}

    

# Test block
if __name__ == '__main__':
    # Creating an instance
    pass

    
    
    
 
