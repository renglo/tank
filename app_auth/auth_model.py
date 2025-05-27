from flask import redirect,url_for, jsonify, current_app, session

import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import uuid
from decimal import Decimal
from env_config import DYNAMODB_ENTITY_TABLE,DYNAMODB_REL_TABLE,COGNITO_APP_CLIENT_ID,COGNITO_USERPOOL_ID,COGNITO_REGION



class AuthModel:

    def __init__(self,tid=False,ip=False):

        #Dynamo
        self.dynamodb = boto3.resource('dynamodb')
        self.entity_table = self.dynamodb.Table(DYNAMODB_ENTITY_TABLE)
        self.rel_table = self.dynamodb.Table(DYNAMODB_REL_TABLE)

        #SES
        self.cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION) 
        self.USER_POOL_ID = COGNITO_USERPOOL_ID  # Replace with your user pool ID


 #-------------------------------------------------AWS COGNITO


     #TANK-FE
    def check_user_by_email(self,email):
        try:
            # Get the email from the request
            #email = request.json.get('email')
            if not email:
                return jsonify({'error': 'Email is required'}), 400

            # List users by email filter
            response = self.cognito_client.list_users(
                UserPoolId=self.USER_POOL_ID,
                Filter=f'email = "{email}"'  # Filter by email
            )

            # Check if a user was found
            if response['Users']:
                user = response['Users'][0]  # Get the first user from the response

                # Extract Cognito User ID (the 'sub' attribute)
                cognito_user_id = next(
                    (attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'sub'), 
                    None
                )

                if cognito_user_id:
                    return {
                        "success":True, 
                        "message": "User found", 
                        "document": {'email':email,'cognito_user_id':cognito_user_id},
                        "status" : 200
                    } 
                        
            return {
                "success":False, 
                "message": "User not found",
                "status" : 404
            }

        except self.cognito_client.exceptions.UserNotFoundException:
            return {
                "success":False, 
                "message": "User not found (UserNotFoundException)",
                "status" : 404
            }
        except Exception as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
            }
        
    #DEPRECATED
    def cognito_user_create_with_permanent_password(self,email, password,first='FIRST',last='LAST'):
        try:
            # Step 1: Create the user with a temporary password
            response_1 = self.cognito_client.admin_create_user(
                UserPoolId=COGNITO_USERPOOL_ID,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'given_name', 'Value': first },
                    {'Name': 'family_name','Value': last }
                ],
                TemporaryPassword=password,
                MessageAction='SUPPRESS'  # Optionally suppress the email notification
            )

            
            # Step 2: Set the password as permanent
            response_2 = self.cognito_client.admin_set_user_password(
                UserPoolId=COGNITO_USERPOOL_ID,
                Username=email,
                Password=password,
                Permanent=True  # Make the password permanent
            )

            print(f"User {email} created with a permanent password.")

        except Exception as e:
            print(f"Error creating user: {str(e)}")


    
    def cognito_user_permanent_password_assign(self,email,password):
        try:
            
            # Set the password as permanent
            response = self.cognito_client.admin_set_user_password(
                UserPoolId=COGNITO_USERPOOL_ID,
                Username=email,
                Password=password,
                Permanent=True  # Make the password permanent
            )

            print(f"User {email} created with a permanent password.")
            # Return success message
            return {
                'success': True,
                'message': 'Password assigned',
                'document': response,
                'status': 200
            }

        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'status': 400
            }
        


    def cognito_user_create(self,email,first='FIRST',last='LAST'):
        try:
            
            temporary_password = 'TempPassword123!'
            # Create the user in the Cognito User Pool
            response = self.cognito_client.admin_create_user(
                UserPoolId=COGNITO_USERPOOL_ID,
                Username=email,
                UserAttributes=[
                    {
                        'Name': 'email',
                        'Value': email
                    },
                    {
                        'Name': 'email_verified',
                        'Value': 'true'
                    },
                    {
                        'Name': 'given_name',
                        'Value': first
                    },
                    {
                        'Name': 'family_name',
                        'Value': last
                    }
                ],
                TemporaryPassword=temporary_password,  # Optional: Set a temporary password for the user
                MessageAction='SUPPRESS'  # Optional: Suppresses the sending of the welcome email
            )

            # Return success message
            return {
                'success': True,
                'message': 'User created successfully',
                'document': response,
                'status': 200
            }

        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'status': 400
            }


    #NOT USED 
    def cognito_user_login_challenge(self,email,new_password):

        temporary_password = 'TempPassword123!'
        
        try:
            # Step 1: Authenticate the user with the email and temporary password
            auth_response = self.cognito_client.admin_initiate_auth(
                UserPoolId=COGNITO_USERPOOL_ID,
                ClientId=COGNITO_APP_CLIENT_ID,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': email,  # Use email as the username
                    'PASSWORD': temporary_password
                }
            )

            # Step 2: Check if a password change is required
            if auth_response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
                # Step 3: Respond to the password challenge by providing the new password
                challenge_response = self.cognito_client.respond_to_auth_challenge(
                    ClientId=COGNITO_APP_CLIENT_ID,
                    ChallengeName='NEW_PASSWORD_REQUIRED',
                    ChallengeResponses={
                        'USERNAME': email,  # Use email as the username
                        'NEW_PASSWORD': new_password,
                        'PASSWORD': temporary_password
                    },
                    Session=auth_response['Session']
                )
                return {
                    'success': True,
                    'message': 'Password changed successfully. User is now authenticated.',
                    'document': challenge_response['AuthenticationResult'],
                    'status': 200
                }

            else:
                return {
                    'success': False,
                    'message': 'Unexpected challenge. Expected NEW_PASSWORD_REQUIRED.',
                    'status': 400
                }

        except self.cognito_client.exceptions.NotAuthorizedException:
            return {'success': False, 'message': 'Invalid temporary password', 'status':401}
        except Exception as e:
            return {'success': False, 'message': str(e),'status':500}

            





#---------------------------------------------------- AWS SES



    def send_email(self, sender, recipient, subject, body_text, body_html):
        # Initialize the SES client
        ses_client = boto3.client('ses', region_name=COGNITO_REGION)  # Replace with your AWS region

        # Email details
        email_data = {
            'Source': sender,
            'Destination': {
                'ToAddresses': [
                    recipient,
                ],
            },
            'Message': {
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': body_text,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': body_html,
                        'Charset': 'UTF-8'
                    }
                }
            }
        }

        try:
            # Send the email
            response = ses_client.send_email(**email_data)

            if response['MessageId']:
                return{
                    "success":True, 
                    "message": "Email sent", 
                    "document": {
                        'MessageId':response['MessageId']
                        },
                    "status" : response['ResponseMetadata']['HTTPStatusCode']
                }
 
        except ClientError as e:
            '''
            example e: 'Email address is not verified. The following identities failed the check in region US-EAST-1: user@email.com'
            '''
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "document": e.response,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
            }
            


    





#-------------------------------------------------MODEL/ENTITIES


    def list_entity(self,index,limit=50,lastkey=None):

        try:
            # Build the query parameters
            query_params = {
                'KeyConditionExpression': boto3.dynamodb.conditions.Key('index').eq(index),
                'Limit': int(limit)
            }
            
            # Add the ExclusiveStartKey to the query parameters if provided
            if lastkey:
                query_params['ExclusiveStartKey'] = {'index': index, 'ref': lastkey}

            # Query DynamoDB to get items with the same partition key
            response = self.entity_table.query(**query_params)
            items = response.get('Items', [])
            endkey = response.get('LastEvaluatedKey') # This will become the first in the next page 

            documents = {
                "items": items,
                "lastkey": endkey
            }

            return {
                "success":True, 
                "message": "Documents found", 
                "document": documents,
                "status" : response['ResponseMetadata']['HTTPStatusCode']
            }
        
        except ClientError as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }



    def get_entity(self,index,id):
   
        try:
            current_app.logger.debug('INDEX:'+index)
            current_app.logger.debug('ID:'+id)
            response = self.entity_table.get_item(Key={'index':index,'_id':id})
            item = response.get('Item')
            current_app.logger.debug('MODEL: get_entity:')
            current_app.logger.debug(response)
            current_app.logger.debug('MODEL: item:')
            current_app.logger.debug(item)
            

            if item:
                #return item
                return {
                    "success":True, 
                    "message": "Entity found", 
                    "document": item,
                    "status" : response['ResponseMetadata']['HTTPStatusCode']
                    }
            else:
                return {
                    "success":False, 
                    "message": "Entity not found",
                    "status" : 404
                    }
        except ClientError as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
        
    
    def create_entity(self,data):

        data['modified'] = datetime.now().isoformat()
        
        try:
            response = self.entity_table.put_item(Item=data)
            current_app.logger.debug('MODEL: Created entity successfully:'+str(data))
            return {
                "success":True, 
                "message": "Entity created", 
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
        


    def update_entity(self,data):

        data['modified'] = datetime.now().isoformat()
        
        try:
            response = self.entity_table.put_item(Item=data)
            #current_app.logger.debug('MODEL: Updated entity successfully')
            return {
                "success":True, 
                "message": "Entity updated", 
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
        



    def delete_entity(self,**entity_document):

        keys = {
            'index': entity_document['index'],
            '_id': entity_document['_id']
        }

        try:
            response = self.entity_table.delete_item(Key=keys)
            current_app.logger.debug('MODEL: Deleted Entity:' + str(entity_document))
            return {
                "success":True,
                "message": "Entity deleted", 
                "document": entity_document,
                "status" : response['ResponseMetadata']['HTTPStatusCode'] 
                }
        
        except ClientError as e:
            return {
                "success":False,
                "message": e.response['Error']['Message'],
                "document": rel_document,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }




    def get_rel(self,index,rel):
   
        try:
            response = self.rel_table.get_item(Key={'index':index,'rel':rel})
            item = response.get('Item')

            if item:
                #return item
                return {
                    "success":True, 
                    "message": "Entity found", 
                    "document": item,
                    "status" : 200
                    }
            else:
                return {
                    "success":False, 
                    "message": "Entity not found",
                    "status" : 404
                    }
        except ClientError as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
        

    
    def list_rel(self,index,limit=50,lastkey=None):

        try:
            # Build the query parameters
            query_params = {
                'KeyConditionExpression': boto3.dynamodb.conditions.Key('index').eq(index),
                'Limit': int(limit)
            }
            
            # Add the ExclusiveStartKey to the query parameters if provided
            if lastkey:
                query_params['ExclusiveStartKey'] = {'index': index, 'ref': lastkey}

            # Query DynamoDB to get items with the same partition key
            response = self.rel_table.query(**query_params)
            items = response.get('Items', [])
            endkey = response.get('LastEvaluatedKey') # This will become the first in the next page 

            documents = {
                "items": items,
                "lastkey": endkey
            }

            return {
                "success":True, 
                "message": "Documents found", 
                "document": documents,
                "status" : response['ResponseMetadata']['HTTPStatusCode']
            }
        
        except ClientError as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
        

    def list_rel_prefix(self,partition_key_value,prefix):
        

        if not partition_key_value or not prefix:
            return {
                    "success":False, 
                    "message": 'Partition key and prefix are required',
                    "status" : 400
                    }

        try:
            # Query the table with the begins_with function on the sort key
            response = self.rel_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('index').eq(partition_key_value) &
                                    boto3.dynamodb.conditions.Key('rel').begins_with(prefix)
            )

        
            return {
                "success":True, 
                "message": "Documents found", 
                "document": response['Items'],
                "status" : response['ResponseMetadata']['HTTPStatusCode']
            }

        except Exception as e:
            return {
                "success":False, 
                "message": e.response['Error']['Message'],
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
   
        



    def create_rel(self, **rel_document):

        
        try:
            response = self.rel_table.put_item(Item=rel_document)
            current_app.logger.debug('MODEL: Created Relationship:' + str(rel_document))
            return {
                "success":True,
                "message": "Rel created", 
                "document": rel_document,
                "status" : response['ResponseMetadata']['HTTPStatusCode'] 
                }
        
        except ClientError as e:
            return {
                "success":False,
                "message": e.response['Error']['Message'],
                "document": rel_document,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }
        


    def delete_rel(self, **rel_document):

        keys = {
            'index': rel_document['index'],
            'rel': rel_document['rel']
        }

        try:
            response = self.rel_table.delete_item(Key=keys)
            current_app.logger.debug('MODEL: Deleted Relationship:' + str(rel_document))
            return {
                "success":True,
                "message": "Rel deleted", 
                "document": rel_document,
                "status" : response['ResponseMetadata']['HTTPStatusCode'] 
                }
        
        except ClientError as e:
            return {
                "success":False,
                "message": e.response['Error']['Message'],
                "document": rel_document,
                "status" : e.response['ResponseMetadata']['HTTPStatusCode']
                }







    