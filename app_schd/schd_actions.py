#DEPRECATED
from datetime import datetime

from app_data.data_controller import DataController
from app_docs.docs_controller import DocsController
from app_chat.chat_controller import ChatController

from openai import OpenAI

import random
import json
import boto3
from datetime import datetime


from env_config import OPENAI_API_KEY,WEBSOCKET_CONNECTIONS


class SchdActions:
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
        #self.AI_1_MODEL = "gpt-4o-mini" // This model is not very smart
        self.AI_1_MODEL = "gpt-3.5-turbo"
        
        self.bridge['conn'] = ''
        self.apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=WEBSOCKET_CONNECTIONS)
        
        
        
    
        
    def print_chat(self,output,type):
        
        if not self.bridge['conn']:
            return False
             
        try:
            print(f'Sending Real Time Message to:{self.bridge['conn']}')
            doc = {'_out':output,'_type':type}
            
            # WebSocket
            self.apigw_client.post_to_connection(
                ConnectionId=self.bridge['conn'],
                Data=json.dumps(doc)
            )
            # DataBase
            self.update_chat_message_document(doc)
            
            print(f'Message has been updated')
            
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            self.bridge['conn'] = ''  # Clear the connection ID
            return False
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
                
                
                
    def mutate_workspace(self,output,key):
        
        if not self.bridge['thread']:
            return False
        

        print("MUTATE_WORKSPACE>>",key,output)
       
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
            
            
        if not self.bridge.get('workspace'):
            workspace = workspaces_list['items'][-1]
        else:
            for w in workspaces_list['items']:
                if w['_id'] == self.bridge['workspace']:
                    workspace = w
                    
        print('Selected workspace >>>>',workspace) 
        if 'state' not in workspace:
            workspace['state'] = {
                "beliefs": {},
                "goals": [],           
                "intentions": [],       
                "history": [],          
                "in_progress": None    
            }
            
        #2. Store the output in the workspace
        if key == 'belief':
            # output = {"date":"345"}
            if isinstance(output, dict):
                workspace['state']['beliefs'] = {**workspace['state']['beliefs'], **output} #Creates a new dictionary that combines both dictionaries
                
            # Now update the belief history
            for k, v in output.items():
                history_event = {
                    'key': k,
                    'val': v,
                    'time': datetime.now().isoformat()
                }
                workspace['state']['history'].append(history_event)
            
            
        
        if key == 'goals':
            if isinstance(output, dict):
                workspace['state']['goals'].insert(0, output) # The inserted object goes to the first position (this will work as a stack)
                
        if key == 'intentions':
            if isinstance(output, dict):
                workspace['state']['intentions'].insert(0, output) # The inserted object goes to the first position (this will work as a stack)
                
        if key == 'history':
            if isinstance(output, dict):
                workspace['state']['history'].append(output) # The inserted object goes to the last position
                          
        if key == 'data':
            if isinstance(output, dict):
                workspace['data'].append(output) # The inserted object goes to the last position            
        
        if key == 'data_ovr':
            if isinstance(output, list):
                workspace['data'] = output # Output overrides existing data
                
        if key == 'is_active':
            if isinstance(output, bool):
                workspace['data'] = output # Output overrides existing data
                
                    
        #3. Broadcast updated workspace
        
        # WebSocket
            self.apigw_client.post_to_connection(
                ConnectionId=self.bridge['conn'],
                Data=json.dumps(doc)
            )
         
        
        try:
            print(f'Sending Real Time Message to:{self.bridge['conn']}')
            doc = {'_out':workspace,'_type':'json'}
            
            self.print_chat('Updating the workspace document...','text')
            #self.print_chat(doc,'json')
            
            # Update document
            self.update_workspace_document(workspace,workspace['_id'])
            
            return True
        
        except self.apigw_client.exceptions.GoneException:
            print(f'Connection is no longer available')
            self.bridge['conn'] = ''  # Clear the connection ID
            return False
        except Exception as e:
            print(f'Error sending message: {str(e)}')
            return False
                

                
        
         
        
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
            self.bridge['completion_result'] = json.loads(raw_content)
                 
            
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
            temperature=0.5
        )
        
        return response.choices[0].message.content.strip()
    
    
    
    # 1
    def perception_and_interpretation(self, message):
        
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

            Do not perform reasoning or fill in missing values. Just extract what is directly mentioned.
            Make sure to return valid JSON with all strings properly quoted.

            User message: '{message}'
        """
        
        response = self.llm(prompt)
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Raw response: {response}")
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
        self.print_chat('Enriching and normalizing the beliefs...','text')
          
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

            Today's date is 2025-04-19.

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
            # Clean the response by removing any comments or non-JSON content
            cleaned_response = response.strip()
            # Remove any trailing commas
            cleaned_response = cleaned_response.replace(',}', '}')
            cleaned_response = cleaned_response.replace(',]', ']')
            
            print(f'LLM Response before parsing: {cleaned_response}')
            parsed_response = json.loads(cleaned_response)
            
            # Ensure the response has the required structure
            if not isinstance(parsed_response, dict):
                raise ValueError("Response is not a dictionary")
                
            if "beliefs" not in parsed_response:
                raise ValueError("Response missing 'beliefs' key")
            
            
            self.print_chat(parsed_response,'json')
            self.print_chat('Now, I will update the beliefs in the workspace','text')
            self.mutate_workspace(parsed_response['beliefs']['entities'],'belief')
        
            return {'success':True,'action':action,'input':input,'output':parsed_response}
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response in process_information: {e}")
            print(f"Raw response: {response}")
            default_response = {
                "beliefs": {
                    "intent": "unknown",
                    "entities": {},
                    "raw_text": str(input),
                    "needs_tools": [],
                    "date": datetime.now().strftime("%Y-%m-%d")
                },
                "missing_beliefs": [],
                "resolved_intent": "unknown"
            }
            
            return {'success':False,'action':action,'input':input,'output':default_response}
    
    
        
    #DEPRECATED       
    '''def perception_and_interpretation_x(self,input):
        
        action = 'perception_and_interpretation'
        print(f'Running: {action}')
        
        
        self.print_chat('Trying to understand the context of the message...','text')
        
        input_template = '<raw message string>'
        output_template = {
                "type":"text",
                "message":"<sanitized version of the message>",
                "language":"<detected language>",
                "sentiment":"[<list of sentiments>]"
            }
        
        
        payload = {  
            'system_wide_prompt': system_prompt, 
            'feedback_key': 'perception_and_interpretation',
            'system_content': (
                "You are an agent in charge of receiving and relaying messages while detecting its language and sentiment.\n"
            ),
            'user_content': f"{self.bridge['config']['prompt_1_perception_and_interpretation']}",
            'input_template':f"{input_template}",
            'output_template':f"{output_template}",
            'user_input': f"The messaged received is the following:{input}",
            
        }
        
        response = self.run_prompt(payload)
        self.bridge['interpretation'] = response['output']
        self.print_chat(response['output'],'json')
        self.mutate_workspace(response['output'],'belief')
        
        
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        return {'success':True,'action':action,'input':input,'output':response}'''
        
        
    # DEPRECATED
    '''def process_information_x(self,input):
        
        action = 'process_information'
        print(f'Running: {action}')
        
        self.print_chat('Setting up a goal...','text')
        
        input_template = {
            "type": "text",
            "message": "<original message>",
            "language": "<original language>",
            "sentiment": "[<sentiment list>]"
        }
        output_template = {
            "goal":"<recommended goal>",
            "guest_qty":"<number of guest>",
            "date":"<date of the reservation>",
            "time":"<time of the reservation>"
        }
        
        payload = {   
            'feedback_key': 'process_information',
            'system_content': (
                "You are an agent in charge of understanding the message and setting up the goal that needs to be achieved.\n"
            ),
            'user_content': f"{self.bridge['config']['prompt_2_process_information']}",
            'input_template':f"{input_template}",
            'output_template':f"{output_template}",
            'user_input': f"The actual input received from the receptionist is: {input}"
        }
        
        response = self.run_prompt(payload)
        self.bridge['information'] = response['output']
        self.print_chat(response['output'],'json')
        self.mutate_workspace(response['output'],'goals')
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        return {'success':True,'action':action,'input':input,'output':response}'''
        
        
    '''
    def reasoning_and_planning_x(self,input):
        
        action = 'reasoning_and_planning'
        print(f'Running: {action}')
        
        self.print_chat('Creating a plan of action...','text')
        
        input_template = {
            'goal':"<goal>",
            'guest_qty':"<number of guests>",
            'date':"<reservation date>",
            'time':"<reservation_time>"
        }
        output_template = [
            {
                'tool':"<tool name 1>",
                'parameters':{
                    'param':"<param to be sent 1>",
                }
            }, 
            {
                'tool':"<tool name n>",
                'parameters':{
                    'param':"<param to be sent n>",
                }
            }
        ]
        
        payload = {   
            'feedback_key': 'reasoning_and_planning',
            'system_content': (
                "You are an agent that plans how to execute a task with available tools.'\n"
            ),
            'user_content': f"{self.bridge['config']['prompt_3_reasoning_and_planning']}",
            'input_template':f"{input_template}",
            'output_template':f"{output_template}",
            'user_input': f"Prepare a plan for the following case: {input}"
            
        }
        
        response = self.run_prompt(payload)
        self.bridge['plan'] = response['output']
        self.print_chat(response['output'],'json')
        self.mutate_workspace(response['output'],'intentions')
        
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        
        return {'success':True,'action':action,'input':input,'output':response}
    '''
    
    
    '''
    def generate_commands_x(self,plan):
        
        action = 'generate_commands'
        print(f'Running: {action}')
        
        self.print_chat('Generating the commands to make it happen...','text')
        
        input_template = [
            {
                'tool':"<tool name 1>",
                'parameters':{
                    'param':"<param to be sent 1>",
                }
            }, 
            {
                'tool':"<tool name n>",
                'parameters':{
                    'param':"<param to be sent n>",
                }
            }
        ]
        output_template = {
            'commands':
            [
                "<COMMAND STRING>"
            ]
        }
        
        payload = {  
            'feedback_key': 'generate_commands', 
            'system_content': (
                "You are an agent that creates an output that will be executed \n"
            ),
            'user_content': f"{self.bridge['config']['prompt_4_execution']}",
            'input_template':f"{input_template}",
            'output_template':f"{output_template}",
            'user_input': f" This is the input: {plan}"
        }
        
        response = self.run_prompt(payload)
        
        print(f'generate_commands > response > {response}')
        self.bridge['commands'] = response['output']
        self.print_chat(response['output'],'json')
        
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':plan,'output':response}
        
        
        return {'success':True,'action':action,'input':plan,'output':response}
    '''
    
    
    
    '''
    def run_command(self,command):
        
        action = 'run_command'
        print(f'Running: {action}')
        
        print('Running the following command:')
        print(command)
        self.print_chat(f'running: {command}','command')
        
        return {'success':True,'action':action,'input':command,'output':'mock-executed'}
    '''
        
    
    
    '''
    def execute_plan_NEW(self,plan):
        
        action = 'execute_plan'
        print(f'Running: {action}')
        
        last_response = {}
        for step in plan:    
            step['last_response']   
            response = self.SHL.load_and_run(step['tool'], payload = step['parameters'])
            last_response = response
    '''
        
            
            
    
    '''
    def execute_plan(self,plan):
        
        action = 'execute_plan'
        print(f'Running: {action}')
        

        self.print_chat('Executing plan...','text')
         
        #1. Call function that generates the RESTFUL commands
        response_1 = self.generate_commands(plan)  
        if not response_1:
            return {'success':False,'action':action,'input':plan,'output':response_1}
        
        
        #2. Iterate through the list of commands and execute each one at a time until done. 
        #executions = []
        #print('RESPONSE_1 >>>')
        #print(response_1)
        #for command in response_1['output']['output']['commands']:
        #    # This is like a dynamic funnel
        #    response_2 = self.run_command(command)
        #    if not response_2:
        #        return {'success':False,'action':action,'input':command,'output':response_2}
        #    executions.append(response_2)
            
        print(f'EXECUTE_PLAN >>{response_1}')
        
        
        return {'success':True,'action':action,'input':plan,'output':response_1}
    '''
            

    
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
    
    
    
    '''
    def load_action(self,payload):
        
        action = 'load_action'
             
        #Get config document for this portfolio/org
        
        # Look for the document that belongs to the action : payload[action]
        # You might get back a list. Select the most recent one (you can select other ways, e.g by author)
        # The premise is that there might be more than one way to run an action.
        query = {
            'portfolio':payload['portfolio'],
            'org':payload['org'],
            'ring':'schd_actions',
            'operator':'begins_with',
            'value': payload['action'],
            'filter':{},
            'limit':999,
            'lastkey':None,
            'sort':'asc'
        }
        print(f'Query: {query}')
        response = self.DAC.get_a_b_query(query)
        print(f'Query: {response}')
        if not response['success']:return {'success':False,'action':action,'input':payload,'output':response}
        
        
        if isinstance(response['items'], list) and len(response['items']) > 0:
            self.bridge['config'] = response['items'][0]
            print('Action config stored in bridge')
            return {'success':True,'action':action,'input':payload,'output':response['items'][0]}
        else:
            return {'success':False,'action':action,'input':payload}
    '''
    
    
    
  
    
    def run(self,payload):
        
        results = []
        action = 'schd_actions'
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
            self.bridge['workspace'] = payload['workspace']
            
           
        '''
        # Step 0a: Load Action
        response_0a = self.load_action(payload)
        results.append(response_0a)
        if not response_0a['success']: return {'success':False,'action':action,'output':results}
        '''
        
        print('Starting step 0')
        # Step 0: Create thread/message document
        response_0 = self.new_chat_message_document(payload['data'])
        results.append(response_0)
        if not response_0['success']: return {'success':False,'action':action,'output':results}
        

        # Step 1: Perception and Interpretation
        response_1 = self.perception_and_interpretation(payload['data'])
        results.append(response_1)
        if not response_1['success']: return {'success':False,'action':action,'output':results}
        
        
        '''
        response_1["output"] = {
        "language": "English",
        "message": "I need a reservation in your stupid restaurant",
        "next": {
            "action": "send_chat_message",
            "parameters": {
                "message": "We do not tolerate harassment in this chat"
            },
            "type": "break"
        },
        '''
        
        print('RESPONSE 1:',response_1)
        
        # If perception_and_interpretation need to say something in the chat (mostly to ask for more information)
        '''if 'next' in response_1['output']['output']:
            if 'action' in response_1['output']['output']['next']:
                if response_1['output']['output']['next']['action'] == 'send_chat_message':
                    self.print_chat(response_1['output']['output']['next']['parameters']['message'],'text')
                    print('NEXT/ACTION >>> Perception and Interpretation')
                    print(response_1['output']['output']['next']['parameters']['message'])
                    
        
        # If perception_and_intepretation needs a break (mostly to ask for more information)
        if 'next' in response_1['output']['output']:
            if 'break' in response_1['output']['output']['next']:
                if response_1['output']['output']['next']['break']:
                    print('NEXT/TYPE >>> Perception and Interpretation')
                    print(response_1['output']['output']['next']['break'])
                    return {'success':True,'action':action,'output':results}
        '''
                    
                
                    
        
        
        # Step 2: Process Information
        response_2 = self.process_information(response_1['output'])
        results.append(response_2)
        if not response_2['success']: return {'success':False,'action':action,'output':results}
        
        
        print('RESPONSE 2:',response_2)
        
        
        ''' if 'next' in response_2['output']['output']:
            if 'action' in response_2['output']['output']['next']:
                if response_2['output']['output']['next']['action'] == 'send_chat_message':
                    self.print_chat(response_2['output']['output']['next']['parameters']['message'],'text')
                    print('NEXT/ACTION >>> Perception and Interpretation')
                    print(response_2['output']['output']['next']['parameters']['message'])
                    
        
        if 'next' in response_2['output']['output']:
            if 'break' in response_2['output']['output']['next']:
                if response_2['output']['output']['next']['break']:
                    print('NEXT/TYPE >>> Perception and Interpretation')
                    print(response_2['output']['output']['next']['break'])
                    return {'success':True,'action':action,'output':results}
        '''
                
                

        
        '''
        {
        "date": "2025-04-11",
        "goal": "book-table",
        "guest_qty": "5",
        "next": {
            "action": "send_chat_message",
            "break": false,
            "parameters": {
            "message": "Your request is clear"
            }
        },
        "time": "17:00"
        }
        '''
        
        
        
        
        
        
        '''
        # Step 3: Reasoning and Planning
        response_3 = self.reasoning_and_planning(self.bridge['information'])
        results.append(response_3)
        if not response_3['success']: return {'success':False,'action':action,'output':results}
        '''
        
        
        
        '''
        {
        "plan": [
            {
            "parameters": {
                "date": "2025-04-11",
                "guest_qty": "5",
                "time": "17:00"
            },
            "tool": "search_table_availability"
            },
            {
            "parameters": {
                "date": "2025-04-11",
                "guest_qty": "5",
                "time": "17:00"
            },
            "tool": "book_table"
            },
            {
            "parameters": {
                "param": "Your request is clear"
            },
            "tool": "send_whatsapp_message"
            }
        ]
        }
        '''
        
        
        
        '''
        # Step 4: Validate Plan
        response_4 = self.validate_plan()
        results.append(response_4)
        if not response_4['success']: return {'success':False,'output':results}
        '''
    
        
        '''
        # Step 5: Execute Plan
        response_5 = self.execute_plan(self.bridge['plan'])
        results.append(response_5)
        if not response_5['success']: return {'success':False,'output':results}
        '''
        
        
        '''
        # Step 6: Verify Execution
        response_6 = self.verify_execution()
        results.append(response_6)
        if not response_6['success']: return {'success':False,'output':results}
        '''
        
        '''
        # Step 7: Create thread/message document
        response_7 = self.save_chat_document(payload,{'plan':self.bridge['plan'],'commands':self.bridge['commands']})
        results.append(response_7)
        if not response_7['success']: return {'success':False,'action':action,'output':results}
        '''
    

        self.print_chat('Cycle completed','text')
        self.bridge['conn'] = ''
            
                  
        #All went well, report back
        return {'success':True,'action':action,'message':'run completed','output':results}
        
          

# Test block
if __name__ == '__main__':
    # Creating an instance
    pass

    
    
    
 
