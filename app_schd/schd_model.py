import boto3
import json
from env_config import TANK_ROLE_ARN, TANK_API_GATEWAY_ARN, TANK_AWS_REGION



class SchdModel:
    
    
    def __init__(self,tid=False,ip=False):
        
        self.client = boto3.client('events', region_name=TANK_AWS_REGION)
        

    def create_https_target_event(self, rule_name, schedule_expression):
        """
        Create an EventBridge rule that triggers an HTTPS POST request to a specified Flask endpoint.
        
        Parameters:
        - rule_name: Name of the EventBridge rule.
        - schedule_expression: Cron or rate expression (e.g., 'rate(1 minute)').
        - target_url: The HTTPS endpoint that EventBridge should send events to.
        """
        # Create or update the EventBridge rule
        response = self.client.put_rule(
            Name=rule_name,
            ScheduleExpression=schedule_expression,
            State='ENABLED'
        )
        rule_arn = response['RuleArn']

        # Set the HTTPS target for the rule

        self.client.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    'Id': rule_name+'_target',
                    'Arn':  TANK_API_GATEWAY_ARN+'/op3rator_www/GET/_schd/execute_rule', # ARN of the API Gateway
                    'RoleArn': TANK_ROLE_ARN,  # IAM role to allow EventBridge to invoke HTTPS
                    'Input': json.dumps({"message": "Trigger this:"+rule_name}),
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

        return f"Rule {rule_name} created successfully."
    
    
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
    
    
    
    