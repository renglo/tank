from flask import current_app

from app_data.data_controller import DataController
from app_docs.docs_controller import DocsController
from app_blueprint.blueprint_controller import BlueprintController

from app_schd.schd_loader import SchdLoader
from app_schd.schd_model import SchdModel

from datetime import datetime

import json

class SchdController:

    def __init__(self):

        self.DAC = DataController()
        self.DCC = DocsController()
        self.BPC = BlueprintController()
        self.SHM = SchdModel()
        self.SHL = SchdLoader()
        


    def convert_module_name_to_class(self,input_string):
        # Step 1: Split the string at '/'
        after_slash = input_string.split('/')[-1]
        
        # Step 2: Replace '_' with spaces
        words = after_slash.replace('_', ' ')
        
        # Step 3: Capitalize the first letter of each word
        capitalized_words = words.title()
        
        # Step 4: Remove spaces
        result = capitalized_words.replace(' ', '')
        
        return result
    
    
    def find_rule(self,portfolio,org,timer):
        
        rule_name = "cronjob_"+portfolio+"_"+org+"_"+timer        
        result = self.SHM.find_rule(rule_name)
        
        return result
        
    
    def create_rule(self,portfolio,org,timer,schedule_expression,handler):
        '''
        Function used to create the cronjob
        '''
        
        rule_name = "cronjob_"+portfolio+"_"+org+"_"+timer 
        
        payload = {
            'portfolio':portfolio,
            'org':org,
            'handler':handler
        }
        
        result = self.SHM.create_https_target_event(
            rule_name=rule_name,
            schedule_expression=schedule_expression,
            payload=payload
        )
        
        '''
        result = SHM.create_https_target_event(
            rule_name='cronrule_'+str(random.randint(1000, 9999)),
            schedule_expression='rate(1 minute)',
            payload=payload
        )'''
        
        return result
        
        
    def verify_rule(self,portfolio,org,timer):
        
        rule_name = "cronjob_"+portfolio+"_"+org+"_"+timer        
        result = self.SHM.find_rule(rule_name)
        
        return result
    
   
    # COMPLETE  
    def create_job_run(self,portfolio,org,payload):
        '''
        Function that is called by the cronjob 
        '''
        
        result = []
        action = 'create_job_run'
        #1. Check if the job exists. Get the document
        if 'schd_jobs_id' not in payload:
            return {'success': False,'action':action,'input':payload,'message': 'No Job Id'}, 400  
        else:
            response_1 = self.DAC.get_a_b_c(portfolio,org,'schd_jobs',payload['schd_jobs_id'])
            if 'error' not in response_1:
                jobdoc = response_1
            else:
                result.append(response_1)
                return {'success': False,'action':'get_job_document' ,'message': 'Error getting job','input':payload,'output':response_1}, 400 
            
         
        current_app.logger.debug('Job document check:',response_1)
        
        #2. Create the schd_runs document 
        action = 'create_run'  
        # Check that payload['trigger'] is one of these: [manual, call, cron]
        if payload.get('trigger') not in ['manual', 'call', 'cron']:
            result.append({'success': False,'action':action,'input':payload,'message': 'Invalid trigger value'})
            return result, 400  
        
        if 'author' not in payload:
            payload['author'] = ''
        
        payload['status'] = 'new'
        payload['time_queued'] = str(int(datetime.now().timestamp()))
        payload['time_executed'] = '.'
        payload['output'] = '.'
        
        response_2, status = self.DAC.post_a_b(portfolio,org,'schd_runs',payload)
        
        #{'success': True, 'message': 'Item saved', 'path': '160c4e266ea3/5e7f29c29084/schd_runs/f15c58e4-aa2d-4780-8616-bd1834ca777c'}
        
        current_app.logger.debug('Create the schd_runs document:')
        current_app.logger.debug(response_2)
        result.append({'success':True,'action':action,'input':payload,'output':response_2})
        
        
        #3. Run  the handler indicated in the schd_jobs document
            #NOTICE: This indicates a Synchronous process which is not ideal
            # Ideally, this route should only store the schd_runs document and an asychronous process
            # should pick up and execute one at a time (or in parallel if you use many workers).
            
            
            
        action = 'call_handler'
        
        response_3 = {'success':False,'output':[]}
        
        
        if 'handler' in jobdoc:
            handler_name = jobdoc['handler']
            handler_class = self.convert_module_name_to_class(jobdoc['handler'])
        
            # Example data to pass to classes
            # You could send anything coming in the payload
            handler_input_data = {'portfolio': portfolio,'org':org,'handler':handler_name}

            response_3 = self.SHL.load_and_run(handler_name, handler_class, payload = handler_input_data)
            #response_3 = {'success':False,'output':[]}
            
            
            current_app.logger.debug(f'Handler output:{response_3}')
            
            
            if not response_3['success']:
                result.append({'success':False,'action':action,'handler':handler_name,'input':handler_input_data,'output':response_3})
                return result, 400
            
            result.append({'success':True,'action':action,'handler':handler_name,'input':handler_input_data,'output':response_3})
          
            #UP FROM HERE , OK   
        
        else: 
            result.append({'success':False,'action':action,'handler':'','message':'No handler in the job document'}) 
            return result, 400
        
        
        
        json_doc = json.dumps(response_3)
        
        #Save response_3 to S3, You'll store the s3 url in the change['output']
        response_3b = self.DCC.a_b_post(portfolio,org,'schd_jobs',json_doc,'application/json',False)
        
        
        
        
        #DOWN FROM HERE , OK
        
        if response_3b['success']:
            if 'path' in response_3b:
                output_doc = response_3b['path']
            else:
                output_doc = 'Output unavailable..'
        else:
            output_doc = 'Output unavailable.'
        
           
        
            
        
        #4. Record the results from the handler run in the schd_runs document, return 
        
        action = 'record_results'
        run_id = response_2['path'].split('/')[-1]
        changes = {}
    
        changes['output'] = output_doc
        changes['status'] = 'executed'
        changes['time_executed'] = str(int(datetime.now().timestamp()))
            
        response_4, status = self.DAC.put_a_b_c(portfolio,org,'schd_runs',run_id,changes)
        
        current_app.logger.debug(f'Record handler output in run document:{response_4}')
        result.append({'action':action,'input':changes,'output':response_4})
        
        self.DAC.refresh_s3_cache(portfolio, org, 'schd_runs', None)
        
        
        return result, 200
        
        
    
    def direct_run(self,tool,handler,payload):
           
        result = []

        action = 'direct_run'
             
        response = {'success':False,'output':[]}
        
        # A way to limit the calls to this endpoint is to make each one of these runs have the same name as a blueprint. 
        # And before every run, we could fetch the blueprint. It if doesn't exist we abort the call. 
        # It makes sense that there is a blueprint for every RPC as it shows the inputs of the call. 
        # We could store every call to the RPC as a document. The ring itself is the name of the blueprint. 
        
        blueprint = self.BPC.get_blueprint('irma',handler,'last')
        
        if 'fields' not in blueprint:
            result.append({'success':False,'action':action,'handler':'','message':'No valid handler'}) 
            return result, 400
            
        else:
            handler_name = tool + '/' + handler
            handler_class = self.convert_module_name_to_class(handler_name)
            handler_input_data = payload

            response = self.SHL.load_and_run(handler_name, handler_class, payload = handler_input_data)
            
            current_app.logger.debug(f'Handler output:{response}')
            
            
            if not response['success']:
                result.append({'success':False,'action':action,'handler':handler_name,'input':handler_input_data,'output':response})
                return result, 400
            
            result.append({'success':True,'action':action,'handler':handler_name,'input':handler_input_data,'output':response})
          

   
        return result, 200