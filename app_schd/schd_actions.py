#
from datetime import datetime

from app_data.data_controller import DataController
from app_docs.docs_controller import DocsController
from app_chat.chat_controller import ChatController

from openai import OpenAI

import random
import json
import boto3


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
        #self.SHL = SchdLoader()
              
        
        self.AI_1 = openai_client
        #self.AI_1_MODEL = "gpt-4" // This model does not support json_object response format
        #self.AI_1_MODEL = "gpt-4o-mini" // This model is not very smart
        self.AI_1_MODEL = "gpt-3.5-turbo"
        
        self.bridge['conn'] = ''
        self.apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=WEBSOCKET_CONNECTIONS)
        
        
        
    
        
    def print_rt(self,output,type):
        
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
    
    
        
           
    def perception_and_interpretation(self,input):
        
        action = 'perception_and_interpretation'
        print(f'Running: {action}')
        
        
        self.print_rt('Trying to understand the context of the message...','text')
        
        input_template = '<raw message string>'
        output_template = {
                "type":"text",
                "message":"<sanitized version of the message>",
                "language":"<detected language>",
                "sentiment":"[<list of sentiments>]"
            }
        
        
        payload = {   
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
        self.print_rt(response['output'],'json')
        
        
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        return {'success':True,'action':action,'input':input,'output':response}
        
        
    
    def process_information(self,input):
        
        action = 'process_information'
        print(f'Running: {action}')
        
        self.print_rt('Setting up a goal...','text')
        
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
        self.print_rt(response['output'],'json')
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        return {'success':True,'action':action,'input':input,'output':response}
        
        
    def reasoning_and_planning(self,input):
        
        action = 'reasoning_and_planning'
        print(f'Running: {action}')
        
        self.print_rt('Creating a plan of action...','text')
        
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
        self.print_rt(response['output'],'json')
        
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        
        return {'success':True,'action':action,'input':input,'output':response}
    
    
    
    def generate_commands(self,plan):
        
        action = 'generate_commands'
        print(f'Running: {action}')
        
        self.print_rt('Generating the commands to make it happen...','text')
        
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
                "You are an agent that creates RESTful queries \n"
            ),
            'user_content': f"{self.bridge['config']['prompt_4_execution']}",
            'input_template':f"{input_template}",
            'output_template':f"{output_template}",
            'user_input': f" This is the input: {plan}"
        }
        
        response = self.run_prompt(payload)
        
        print(f'generate_commands > response > {response}')
        self.bridge['commands'] = response['output']['commands']
        self.print_rt(response['output']['commands'],'json')
        
        
        if 'success' not in response:
            return {'success':False,'action':action,'input':input,'output':response}
        
        
        return {'success':True,'action':action,'input':input,'output':response}
    
    
    
    
    def run_command(self,command):
        
        action = 'run_command'
        print(f'Running: {action}')
        
        print('Running the following command:')
        print(command)
        self.print_rt(f'running: {command}','command')
        
        return {'success':True,'action':action,'input':command,'output':'mock-executed'}
        
    
    
    '''def execute_plan_NEW(self,plan):
        
        action = 'execute_plan'
        print(f'Running: {action}')
        
        last_response = {}
        for step in plan:    
            step['last_response']   
            response = self.SHL.load_and_run(step['tool'], payload = step['parameters'])
            last_response = response'''
        
            
            
    
    
    def execute_plan(self,plan):
        
        action = 'execute_plan'
        print(f'Running: {action}')
        

        self.print_rt('Executing plan...','text')
         
        #1. Call function that generates the RESTFUL commands
        response_1 = self.generate_commands(plan)  
        if not response_1:
            return {'success':False,'action':action,'input':plan,'output':response_1}
        
        
        #2. Iterate through the list of commands and execute each one at a time until done. 
        executions = []
        print('RESPONSE_1 >>>')
        print(response_1)
        for command in response_1['output']['output']['commands']:
            # This is like a dynamic funnel
            response_2 = self.run_command(command)
            if not response_2:
                return {'success':False,'action':action,'input':command,'output':response_2}
            executions.append(response_2)
        
        
        return {'success':True,'action':action,'input':plan,'output':executions}
            

    
    def new_chat_message_document(self,message):
        
        action = 'new_chat_message_document'
        print(f'Running: {action}')  
        #self.print_rt('Creating new chat document...','text')
        
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
         
        response = self.CHC.create_message(self.bridge['entity_type'],self.bridge['entity_id'],self.bridge['thread'],message_object) 
        
        self.bridge['chat_id'] = response['document']['_id']       
        print(f'Response:{response}')
    
        if 'success' not in response:
            return {'success':False,'action':action,'input':message_object,'output':response}
        
        return {'success':True,'action':action,'input':message_object,'output':response}
    

    
    def update_chat_message_document(self,update):
        
        action = 'update_chat_message_document'
        print(f'Running: {action}')
        #self.print_rt('Updating chat document...','text')
        
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
        
        
        
    def new_chat_workspace_document(self,workspace_type,config,data):
        
        action = 'new_chat_workspace_document'
        print(f'Running: {action}')  
        #self.print_rt('Creating new chat document...','text')
        
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
            
        
        
        
        # Step 0a: Load Action
        response_0a = self.load_action(payload)
        results.append(response_0a)
        if not response_0a['success']: return {'success':False,'action':action,'output':results}
        
        print('Starting step 0')
        # Step 0: Create thread/message document
        response_0 = self.new_chat_message_document(payload['data'])
        results.append(response_0)
        if not response_0['success']: return {'success':False,'action':action,'output':results}
        

         
        # Step 1: Perception and Interpretation
        response_1 = self.perception_and_interpretation(payload['data'])
        results.append(response_1)
        if not response_1['success']: return {'success':False,'action':action,'output':results}
        
        
        # Step 2: Process Information
        response_2 = self.process_information(self.bridge['interpretation'])
        results.append(response_2)
        if not response_2['success']: return {'success':False,'action':action,'output':results}
        
        
        '''# Early finish, Request rejected
        if response_2['output']['goal'] == 'reject_booking':
            return {'success':True,'message':'Booking rejected','action':action,'output':results}'''
        
        
        
        
        # Step 3: Reasoning and Planning
        response_3 = self.reasoning_and_planning(self.bridge['information'])
        results.append(response_3)
        if not response_3['success']: return {'success':False,'action':action,'output':results}
        
        
        
        '''
        # Step 4: Validate Plan
        response_4 = self.validate_plan()
        results.append(response_4)
        if not response_4['success']: return {'success':False,'output':results}
        '''
    
        
        # Step 5: Execute Plan
        response_5 = self.execute_plan(self.bridge['plan'])
        results.append(response_5)
        if not response_5['success']: return {'success':False,'output':results}
        
        
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
    

        self.print_rt('Cycle completed','text')
        self.bridge['conn'] = ''
            
                  
        #All went well, report back
        return {'success':True,'action':action,'message':'run completed','output':results}
        
          

# Test block
if __name__ == '__main__':
    # Creating an instance
    pass

    
    
    
 