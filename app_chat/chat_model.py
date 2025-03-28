# chat_model.py

from flask import redirect,url_for, jsonify, current_app, session

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import BotoCoreError, ClientError
from env_config import DYNAMODB_CHAT_TABLE

class ChatModel:

    def __init__(self,tid=False,ip=False):

        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Adjust region if needed
        self.chat_table = self.dynamodb.Table(DYNAMODB_CHAT_TABLE)  

        
    def list_chat(self,index,limit=50,lastkey=None,sort='asc'):
        
        result = {}
        all_items = []

        try:
            while True:
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
                all_items.extend(items)  # Add current page items to the complete list
                
                # Get the pagination key for next query
                lastkey = response.get('LastEvaluatedKey')
                
                # If there's no more pages, break the loop
                if not lastkey:
                    break

            # Build the result with all items
            result['success'] = True
            result['items'] = all_items
            
            return result

        except (BotoCoreError, ClientError) as e:
            
            result['success'] = False
            result['message'] = 'Items could not be retrieved'
            result['error'] = str(e)
            status = 400
            return result
        
    
    def get_chat(self, index, message_id):
        
        result = {}
        
        current_app.logger.debug(f'get_chat: {index} > {message_id}')
        
        try:
            # Build the query parameters with KeyConditionExpression

            
            query_params = {
                'TableName': DYNAMODB_CHAT_TABLE,
                'KeyConditionExpression': Key('index').eq(index),
                'FilterExpression': Attr('_id').eq(message_id)
            }
            


            current_app.logger.debug(f'Query parameters: {query_params}')

            # Query DynamoDB to get the specific item
            response = self.chat_table.query(**query_params)
            current_app.logger.debug(f'Raw DynamoDB response: {response}')
            
            # Extract items
            items = response.get('Items', [])
            current_app.logger.debug(f'Extracted items: {items}')
            
            if not items:
                current_app.logger.debug(f'No items found for index: {index} and message_id: {message_id}')
                result['success'] = False
                result['message'] = 'Item not found'
                return result
            
            print(f'CHM:get_chat > {items[0]}')
            
            # Build the result
            result['success'] = True
            result['item'] = items[0]  # Return single item
            
            return result

        except Exception as e:
            current_app.logger.error(f"Error in get_chat: {str(e)}")
            result['success'] = False
            result['message'] = 'Item could not be retrieved'
            result['error'] = str(e)
            return result
        
        
        
    def create_chat(self,data):
        
        print(f'create_chat > input:{data}')

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
            print(f'create_chat > error:{e}')
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "document": data,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
        
        
        
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

            
    