# chat_model.py

from flask import redirect,url_for, jsonify, current_app, session

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError
from env_config import DYNAMODB_CHAT_TABLE

class ChatModel:

    def __init__(self,tid=False,ip=False):

        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Adjust region if needed
        self.chat_table = self.dynamodb.Table(DYNAMODB_CHAT_TABLE)  

        
    def list_chat(self,index,limit=50,lastkey=None,sort='asc'):
        
        result = {}

        try:
            # Build the query parameters with KeyConditionExpression
            query_params = {
                'TableName': DYNAMODB_CHAT_TABLE,
                'KeyConditionExpression': Key('index').eq(index),
                'Limit': limit,
                "ScanIndexForward": True if sort == 'asc' else False
            }

            # Add the ExclusiveStartKey to the query parameters if provided (for pagination)
            if lastkey:
                query_params['ExclusiveStartKey'] = lastkey

            # Query DynamoDB to get items with matching PK and SK prefix
            response = self.chat_table.query(**query_params)
            
            # Extract items and pagination key
            items = response.get('Items', [])
            endkey = response.get('LastEvaluatedKey')  # Pagination key for next query

            # Build the result
            result ['success'] = True
            result ['items'] = items
            result ['lastkey'] = endkey  # This will be passed as 'lastkey' in the next call if needed
            
            return result

        except (BotoCoreError, ClientError) as e:
            
            result['success'] = False
            result['message'] = 'Items could not be retrieved'
            result['error'] = str(e)
            status = 400
            return result
        
        
        
    def create_chat(self,data):

        
        try:
            response = self.chat_table.put_item(Item=data)
            current_app.logger.debug('MODEL: Created chat successfully:'+str(data))
            return {
                "success":True, 
                "message": "Chat created", 
                "document": data,
                "status" : response['ResponseMetadata']['HTTPStatusCode']
                }
        except ClientError as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "document": data,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
        
    # NOT USED
    def update_chat(self,data):

        
        try:
            response = self.chat_table.put_item(Item=data)
            current_app.logger.debug('MODEL: Updated entity successfully:'+str(data))
            return {
                "success":True, 
                "message": "Chat updated", 
                "document": data,
                "status" : response['ResponseMetadata']['HTTPStatusCode']
                }
        except ClientError as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "document": data,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }

      
    # NOT USED  
    def delete_chat(self,**data):

        keys = {
            'irn': data['irn'],
            'time': data['time']
        }

        try:
            response = self.chat_table.delete_item(Key=keys)
            current_app.logger.debug('MODEL: Deleted Chat:' + str(data))
            return {
                "success":True,
                "message": "Entity deleted", 
                "document": data,
                "status" : response['ResponseMetadata']['HTTPStatusCode'] 
                }
        
        except ClientError as e:
            return {
                "success":False,
                "message": e.response['Error']['Message'],
                "document": data,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }

            
    