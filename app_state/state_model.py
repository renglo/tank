from flask import redirect,url_for, jsonify, current_app, session, request

import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import uuid
from decimal import Decimal
from env_config import DYNAMODB_BLUEPRINT_TABLE


class StateModel:

    def __init__(self,tid=False,ip=False):

        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Adjust region if needed
        self.state_table = self.dynamodb.Table(DYNAMODB_BLUEPRINT_TABLE)  # Replace with your table name
            

    def get_state(self,name,v):

        irn = 'irn:state:irma:'+ name

        current_app.logger.debug('Get State '+irn+' v:'+v)
        

        try:
            if v == 'last':
                response = self.state_table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('irn').eq(irn),
                    ScanIndexForward=False # Show latest state versions first
                )
                items = response.get('Items', [])
                
                if len(items)==0:
                    return {"success":False,"message": "Document not found"}
                item = items[0]
                #current_app.logger.info('items from DB:'+str(items))
                       
            else:
                response = self.state_table.get_item(Key={'irn': irn, 'version': v})
                item = response.get('Item')

            if item:
                return item
            else:
                return {"success":False,"message": "Document not found"}
        except ClientError as e:
            return {"error": e.response['Error']['Message']}
        
