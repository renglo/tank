import tweepy
import json


class PostTextTweet:
    
    def __init__(self):
             
        self.bridge = {}
        
              
    def post_content(self,payload):
        
        action='post_content' 
        
        client = tweepy.Client(bearer_token=payload['X_BEARER_TOKEN'], 
                       consumer_key=payload['X_API_KEY'], 
                       consumer_secret=payload['X_API_KEY_SECRET'], 
                       access_token=payload['X_ACCESS_TOKEN'], 
                       access_token_secret=payload['X_ACCESS_TOKEN_SECRET'])
        
        if 'caption' not in payload:  
            tweet = ''    
        tweet = payload['caption']      
               
        try:          
            response = client.create_tweet(text=tweet)
            
            output = {}
            
            tweet_data = response.data  # Access the 'data' attribute
            output['tweet_id'] = tweet_data['id']  # Get the tweet ID
            output['tweet_text'] = tweet_data['text']  # Get the tweet text
            output['edit_history_ids'] = tweet_data['edit_history_tweet_ids']  # Get the edit history IDs
            
            
            print("Tweet posted successfully!", response)
            return {'success':True,'action':action,'message':'Tweet posted successfully!','input':payload,'output':output,'status':200}
            
        except Exception as e:
            
            print(f'Exception during Tweet posting attempt: {e}')
            return {'success':False,'action':action,'message':'Tweet posting failed','input':payload,'output':str(e),'status':400}
            
        
        
    def run(self,payload=None):
        
        if payload:
            print(json.dumps(payload)) 
        else:
            print("No payload provided.")   
        results = []
          
        #Step 1: Get Request Token
        response_1 = self.post_content(payload)
        results.append(response_1)
        if not response_1['success']: return {'success':False,'output':results}
            
        return {'success':True,'output':results}
    

# Test block
if __name__ == '__main__':
    # Creating an instance
    PIT = PostTextTweet()
    
    assert PIT.run() == True, 'Posting to X Failed'
    
