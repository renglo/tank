# CLOUD SETUP

This is the second part of the installation process which involves creating all the cloud dependencies and deploying the app to a public endpoint. 


### Step 1: Create the Installer user

Create a user called 'tt-installer' in IAM that uses an AWS managed policy called "AdministratorAccess"
- This is a very powerful user that allows among other things to:
    + Deploy new Zappa environments to the cloud
    + Connect to AWS resources during development (You can run a full cloud application from your laptop)


### Step 1b: (ALTERNATIVE STEP) CREATING INSTALLER USER IN THIRD PARTY AWS ACCOUNT

Ask the third party Admin to 
1. Create a user (tt_dev) 
2. Create a user group (tt_dev_group)
3. Assign the AWS managed role "AdministratorAccess" to the user group
4. Assign the user to that user group
    In order to do this, they'll have to create a group. The group will have assigned the role, the user will be assinged to that group.
5. Create the Acess Key ID and Secret Access Key that will allow the app to gain access (select : Local Code)


### Step 2: Create AWS Profile

 You can have multiple sets. Each one of them is called a Profile. 

 Install awscli 
 
 ```
 brew install awscli
 ```

 Verify installation
 
 ```
 aws --version
 ```

 Run configuration script
 
 ```
 aws configure
 ```

 You'll get a prompt like the following. Enter the access key, secret key and output. Leave output as None.

```
AWS Access Key ID [None]: YOUR_ACCESS_KEY
AWS Secret Access Key [None]: YOUR_SECRET_KEY
Default region name [None]: us-east-1  # (or your preferred region)
Default output format [None]: json
```


The credentials for each profile are saved here: ~/.aws
You'll use the profile name to run a series of installation scripts. 




### Step 3: Create the Cloud dependencies

Follow the instructions in  `tank/installer/ENVIRONMENT_README.md` on how to install the Cloud Environment

Come back after your are done with that step.

### Step 3a: Update config files

Update your configuration files with the latest tokens and ids obtained in Step 3: 

In `tank/env_config.py` 

Update the name of the tables

    DYNAMODB_ENTITY_TABLE = '<name>_entities'
    DYNAMODB_BLUEPRINT_TABLE = '<name>_blueprints'
    DYNAMODB_RINGDATA_TABLE = '<name>_data'
    DYNAMODB_REL_TABLE = '<name>_rel'
    DYNAMODB_CHAT_TABLE = '<name>_chat'

Enter random long strings in the CSRF and SECRET KEYS

    CSRF_SESSION_KEY = '<xxxxx>'
    SECRET_KEY = '<xxxxx>'

Enter the region and cognito ids

    COGNITO_REGION = '<us-xxxx-x>'
    COGNITO_USERPOOL_ID = '<us-xxxx-1_xxxxxxx>'
    COGNITO_APP_CLIENT_ID = '<xxxxx>'

Enter the bucket name

    S3_BUCKET_NAME = '<name>-xxxxx'


In `tower/.env.development.*` and `tower/.env.production.*`

Enter the region and cognito ids (again)

    VITE_COGNITO_REGION='<us-xxxx-x>'
    VITE_COGNITO_USERPOOL_ID='<us-xxxx-1_xxxxxxx>'
    VITE_COGNITO_APP_CLIENT_ID='<xxxxx>'


### Step 4: Run the Zappa installer

Note: If the Zappa app already exists, put the role IAM in zappa_settings.json instead and skip to Step 5.


Install Zappa

```
cd tank
pip install zappa
pip install setuptools
```

Run their init wizard that will walk you through the creation of the environment

```
zappa init
```



```
███████╗ █████╗ ██████╗ ██████╗  █████╗
╚══███╔╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗
  ███╔╝ ███████║██████╔╝██████╔╝███████║
 ███╔╝  ██╔══██║██╔═══╝ ██╔═══╝ ██╔══██║
███████╗██║  ██║██║     ██║     ██║  ██║
╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚═╝  ╚═╝

Welcome to Zappa!

Zappa is a system for running server-less Python web applications on AWS Lambda and AWS API Gateway.
This `init` command will help you create and configure your new Zappa deployment.
Let's get started!

Your Zappa configuration can support multiple production stages, like 'dev', 'staging', and 'production'.
1. What do you want to call this environment (default 'dev'): <environment_name>_<dev|test|prod>

AWS Lambda and API Gateway are only available in certain regions. Let's check to make sure you have a profile set up in one that will work.
2.We found the following profiles: default, and garbanzo. Which would you like us to use? (default 'default'): <aws_profile_from_step_2>


Your Zappa deployments will need to be uploaded to a private S3 bucket.
If you don't have a bucket yet, we'll create one for you too.
3. What do you want to call your bucket? (default 'zappa-7p915w4pa'): <bucket_name_from_step_3>


It looks like this is a Flask application.
What's the modular path to your app's function?
This will likely be something like 'your_module.app'.
We discovered: app.app
4. Where is your app's function? (default 'app.app'): app.app


You can optionally deploy to all available regions in order to provide fast global service.
If you are using Zappa for the first time, you probably don't want to do this!
5. Would you like to deploy this application globally? (default 'n') [y/n/(p)rimary]: n



Okay, here's your zappa_settings.json:
{
    "<environment_name>_<dev|test|prod>": {
        "app_function": "app.app",
        "aws_region": "<aws_region>",
        "exclude": [
            "boto3",
            "dateutil",
            "botocore",
            "s3transfer",
            "concurrent"
        ],
        "profile_name": "<aws_profile_from_step_2>",
        "project_name": "tank",
        "runtime": "python3.12",
        "s3_bucket": "<bucket_name_from_step_3>"
    }
}
6. Does this look okay? (default 'y') [y/n]: y

Done!
```



### Step 5: Deploy the Zappa application


First, you need to update the file that has been generated by the zappa init command:  zappa_settings.json
Open it and add the additional configurations (including the role_name)

```
{
    "<environment_name>_<dev|test|prod>": {
        ...
        "slim_handler": true,
        "domain": "<domain_name>",
        "static_support": true,
        "manage_roles": false,
        "role_name": "<environment_name>_tt_role"
    }
}
```


One more step before deploying!
If the react application has never been built, you need to do that before deploying Zappa

```
cd tower
yarn build
```

Now run 

```
cd tank
zappa deploy <environment_name>_<dev|test|prod>
```


You get something like this:

```
Deploying API Gateway..
Waiting for lambda function [tank-lquant-prod] to be updated...
Deployment complete!: https://<id>.execute-api.<aws_region>.amazonaws.com/<environment_name>_<dev|test|prod>
```


You should be able to test whether the app is running by going to 

`https://<id>.execute-api.<aws_region>.amazonaws.com/<environment_name>_<dev|test|prod>/timex` 

 It should return the server time. 

 You won't be able to access the Application yet, because this url is already using the first position in the path. Tank and Tower depend on the URL for their routing


### Step 6: Setup a customized domain

Setup the API to accept custom domains
- Go to the AWS console > API Gateway and create a new Custom Domain Name

`Domain name = <environment_name>.yourdomain.com`

- Select a new subdomain under an existing ACM Certificate. 
- If you must use a new domain, you need to create the ACM certificate first (out of the scope of this document)
- Create a  Custom Domain and go to the API mappings. You'll be able to select the API that you just deployed and the stage, save that. 
- This alone won't automatically redirect all traffic to your application. You still need to create a CN Record in your domain.

Configure domain to point to API Gateway


- To get the right value, go to API Gateway > Custom Domain Names 
- Select the Custom Domain Name and look for "API Gateway domain name" and copy it as is.
- Go to Route53>Zones and Create a CNAME record:

`NAME=<environment_name>`  `VALUE=<domain_name_api_id>.execute-api.<aws_region>.amazonaws.com>`

VERY IMPORTANT: The value of the CNAME should not be the GATEWAY URL but the CUSTOM DOMAIN URL. They look similar but they are not the same

- Save that record and almost immediately you'll be able to see your app in that subdomain. 

TROUBLESHOOT: 
-If you find a blank screen, double check your tank and tower configuration files have the domain you just configured. 
- If you are using Chrome, it won't work immediately even if you close the window, refresh everything. Try in another browser. Eventually, Chrome will consult the new DNS records and show you the page. 





### Step 7: Setting up the WebSocket API

Manual Process

- Go to API Gateway in the AWS Console
- Create  a new API  APIs > Create API > WebSocket API > Build

Step 1 > API details
API name: <api_name>  //This is the api name, it can be called anything
Route selection expression: $request.body.action
IP address type: IPv4

Step 2 > Routes
Select Add Custom Route
Route key:  chat_message

Step 3 > Integrations

Integration type: HTTP
Method: POST
URL endpoint: <integration_target>

NOTE >> The “integration_target_base” is the URL of the stage in the REST api (which was automatically created by Zappa) on deployment. 
It is the same URL that appears when you deploy something with Zappa
- a. Select the RESTful API in the API Gateway
- b. Go to the Stages section
- c. Look for the Invoke URL


integration_target = integration_target_base + "/_chat/message"

Example: "https://abcdef1234.execute-api.us-east-1.amazonaws.com/something_prod_0305a/_chat/message"

Step 4 > Stages
Stage name: <environment>  (prod|dev)

Once the API is saved. Click on the Route called chat_message,  go to Integration Request tab and enter the following template

Name: message_template
```
#set($inputRoot = $input.path('$'))
{
  "action": "$inputRoot.action",
  "data": "$inputRoot.data",
  "auth": "$inputRoot.auth",
  "entity_type": "$inputRoot.entity_type",
  "entity_id": "$inputRoot.entity_id",
  "thread": "$inputRoot.thread",
  "portfolio": "$inputRoot.portfolio",
  "org": "$inputRoot.org",
  "core": "$context.core",
  "connectionId": "$context.connectionId"
}
```

Add the name of the template ("message_template") to the Template selection expression

IMPORTANT: Every time you make a change in the templates or routes, you need to click on "Deploy API" otherwise the changes won't reflect.


-----------------
Steps 1-4 could have been automatically done by running this command

Go to /tank/installer and run

```
python create_websocket_api.py <api_name> "<integration_target>" "<endpoint>" <environment> --aws-profile <profile>
```

Example_Usage:
python create_websocket_api.py x_prod_1234a_websocket "chat_message" "https://qwerty123.execute-api.us-east-1.amazonaws.com/x_prod_1234a/_chat/message" prod --aws-profile volatour


Go to the Stages section in the new WebSocket API (just created) and looks for:

WebSocket URL and @connections URL . Copy them somewhere
------------------


Step 5 > Tell the FrontEnd and BackEnd where to connect to the WebSocket

Go to the Stages section on the left menu, 
Select the environment you just created (dev|prod)

Look for the Connections URL. 
It looks like this: https://abc123.execute-api.us-east-1.amazonaws.com/dev/@connections

Open tank/env_config.py and paste the @connections URL in the constant called WEBSOCKET_CONNECTIONS without the "/@connections" part at the end. 


Look for the WebSocket URL
It looks like this: wss://abc123.execute-api.us-east-1.amazonaws.com/dev/

Open tower/.env.production and tower/.env.development and paste the WebSocket URL as is

In the "Integration request settings"
IMPORTANT: Check that HTTP proxy integration Info is set to: False
IMPORTANT: Check that the Content Handling is set to : Convert to Text



### Step 8: Setting up the Application Email (Optional)

- In order for the App to send emails to users (e.g.invitation emails) you need to create an identity in SES
- An identity is the email that will show as the "from" in the email metadata. Usually it looks like no-reply@<your_domain>.com

- Please notice that if you don't want to send emails out, you can just have your users to generate an account
in the environment directly. Those emails are validated directly by AWS Cognito so you don't need to put them in the
SES identity list. 


