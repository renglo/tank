import tweepy
import json
from env_config import TANK_DOC_BASE_URL
import requests  # Added for the new post_image method
import io  # Added to create a file-like object
import os


class GetTwitterUser:
    
    def __init__(self):
             
        self.bridge = {} 
        self.search_url = "https://api.x.com/2/users" 
        self.bearer_token = '' #Initializes empty but it will be retrieved from the payload
        
        
    def bearer_oauth(self,r):
        """
        Method required by bearer token authentication.
        """

        r.headers["Authorization"] = f"Bearer {self.bearer_token}"
        r.headers["User-Agent"] = "v2RecentSearchPython"
        return r
             
    
    def get_user(self,payload):
        
        action='get_user' 
        self.bearer_token = payload['X_BEARER_TOKEN']
        
        query_params = {'ids':payload['x_id'],'user.fields': 'id,name,username,created_at,description,location,profile_image_url,public_metrics,url'}
        
        response = requests.get(self.search_url, auth=self.bearer_oauth, params=query_params)
        print(response.status_code)
        if response.status_code != 200:
            raise Exception(response.status_code, response.text)
        
        '''
        {
          'data': [
            {
                'username': 'blacklabelrobot',
                'url': 'https://t.co/1t9g8WAUeb',
                'public_metrics': {
                    'followers_count': 55,
                    'following_count': 41,
                    'tweet_count': 142,
                    'listed_count': 1,
                    'like_count': 15,
                    'media_count': 58
                },
                'id': '988162058',
                'description': 'Ideas for an apocalyptic world',
                'created_at': '2012-12-04T06:26:11.000Z',
                'location': 'New York City',
                'name': 'Ricardo Cid',
                'profile_image_url': 'https://pbs.twimg.com/profile_images/446281668446658560/Hc2ESZ_1_normal.jpeg'
            }
          ]
        }
        '''
        return {'success':True,'action':action,'message':'User retrieved from Twitter','input':payload,'output':response.json()}
    
              
    
            
    
        
    def run(self,payload=None):
        
        action = 'get_twitter_user'
        
        if payload:
            print(json.dumps(payload)) 
        else:
            print("No payload provided.")   
        results = []
        
        
        #Step 1: Post the image
        response_1 = self.get_user(payload)
        results.append(response_1)
        if not response_1['success']: return {'success':False,'action':action,'output':results}
             
        return {'success':True,'action':action,'output':results}
    

# Test block
if __name__ == '__main__':
    # Creating an instance
    pass
    
