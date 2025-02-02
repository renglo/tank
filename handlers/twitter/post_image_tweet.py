import tweepy
import json
from env_config import TANK_DOC_BASE_URL
import requests  # Added for the new post_image method
import io  # Added to create a file-like object
import os


class PostImageTweet:
    
    def __init__(self):
             
        self.bridge = {} 
         
        
    def post_image(self,payload):
        
        action='post_image' 
        imageurl = payload['image']['imageurl']
        filename = imageurl.split('/')[-1]
             
        try:
            
            
            # Determine if Flask is running on AWS Lambda or locally
            if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
                img_base_url = TANK_DOC_BASE_URL
            else:
                img_base_url = '127.0.0.1:5000'
            
            # Download the image from the URL
            response_1 = requests.get(f'{img_base_url}/{imageurl}')
            image_data = response_1.content  # Store the image binary data
            
            # Upload the image using the API object
            auth = tweepy.OAuth1UserHandler(
                payload['X_API_KEY'],
                payload['X_API_KEY_SECRET'],
                payload['X_ACCESS_TOKEN'],
                payload['X_ACCESS_TOKEN_SECRET'])
            api = tweepy.API(auth)
            
            # Use the binary data for media upload
            image_file = io.BytesIO(image_data)  # Create a file-like object from the bytes
            media = api.media_upload(filename=filename, file=image_file)
            output = {}
            output['media_id'] = media.media_id
            output['size'] = media.size
            output['image'] = media.image
            
            
            self.bridge['media'] = output
            
            '''
            Media(
                        _api=<tweepy.api.APIobjectat0x10c2b47a0>,
                        media_id=1882242054727553024,
                        media_id_string='1882242054727553024',
                        size=68682,
                        expires_after_secs=86400,
                        image={
                            'image_type': 'image/jpeg',
                            'w': 1080,
                            'h': 1080
                        }
            '''
            print('Media updated:')
            print(self.bridge['media'])
            return {'success':True,'action':action,'message':'Image posted successfully','output':output}
            
            
        except Exception as e:
            
            print(f'Exception during Tweet posting attempt: {e}')
            return {'success':False,'action':action,'message':'Image posting failed','output':str(e)}
    
    
    def post_content_and_image(self,payload):
        
        action='post_content_and_image' 
        
        client = tweepy.Client(bearer_token=payload['X_BEARER_TOKEN'], 
                       consumer_key=payload['X_API_KEY'], 
                       consumer_secret=payload['X_API_KEY_SECRET'], 
                       access_token=payload['X_ACCESS_TOKEN'], 
                       access_token_secret=payload['X_ACCESS_TOKEN_SECRET'])
        
        
        
        if 'caption' not in payload:  
            tweet = ''    
        tweet = payload['caption']  
        media = self.bridge['media']    
               
        try:          
            response = client.create_tweet(text=tweet, media_ids=[media['media_id']])
            # Parsing the response
            
            output = {}
            
            tweet_data = response.data  # Access the 'data' attribute
            output['tweet_id'] = tweet_data['id']  # Get the tweet ID
            output['tweet_text'] = tweet_data['text']  # Get the tweet text
            output['edit_history_ids'] = tweet_data['edit_history_tweet_ids']  # Get the edit history IDs
               
            
            print("Tweet and its image has been posted", response)
            return {'success':True,'action':action,'message':'Tweet and its image has been posted','input':payload,'output':output,'status':200}
            
        except Exception as e:
            
            print(f'Exception during Tweet+Image posting attempt: {e}')
            #return {'success':False,'action':action,'message':str(e)}
            return {'success':False,'action':action,'message':'Tweet and its image post failed','input':payload,'output':str(e),'status':400}
            
        
        
    def run(self,payload=None):
        
        if payload:
            print(json.dumps(payload)) 
        else:
            print("No payload provided.")   
        results = []
        
        
        #Step 1: Post the image
        response_1 = self.post_image(payload)
        results.append(response_1)
        if not response_1['success']: return {'success':False,'output':results}
          
        #Step 2: Post the tweet
        response_2 = self.post_content_and_image(payload)
        results.append(response_2)
        if not response_2['success']: return {'success':False,'output':results}
            
        return {'success':True,'output':results}
    

# Test block
if __name__ == '__main__':
    # Creating an instance
    PIT = PostImageTweet()
    
    assert PIT.run() == True, 'Posting to X Failed'
    
