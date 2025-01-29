#check_tweet_replies.py
import requests
import os
import json

from env_config import X_BEARER_TOKEN


class GetTweetReplies:
    
    def __init__(self):
             
        self.bridge = {}
        self.search_url = "https://api.twitter.com/2/tweets/search/recent" 
        self.bearer_token = '' #Initializes empty but it will be retrieved from the payload
        
    
    def bearer_oauth(self,r):
        """
        Method required by bearer token authentication.
        """

        r.headers["Authorization"] = f"Bearer {self.bearer_token}"
        r.headers["User-Agent"] = "v2RecentSearchPython"
        return r

    
    def connect_to_endpoint(self,payload):
        
        action = 'connect_to_endpoint'
        self.bearer_token = payload['X_BEARER_TOKEN']
        
        #query_params = {'query': f'to:{payload['X_HANDLE']} is:reply', 'tweet.fields': 'in_reply_to_user_id,author_id,conversation_id', 'max_results': 100}
        query_params = {'query': f'conversation_id:{payload["X_CONVERSATION_ID"]}', 'tweet.fields': 'in_reply_to_user_id,author_id,conversation_id', 'max_results': 100}
        #query_params = {'query': f'conversation_id:{payload["X_CONVERSATION_ID"]} is:reply', 'tweet.fields': 'in_reply_to_user_id,author_id,conversation_id', 'max_results': 100}
         
        
        response = requests.get(self.search_url, auth=self.bearer_oauth, params=query_params)
        print(response.status_code)
        if response.status_code != 200:
            raise Exception(response.status_code, response.text)
        return {'success':True,'action':action,'message':'replies retrieved from X API V2','input':payload,'output':response.json()}
    
    
    def run(self,payload):
        
        action = 'get_tweet_replies' 
        results = []
           

        # Step 1: Verify that the game is still going
        response_1 = self.connect_to_endpoint(payload)
        results.append(response_1)
        if not response_1['success']: return {'success':False,'action':action,'message':'Could not obtain replies','output':results}
              
        #All went well, report back
        return {'success':True,'action':action,'message':'Obtained replies from X API v2','output':results}
        


if __name__ == "__main__":
    
    #TEST STAND-ALONE RUN
    GTR = GetTweetReplies()
    
