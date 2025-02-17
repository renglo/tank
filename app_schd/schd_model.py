import boto3
import json
from env_config import TANK_ROLE_ARN, TANK_API_GATEWAY_ARN, TANK_AWS_REGION, TANK_ENV



class SchdModel:
    
    
    def __init__(self,tid=False,ip=False):
        
        self.client = boto3.client('events', region_name=TANK_AWS_REGION)
        

    def create_https_target_event(self, rule_name, schedule_expression, payload):
        """
        Create an EventBridge rule that triggers an HTTPS POST request to a specified Flask endpoint.
        
        Parameters:
        - rule_name: Name of the EventBridge rule.
        - schedule_expression: Cron or rate expression (e.g., 'rate(1 minute)').
        - target_url: The HTTPS endpoint that EventBridge should send events to.
        """
        # Create or update the EventBridge rule
        
        try:
            response_1 = self.client.put_rule(
                Name=rule_name,
                ScheduleExpression=schedule_expression,
                State='ENABLED'
            )
            if not 'RuleArn' in response_1:
                return {'success':False,'output':response_1}
               
            rule_arn = response_1['RuleArn']
        
        except as e:
            
            '''
            A successful response_1 looks like this: 
            {
                "RuleArn": "arn:aws:events:us-east-1:123456789012:rule/my-scheduled-rule"
            }
            
            You could get the following errors: 
            
            1. AccessDeniedException: The IAM role doesn’t have the necessary permissions to create the rule.
                Solution: Ensure the AWS user has events:PutRule permission in IAM.
            2. ValidationException: The ScheduleExpression is incorrect.
                Solution: Make sure you are using a valid cron or rate expression (rate(5 minutes), cron(0 12 * * ? *)).
            3. LimitExceededException: You have reached the maximum number of rules allowed.
                Solution: Delete unused rules or request a quota increase.
            '''
        
            return {'success':False,'output':e}
        

        
        
        # Set the HTTPS target for the rule

        try:
            response_2 = self.client.put_targets(
                    Rule=rule_name,
                    Targets=[
                        {
                            'Id': rule_name+'_target',
                            'Arn':  TANK_API_GATEWAY_ARN+'/'+TANK_ENV+'/GET/_schd/execute_run', # ARN of the API Gateway
                            'RoleArn': TANK_ROLE_ARN,  # IAM role to allow EventBridge to invoke HTTPS
                            'Input': json.dumps(payload),
                            'HttpParameters': {
                                'HeaderParameters': {
                                    'Content-Type': 'application/json'
                                },
                                'PathParameterValues': [],
                                'QueryStringParameters': {}
                            }
                        }
                    ]
        
            )
        except as e:
            
            '''
            A successful response looks like this:
            
            {
                "FailedEntryCount": 0,
                "FailedEntries": []
            }
            
            

            1.	Invalid Target ARN: Ensure the ARN provided is correct and belongs to a supported service (Lambda, SQS, etc.).
            2.	Permission Issues: The EventBridge rule might not have permissions to invoke the target (check IAM roles).
            3.	Malformed Input: Ensure the Input JSON is properly formatted.      
            '''
            
            return {'success':False,'output':e}
        
        

        #return f"Rule {rule_name} created successfully."
        input = {
            'rule_name':rule_name,
            'schedule_expression':schedule_expression,
            'payload':payload  
            }
        
        return {'success':True,
                'message':'Rule created successfully',
                'input':input,
                'output':response
                } 
    
    
     
    def find_rule(self, rulename):
        """
        Retrieve events that need to be executed within a time window.
        
        Sample: 
        {
            "Name": "MyRule1",
            "Arn": "arn:aws:events:us-east-1:123456789012:rule/MyRule1",
            "EventPattern": "{\"source\":[\"aws.ec2\"]}",
            "State": "ENABLED",
            "Description": "This is my first rule",
            "RoleArn": "arn:aws:iam::123456789012:role/MyRole",
            "ManagedBy": "AWS",
            "ScheduleExpression": "rate(5 minutes)",
            "EventBusName": "default",
            "Targets": [
                {
                    "Id": "Target1",
                    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:MyFunction",
                    "Input": "{\"key1\":\"value1\"}"
                }
            ]
        }
        """
        
        paginator = self.client.get_paginator('list_rules')

        for page in paginator.paginate():
            for rule in page['Rules']:
                if 'Name' in rule:
                    if rule['Name'] == rulename :
                        if rule['State'] == 'ENABLED': 
                            return {'success':True,'input':rulename,'output':rule} 

        return {'success':False,'input':rulename,'output':False}
  
  
    
    #NOT USED
    def get_scheduled_events(self, start_time, end_time):
        """
        Retrieve events that need to be executed within a time window.
        """
        paginator = self.client.get_paginator('list_rules')
        rules = []

        for page in paginator.paginate():
            for rule in page['Rules']:
                if 'ScheduleExpression' in rule:
                    # Filter rules within the time window
                    schedule_expression = rule['ScheduleExpression']
                    if self._is_within_time_window(schedule_expression, start_time, end_time):
                        rules.append(rule)

        return rules

    
    #NOT USED
    def _is_within_time_window(self, schedule_expression, start_time, end_time):
        """
        Check if a rule's schedule falls within a specific time window.
        (This is a placeholder; implement cron parsing for real checks.)
        """
        # Placeholder logic: assumes hourly cron schedule
        if 'rate' in schedule_expression or 'cron' in schedule_expression:
            now = datetime.utcnow()
            return start_time <= now <= end_time
        return False
    
    
    
    