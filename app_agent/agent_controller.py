from app_schd.schd_actions import SchdActions
#from app_schd.schd_controller import SchdController

class AgentController:

    def __init__(self,tid=None,ip=None):

        #self.SHC = SchdController()
        self.SHK = SchdActions()
        
        

    
    def triage(self,payload):
        
        action = 'triage'


        #1. Get a list of all the available actions
        #2. Compare the message with utterances from the actions in the list
        #3. If you find a match, declare that action as the active action
        
        '''
        handler = 'x'
        # Call handler   
        response = self.SHC.direct_run(handler, payload) # REPLACE THIS FOR THE TRIAGE. THE TRIAGE WILL USE SHC.direct_run once it determines what handler to use
        '''
        
        result = self.SHK.run(payload) 
        
        if 'success' in result and not result['success']:
            
            return {'success':False,'action':action,'output':result,'status':400} 
        
        return {'success':True,'action':action,'output':result,'status':200}
        
          
        