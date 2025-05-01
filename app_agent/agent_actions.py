#
from app_data.data_controller import DataController
from app_docs.docs_controller import DocsController
from app_chat.chat_controller import ChatController
from app_agent.agent_tools import ToolRegistry

from openai import OpenAI

import random
import json
import boto3
from datetime import datetime
from typing import List, Dict, Any, Callable
import re
from decimal import Decimal


from env_config import OPENAI_API_KEY,WEBSOCKET_CONNECTIONS

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

class AgentActions:
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
            
        self.bridge = {} 
        
        
        self.DAC = DataController()
        self.DCC = DocsController()
        self.CHC = ChatController()
        #self.SHL = SchdLoader() # If schd_actions was loaded by schd_loader, this will cause a circular dependency > ERROR
              
        
        self.AI_1 = openai_client
        #self.AI_1_MODEL = "gpt-4" // This model does not support json_object response format
        self.AI_1_MODEL = "gpt-3.5-turbo" # Baseline model. Good for multi-step chats
        self.AI_2_MODEL = "gpt-4o-mini" # This model is not very smart
        
        self.bridge['conn'] = ''
        self.apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=WEBSOCKET_CONNECTIONS)
        
        
        self.tools = ToolRegistry()

    
    def print_chat(self,output,type):
        # DataBase
        doc = {'_out':self.sanitize(output),'_type':type}
        self.update_chat_message_document(doc)
        
        if not self.bridge['conn']:
            return False
             
        try:
            print(f'Sending Real Time Message to:{self.bridge['conn']}')
            
            # WebSocket
            self.apigw_client.post_to_connection(
                ConnectionId=self.bridge['conn'],
                Data=json.dumps(doc, cls=DecimalEncoder)
            )
               
            print(f'Message has been updated')
            
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            self.bridge['conn'] = ''  # Clear the connection ID
            return False
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
                
                
                
    def mutate_workspace(self,changes):

        if not self.bridge['thread']:
            return False
        

        print("MUTATE_WORKSPACE>>",changes)
       
        #1. Get the workspace in this thread
        workspaces_list = self.CHC.list_workspaces(self.bridge['entity_type'],self.bridge['entity_id'],self.bridge['thread']) 
        print('WORKSPACES_LIST >>',workspaces_list) 
        
        if not workspaces_list['success']:
            return False
        
        if len(workspaces_list['items'])==0:
            #Create a workspace as none exist
            response = self.CHC.create_workspace(self.bridge['entity_type'],self.bridge['entity_id'],self.bridge['thread'],{}) 
            if not response['success']:
                return False
            # Regenerate workspaces_list
            workspaces_list = self.CHC.list_workspaces(self.bridge['entity_type'],self.bridge['entity_id'],self.bridge['thread']) 

            print('WORKSPACES_LIST >>>>',workspaces_list) 
            
            
        if not self.bridge.get('workspace_id'):
            workspace = workspaces_list['items'][-1]
        else:
            for w in workspaces_list['items']:
                if w['_id'] == self.bridge['workspace_id']:
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
                    #workspace['state']['beliefs'] = {**workspace['state']['beliefs'], **output} #Creates a new dictionary that combines both dictionaries
                    workspace['state']['beliefs'] = output
            
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
            
            if key == 'data_ovr':
                if isinstance(output, list):
                    workspace['data'] = output # Output overrides existing data
                    
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
            print(f'Sending Real Time Message to:{self.bridge['conn']}')
            #doc = {'_out':workspace,'_type':'json'}
            #self.print_chat(doc,'json')
            
            #self.print_chat('Updating the workspace document...','text')
            # Update document in DB
            self.update_workspace_document(workspace,workspace['_id'])
            
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            self.bridge['conn'] = ''  # Clear the connection ID
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
        elif isinstance(obj, (int, float)):
            # Keep numbers as is - they will be handled properly by JSON serialization
            return obj
        else:
            return obj
                    

  
    # NOT USED  
    def run_prompt(self,payload):
        
        action = 'run_prompt'
        

        if not self.AI_1:
            return {'success':False,'message':'No LLM client found.'}
        
        
        query = {
            'portfolio':self.bridge['portfolio'],
            'org':self.bridge['org'],
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
                self.bridge['completion_result'] = self.clean_json_response(raw_content)
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing LLM response: {e}"
                print(error_msg)
                return {'success':False,'action':action,'input':messages,'message':error_msg,'output':e}
                 
        except Exception as e:
            error_msg = f"Error occurred while calling LLM: {e}"
            print(error_msg)
            return {'success':False,'action':action,'input':messages,'message':error_msg,'output':e}
            
        return {'success':True,'action':action,'message':'Completion executed','input':messages,'output':self.bridge['completion_result'] }
    
    
    
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
    
    
    
    # 1
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
            
            return {'success':False,'action':action,'input':message,'output':default_result}
            
            
        
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
        
        return {'success':True,'action':action,'input':message,'output':result}
    
    
    
    # 2
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
        
            return {'success':True,'action':action,'input':input,'output':parsed_response}
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response in process_information: {e}")
            print(f"Raw response: {response}")
            
            
            return {'success':False,'action':action,'input':input,'output':None}
    
    
    
    

    
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
        
        
        actions = self.DAC.get_a_b(self.bridge['portfolio'], self.bridge['org'], 'schd_actions')
        
        #Accumulate all actions in a single prompt that we are going to send to the LLM. 
        prompt_actions = {}
        
        for action in actions['items']:
            
            print('Every action:',action)
            
            prompt_actions[action['key']] = {
                'goal':action['goal'],
                'name':action['name'],
                'utterances':action['utterances'],
                'slots':action['slots']
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
        {json.dumps(prompt_actions)}
        
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
            self.bridge['belief'] = belief 
            print('Belief >>', belief)
            self.mutate_workspace({'belief':belief})
            
            
            # Detect Desire based on belief history
            desire = self.detect_desire(belief)
            self.print_chat(desire,'text')
            self.bridge['desire'] = desire
            print('Desire >>', desire)
            self.mutate_workspace({'desire':desire})
                
            
            # Match Action with detected belief and desire
            act = self.match_action(belief,desire)
            self.print_chat(act,'json')
            self.bridge['action'] = act['action']
            print('Action >>', act)
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
            question = self.bridge['workspace']['state']['follow_up']['request'] # THIS OBJECT IS NOT ACTIVELY UPDATED!!!! BE CAREFUL
            options = self.bridge['workspace']['state']['follow_up']['options']
            
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
            
            # Remove any trailing commas
            cleaned_response = cleaned_response.replace(',}', '}')
            cleaned_response = cleaned_response.replace(',]', ']')
            
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
        
        act = self.bridge['action']
        response_0 = self.load_action(act)
        
        if not response_0['success']:
            return response
        
        slots = response_0['output']['slots']
        beliefs = self.bridge['belief']
        
        
        try:
            prompt = f"""
                You are an agent that checks if all required slots (parameters) for an action are filled with valid data.

                CURRENT CONTEXT:
                - Action: {act}
                - Required slots: {slots}
                - Available information: {beliefs}

                SLOT MATCHING RULES:
                1. Look for semantic matches between slot names and belief keys, not just exact matches
                2. Consider variations and synonyms (e.g., "number_of_passengers" matches "number_of_people", "passengers", "people_count")
                3. Look for related concepts (e.g., "departure_city" matches "origin", "from_city", "starting_location")
                4. Consider plural/singular forms and compound words (e.g., "departure_date" matches "departure", "date", "departuredate")

                A slot is considered "filled" if:
                - It has an exact match in the beliefs
                - It has a semantic match in the beliefs
                - The value is not null, empty, or undefined
                - If a slot is in the "slots" dictionary with a value, it should NOT be in the "missing_slots" list

                Examples of valid matches:
                - If slot is "number_of_passengers" and belief has "number_of_people" with value "2", the slot is filled
                - If slot is "departure_city" and belief has "origin" with value "New York", the slot is filled
                - If slot is "return_date" and belief has "end_date" with value "2025-05-01", the slot is filled

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
                1. If complete=true: Use a variation of "We have all the data that we need"
                2. If complete=false: Use a variation of "We still need: [list of missing slots]"
                3. Never say "We have all the data" if there are missing slots
                4. Clearly indicate what information is still needed
            """
        
            response = self.llm(prompt)
        
            print(f"complete_slots > Raw prompt: {prompt}")
            print(f"complete_slots > Raw response: {response}")
            
            try:
                result_raw = self.clean_json_response(response)
                result = self.sanitize(result_raw)
                
            except json.JSONDecodeError as e:
                return {'success':False,'action':action,'input':{'slots':slots,'beliefs':beliefs},'output':str(e)}
                
        except Exception as e:
            print(f"Error in complete_slots: {e}")
            return {'success':False,'action':action,'input':{'slots':slots,'beliefs':beliefs},'output':str(e)}
        
        self.print_chat(result,'json')
        self.print_chat(result['human_prompt'],'text')
        self.mutate_workspace({'intent':result}) 
        next = 'form_intention'
        
        return {'success':True,'action':action,'next':next,'input':{'slots':slots,'beliefs':beliefs},'output':result}
        
    
    #NOT USED YET
    # Intention Formation (Planning)
    def form_intention(self):
        
        action = 'form_intention'
        
        self.print_chat('Deciding next step...','text')
        
        actions = self.DAC.get_a_b(self.bridge['portfolio'], self.bridge['org'], 'schd_actions')
        
        #Accumulate all actions in a single prompt that we are going to send to the LLM. 
        list_actions = {}
        
        # TO-DO : You should formalize the tool registry instead of doing this. You can have the tool registry pool do what you are doing below.
        for a in actions['items']:
            list_actions[a['key']] = {
                'goal':a['goal'],
                'name':a['name'],
                'utterances':a['utterances'],
                'slots':a['slots']
            }        
            if a['key'] == self.bridge['action']:
                if 'tools_reference' in a:
                    examples = a['tools_reference']
            
            
        prompt = f"""
        You are a tool selection module inside a BDI agent.

        Your task is to select the next tool to use based on:
        1. The current action being executed
        2. The available information (beliefs)
        3. The desired outcome
        4. Previous examples of how this action was executed

        ### Current Action:
        {self.bridge['action']}

        ### Available Information:
        {json.dumps(self.bridge['belief'], indent=2)}

        ### Desired Outcome:
        {self.bridge['desire']}

        ### Action Examples:
        # TO-DO: Add field name to 'examples'
        {examples}

        ### Available Tools:
        {json.dumps(list_actions)}

        Return a JSON object with:
        {{
            "tool": "name_of_selected_tool",
            "params": {{
                // Parameters needed for the tool
                // Use values from the available information when possible
            }},
            "reasoning": "Brief explanation of why this tool was selected"
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
            self.bridge['plan'] = response
            self.print_chat(response,'json')
            inputs = {'belief':self.bridge['belief'],'desire':self.bridge['desire'],'action':self.bridge['action']}
            return {'success':True,'action':action,'next':'finishing','input':inputs,'output':response}
            
        except json.JSONDecodeError as e:         
            print(f"Error parsing LLM response in form_intention: {e}")
            return {'success':False,'action':action,'next':'finishing','input':inputs,'output':e}
    
    

    ## Execution of Intentions
    def execute_intention(self):
        """
        Executes a single tool call based on the tool selection from form_intention().
        
        Args:
            tool_selection: A dictionary containing:
                - tool: The name of the tool to execute
                - params: The parameters for the tool
                - reasoning: The reasoning behind selecting this tool
                
        Returns:
            Dict containing the execution results
        """
        print("🚀 Executing tool...")
        tool_selection = self.bridge['plan']
        
        if not isinstance(tool_selection, dict):
            raise ValueError("❌ Tool selection must be a dictionary")
            
        tool_name = tool_selection.get("tool")
        params = tool_selection.get("params", {})
        reasoning = tool_selection.get("reasoning", "")
        
        if not tool_name:
            raise ValueError("❌ No tool name provided in tool selection")
            
        print(f"Selected tool: {tool_name}")
        print(f"Reasoning: {reasoning}")
        print(f"Parameters: {params}")
        
        try:
            # Get the tool function from the registry
            tool_func = self.tools.get_tool(tool_name)
            if not tool_func:
                raise ValueError(f"❌ No tool registered with name '{tool_name}'")
                
            # Execute the tool
            print(f"⚙️  Executing: {tool_name}({params})")
            result = tool_func(**params)
            
            # Store results
            execution_result = {
                "tool": tool_name,
                "params": params,
                "result": result,
                "success": True
            }
            
            self.bridge['execute_intention_results'] = execution_result
            print("✅ Tool execution complete.")
            
            return execution_result
                    
        except Exception as e:
            error_msg = f"❌ Error executing '{tool_name}': {str(e)}"
            print(error_msg)
            self.bridge['execute_intention_error'] = error_msg
            
            error_result = {
                "tool": tool_name,
                "params": params,
                "error": str(e),
                "success": False
            }
            
            self.bridge['execute_intention_results'] = error_result
            return error_result
    
    
    
    ## Reflection and Adaptive Replanning
    def reflect_on_success(self) -> str:
        prompt = f"""
        You are a reflection module inside a BDI agent.

        The previous intention (plan) succeeded during execution. Figure out if the goal has been achieved yet or we need to form more intentions.

        ### Current Action:
        {self.bridge['action']}

        ### Desired Outcome:
        {self.bridge['desire']}
        
        ### Available Information:
        {json.dumps(self.bridge['belief'], indent=2)}
 

        Return a short analysis and advice for next steps.
        """
        reflection = self.llm(prompt).strip()
        print(f"🧠 Reflection:\n{reflection}\n")
        return reflection
    
    
    ## Reflection and Adaptive Replanning
    def reflect_on_failure(self) -> str:
        prompt = f"""
        You are a reflection module inside a BDI agent.

        The previous intention (plan) failed during execution. Analyze what went wrong, and suggest what to adjust in future planning.

        ### Plan:
        {json.dumps(plan, indent=2)}

        ### Error:
        {str(error)}

        Return a short analysis and advice for replanning.
        """
        reflection = self.llm(prompt).strip()
        print(f"🧠 Reflection:\n{reflection}\n")
        return reflection
    
        
    
    #4  
    #NOT USED YET
    def planning(self):
    
        action = 'planning'
        
        try:
        
            print("📋 Forming intention (planning)...")
            plan = self.form_intention(self.bridge['desire'], self.bridge['belief'])
            print(f"  → Plan:\n{json.dumps(plan, indent=2)}")
            self.print_chat(plan,'json')
            self.mutate_workspace({'intent':plan})
            self.bridge['intent'] = plan
            
            return {'success':True,'action':action,'input':{'desire':self.bridge['desire'],'belief':self.bridge['belief']},'output':plan}
                   
        except Exception as e:
            return {'success':False,'action':action,'input':{'desire':self.bridge['desire'],'belief':self.bridge['belief']},'output':e}
        
        


    
    def new_chat_message_document(self,message):
        
        action = 'new_chat_message_document'
        print(f'Running: {action}')  
        #self.print_chat('Creating new chat document...','text')
        
        context = {}
        context['portfolio'] = self.bridge['portfolio']
        context['org'] = self.bridge['org']
        context['entity_type'] = self.bridge['entity_type']
        context['entity_id'] = self.bridge['entity_id']
        context['thread'] = self.bridge['thread']
                    
        message_object = {}
        message_object['message'] = message
        message_object['context'] = context
        message_object['input'] = message
         
        response = self.CHC.create_message(
                        self.bridge['entity_type'],
                        self.bridge['entity_id'],
                        self.bridge['thread'],
                        message_object
                    ) 
        
        self.bridge['chat_id'] = response['document']['_id']       
        print(f'Response:{response}')
    
        if 'success' not in response:
            return {'success':False,'action':action,'input':message_object,'output':response}
        
        return {'success':True,'action':action,'input':message_object,'output':response}
    

    
    def update_chat_message_document(self,update):
        
        action = 'update_chat_message_document'
        print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        response = self.CHC.update_message(
                        self.bridge['entity_type'],
                        self.bridge['entity_id'],
                        self.bridge['thread'],
                        self.bridge['chat_id'],
                        update
                    )
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':update,'output':response}
        
        return {'success':True,'action':action,'input':update,'output':response}
    
    
    
    def update_workspace_document(self,update,workspace_id):
        
        action = 'update_workspace_document'
        print(f'Running: {action}')
        #self.print_chat('Updating chat document...','text')
        
        response = self.CHC.update_workspace(
                        self.bridge['entity_type'],
                        self.bridge['entity_id'],
                        self.bridge['thread'],
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
        context['portfolio'] = self.bridge['portfolio']
        context['org'] = self.bridge['org']
        context['entity_type'] = self.bridge['entity_type']
        context['entity_id'] = self.bridge['entity_id']
        context['thread'] = self.bridge['thread']
                    
        message_object = {}
        message_object['context'] = context
        message_object['type'] = workspace_type  # Using doc_type instead of type since type is a built-in Python function
        message_object['config'] = config
        message_object['data'] = data
         
        response = self.CHC.create_message(self.bridge['entity_type'],self.bridge['entity_id'],self.bridge['thread'],message_object) 
        
        self.bridge['chat_id'] = response['document']['_id']       
        print(f'Response:{response}')
    
        if 'success' not in response:
            return {'success':False,'action':action,'input':message_object,'output':response}
        
        return {'success':True,'action':action,'input':message_object,'output':response}
    
    
    
    def get_active_workspace(self):
        
        workspaces_list = self.CHC.list_workspaces(self.bridge['entity_type'],self.bridge['entity_id'],self.bridge['thread']) 
        
        if not workspaces_list['success']:
            return False
        
        if len(workspaces_list['items'])==0:
            return False
        
        if not self.bridge.get('workspace_id'):
            workspace = workspaces_list['items'][-1]
        else:
            for w in workspaces_list['items']:
                if w['_id'] == self.bridge['workspace_id']:
                    workspace = w
                    
        return workspace
    
    
    
    def load_action(self,act):
        
        action = 'load_action'            
        #Get action document 
        
        # Look for the document that belongs to the action : payload[action]
        # You might get back a list. Select the most recent one (you can select other ways, e.g by author)
        # The premise is that there might be more than one way to run an action.
        query = {
            'portfolio':self.bridge['portfolio'],
            'org':self.bridge['org'],
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
            self.bridge['action_obj'] = response['items'][0]
            return {'success':True,'action':action,'input':act,'output':response['items'][0]}
        else:
            return {'success':False,'action':action,'input':act}
    
    
    
    
  
    
    def run(self,payload):
        results = []
        action = 'agent_actions'
        print(f'Running: {action}')
        
        print(f'Payload: {payload}')   
        
        if 'connectionId' in payload:
            self.bridge['conn'] = payload["connectionId"]      
        if 'portfolio' in payload:
            self.bridge['portfolio'] = payload['portfolio']
        if 'org' in payload:
            self.bridge['org'] = payload['org']
        if 'entity_type' in payload:
            self.bridge['entity_type'] = payload['entity_type']
        if 'entity_id' in payload:
            self.bridge['entity_id'] = payload['entity_id']
        if 'thread' in payload:
            self.bridge['thread'] = payload['thread']
        if 'workspace' in payload:
            self.bridge['workspace_id'] = payload['workspace']
            
        try:
            # Step 0: Create thread/message document
            response_0 = self.new_chat_message_document(payload['data'])
            results.append(response_0)
            if not response_0['success']: 
                return {'success':False,'action':action,'output':results}
            next_step = 'perception_and_interpretation'
                
            
            # Get the latest workspace and make it available via the bridge
            workspace = self.get_active_workspace() 
            self.bridge['workspace'] = workspace
            
            # Check if there is a follow up item pending.
            last_belief = {}
            if workspace:    
                if workspace.get('state', {}).get('follow_up', {}).get('expected', False):
                    next_step = 'confirm_action'
                if workspace.get('state', {}).get('belief', {}):
                    last_belief = workspace['state']['belief']
            
            # Add protection against infinite loops
            MAX_ITERATIONS = 10  # Maximum number of steps allowed
            step_counter = 0
            previous_steps = set()  # Track previous steps to detect cycles
            
            while True:
                step_counter += 1
                
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
                
                if next_step == 'perception_and_interpretation':
                    # Perception and Interpretation
                    response_1 = self.perception_and_interpretation(payload['data'],last_belief)
                    results.append(response_1)
                    if not response_1['success']: 
                        return {'success':False,'action':action,'output':results} 
                    next_step = 'process_information'
                    continue

                if next_step == 'process_information':            
                    # Process Information
                    response_2 = self.process_information(response_1['output'])
                    results.append(response_2)
                    if not response_2['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = 'reasoning'
                    continue
                    
                if next_step == 'reasoning': 
                    # Reasoning 
                    response_3 = self.reasoning()
                    results.append(response_3)
                    if not response_3['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = response_3['next']
                    continue
                
                
                '''
                #NOT USED
                  if next_step == 'confirm_action': 
                    response_4 = self.confirm_action(payload['data'])
                    results.append(response_4)
                    if not response_4['success']: 
                        return {'success':False,'action':action,'output':results}
                    
                    if response_4['output']['status']=='valid':
                        next_step = 'complete_slots'
                    else:
                        next_step = 'perception_and_interpretation'
                    continue'''
                        
                
                if next_step == 'complete_slots':
                    response_5 = self.complete_slots()
                    results.append(response_5)
                    if not response_5['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = response_5['next']
                    continue
                    
                # Planning the next step only
                if next_step == 'form_intention':
                    response_6 = self.form_intention()
                    results.append(response_6)
                    if not response_6['success']: 
                        return {'success':False,'action':action,'output':results}
                    #next_step = 'execute_intention'  # Changed from 'finishing' to 'execute_intention'
                    next_step = 'finishing'  
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
                    next_step = 'finishing'
                    continue
               
                if next_step == 'reflect_on_failure':
                    response_9 = self.reflect_on_failure()
                    results.append(response_9)
                    if not response_9['success']: 
                        return {'success':False,'action':action,'output':results}
                    next_step = 'finishing'
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
            return {'success':True,'action':action,'message':'run completed','output':results}
            
        except Exception as e:
            return {'success':False,'action':action,'message':str(e),'output':results}
        
          

# Test block
if __name__ == '__main__':
    # Creating an instance
    pass

    
    
    
 
