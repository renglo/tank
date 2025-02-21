# CLOUD SETUP

The goal of this document is to show how to setup the cloud to host TankTower applications


Step 1: Super Dev Permissions

Create a user in IAM that uses an AWS managed policy called "AdministratorAccess"
- This is a very powerful user that allows among other things to:
    + Deploy new Zappa environments to the cloud
    + Connect to AWS resources during development (You can run a full cloud application from your laptop)


CREATING INSTALLER USER IN THIRD PARTY AWS ACCOUNT

Ask the third party Admin to 
1. Create a user 
2. Create a user group
3. Assign the AWS managed role "AdministratorAccess" to the user group
4. Assign the user to that user group
    In order to do this, they'll have to create a group. The group will have assigned the role, the user will be assinged to that group.

2. Create the Acess Key ID and Secret Access Key that will allow the app to gain access




Step 2: Add TankSpecific permissions 


"environment_name" represents a stand-alone set of cloud services that can host multiple Zappa Environments, each one of them logically separated. 
TankTower was designed to be distributed, the ideas is that each cluster should host just a handful of Zappa environments to use a minimal amount of resources to stay within the free range of cloud services. 

While you can overload a cluster and turn it into a centralized hub, it is better to distribute the computing and cost across the companies that are using it (similar to the principle of WordPress being a common repository but being installed everywhere instead of it being a centralized SaaS).


Create this custom inline policy and add it to the user you created in step 1


{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_blueprints",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_data",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_entities",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_rel",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_data/index/path_index"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "ses:SendEmail",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "execute-api:Invoke",
            "Resource": "arn:aws:execute-api:us-east-1:<aws_account_number>:gs338uqho1/*/*/"
        }
    ]
}



Step 3: Create the tables that are listed in the Resource array in the policy from step 2. 
Before creating the tables, verify you are in the right region

Table 1
    Name: <environment_name>_blueprints
    Partition key: irn(String)
    Sort key: version(String)


Table 2

    Name: <environment_name>_data
    Partition key: portfolio_index(String)
    Sort key: doc_index(String)
    

    Local Secondary Indexes
        
        Name: geo_index 
        Partition key: portfolio_index(String)
        Sort key: geo_index(String)
        Projected attributes: Keys only

        Name: path_index 
        Partition key: portfolio_index(String)
        Sort key: path_index(String)
        Projected attributes: All

        Name: time_index 
        Partition key: portfolio_index(String)
        Sort key: time_index(String)
        Projected attributes: Include > path_index

Table 3

    Name: <environment_name>_entities
    Partition key:  index(String)
    Sort key: _id(String)


Table 4

    Name: <environment_name>_rel
    Partition key:  index(String)
    Sort key: rel(String)




Step 4a: Create the Cognito User Pool

- Go to Amazon Cognito > User pools > Create user pool
- Select Traditional web application
- Name your application : <environment_name>
- Configure options > Sign Identifiers : Only select "email"
- Required attributes for sign-up: None
- Return URL: None

Once created, take note of the following information from the New User Pool

User pool ID >> <aws_region>_XXXXXXXXX
ARN >> arn:aws:cognito-idp:<aws_region>:<aws_account_number>:userpool/<user_pool_id>

Take note of the client id. 
ClientID >> xxxxxxxxxxxxxxxx

- The next step is to create an App Client in the User Pool
- Select SINGLE PAGE APPLICATION
- And check that you are using the flow : USER_PASSWORD_AUTH
- Save and take note of the Client Secret.

Client secret >> pppppppppppppppppppp






Step 4b: Assign a name to the bucket that will be generated when the app is deployed. 

-Call it <environment_name><random_string_of_8_characters>



Step 4b: Create the AWS Policy  


Step 4: Create the Zappa/TankTower Policy that the Application will use when loaded to the Lambda

- The policy name should be:  <environment_name>_tt_policy
- It is a combination between the standard zappa-permissions policy that is automatically generated by zappa on deployment and 
the inline policy created in step 2. 
- It uses minimum required permissions


{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "apigateway:POST",
                "apigateway:GET",
                "apigateway:PUT",
                "apigateway:DELETE"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::<s3_bucket_name>/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_blueprints",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_data",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_entities",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_rel",
                "arn:aws:dynamodb:<aws_region>:<aws_account_number>:table/<environment_name>_data/index/path_index"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "ses:SendEmail",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cognito-idp:ListUsers",
                "cognito-idp:AdminCreateUser",
                "cognito-idp:AdminSetUserPassword",
                "cognito-idp:AdminInitiateAuth",
                "cognito-idp:RespondToAuthChallenge"
            ],
            "Resource": "arn:aws:cognito-idp:us-east-1:<aws_account_id>:userpool/<aws_region>_<user_pool_id>"
        }
    ]
}


Step 5: Create a role that uses your newly created policy

- Go to IAM > Roles > Create Role
- Select "AWS Service"
- Select Service: Lambda
- Find the policy you just created in the search:  <environment_name>_tt_policy
- Name your new role <environment_name>_tt_role
- Click on "Create Role"

It will show a success message
- Look for the new Role , and copy the ARN
arn:aws:iam::<aws_account_number>:role/tanktower_role_<environment_name>



Step 5b: Adjust the Trust Policy to include events
- Go to the IAM console, find the role and look for the Trust relationships tab
- Edit the policy to look like this:

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    "apigateway.amazonaws.com",
                    "events.amazonaws.com",
                    "lambda.amazonaws.com"
                ]
            },
            "Action": "sts:AssumeRole"
        }
    ]
}


Step5c: Create a revoke sessions policy the same way as last step 

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Deny",
            "Action": [
                "*"
            ],
            "Resource": [
                "*"
            ],
            "Condition": {
                "DateLessThan": {
                    "aws:TokenIssueTime": "[policy creation time]"
                }
            }
        }
    ]
}


Step 6: Assign role to your Flask Application

-  Put the role IAM in zappa_settings.json




Step 7: Application Email

- In order for the App to send emails to users (e.g.invitation emails) you need to create an identity in SES
- An identity is the email that will show as the "from" in the email metadata. Usually it looks like no-reply@<your_domain>.com

- Please notice that if you don't want to send emails out, you can just have your users to generate an account
in the environment directly. Those emails are validated directly by AWS Cognito so you don't need to put them in the
SES identity list. 


Step 8: Default Blueprints

- There is a list of Blueprints that TankTower require to operate. 
- A very important blueprint is sys/entities that help define portfolios, orgs, teams and users

irn:blueprint:sys:entities
irn:blueprint:irma:schd_runs
irn:blueprint:irma:schd_jobs


ENTITIES

{
 "irn": "irn:blueprint:sys:entities",
 "version": "0.0.1",
 "added": "2024-09-04T13:22:46.229773",
 "blueprint_origin": "https://tank7075.helloirma.com/_blueprint/sys/entities/0.0.1",
 "description": "A user/organization is an entity that owns its own data and processes",
 "fields": [
  {
   "cardinality": "single",
   "default": "",
   "hint": "The name of the entity",
   "label": "Name",
   "layer": "0",
   "multilingual": false,
   "name": "name",
   "order": "1",
   "required": true,
   "semantic": "https://schema.org/name",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "About the entity",
   "label": "About",
   "layer": "0",
   "multilingual": false,
   "name": "about",
   "order": "2",
   "required": false,
   "semantic": "https://schema.org/about",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Handle for this entity. This is a mutable alias for the immutable entity id",
   "label": "Handle",
   "layer": "1",
   "multilingual": false,
   "name": "handle",
   "order": "3",
   "required": false,
   "semantic": "https://schema.org/alternateName",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Physical Location of this entity",
   "label": "Location",
   "layer": "1",
   "multilingual": false,
   "name": "location",
   "order": "4",
   "required": false,
   "semantic": "https://schema.org/Place",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Email of entity owner",
   "label": "Email",
   "layer": "2",
   "multilingual": false,
   "name": "email",
   "order": "8",
   "required": true,
   "semantic": "https://schema.org/email",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Slot A",
   "label": "Slot A",
   "layer": "2",
   "multilingual": false,
   "name": "slot_a",
   "order": "9",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Slot B",
   "label": "Slot B",
   "layer": "2",
   "multilingual": false,
   "name": "slot_b",
   "order": "10",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Slot C",
   "label": "Slot C",
   "layer": "2",
   "multilingual": false,
   "name": "slot_c",
   "order": "11",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Slot D",
   "label": "Slot D",
   "layer": "2",
   "multilingual": false,
   "name": "slot_d",
   "order": "12",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Slot E",
   "label": "Slot E",
   "layer": "2",
   "multilingual": false,
   "name": "slot_e",
   "order": "13",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Id of entity owner",
   "label": "Owner ID",
   "layer": "2",
   "multilingual": false,
   "name": "owner_id",
   "order": "14",
   "required": true,
   "semantic": "https://schema.org/owns",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "The date the entity was created",
   "label": "Added",
   "layer": "2",
   "multilingual": false,
   "name": "added",
   "order": "15",
   "required": false,
   "semantic": "https://schema.org/dateCreated",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": true,
   "hint": "Flag that shows whether the entity has been deactivated or not.",
   "label": "Is Active",
   "layer": "2",
   "multilingual": false,
   "name": "is_active",
   "order": "16",
   "required": false,
   "semantic": "https://schema.org/DeactivateAction",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": false,
   "hint": "<user|portfolio|org|team|app> ",
   "label": "Entity Type",
   "layer": "2",
   "multilingual": false,
   "name": "type",
   "order": "17",
   "required": false,
   "semantic": "https://schema.org/Organization",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Last IP address this entity has been accessed from (users only)",
   "label": "Last IP",
   "layer": "2",
   "multilingual": false,
   "name": "last_ip",
   "order": "18",
   "required": false,
   "semantic": "https://schema.org/address",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Last Login to this account (users only)",
   "label": "Last Login",
   "layer": "2",
   "multilingual": false,
   "name": "last_login",
   "order": "19",
   "required": false,
   "semantic": "https://schema.org/RegisterAction",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "The date on which this document was last modified",
   "label": "Modified",
   "layer": "2",
   "multilingual": false,
   "name": "modified",
   "order": "20",
   "required": false,
   "semantic": "https://schema.org/dateModified",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Raw ID",
   "label": "Raw ID",
   "layer": "2",
   "multilingual": false,
   "name": "raw_id",
   "order": "21",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Irma Resource Number",
   "label": "IRN",
   "layer": "2",
   "multilingual": false,
   "name": "irn",
   "order": "22",
   "required": false,
   "semantic": "https://schema.org/id",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Preferred language",
   "label": "Language",
   "layer": "2",
   "multilingual": false,
   "name": "language",
   "order": "21",
   "required": false,
   "semantic": "https://schema.org/language",
   "source": "",
   "type": "string",
   "widget": "text"
  }
 ],
 "handle": "irma",
 "label": "Entities",
 "license": "CC BY",
 "name": "entities",
 "public": true,
 "status": "final",
 "uri": "https://tank7075.helloirma.com/_blueprint/sys/entities/0.0.1",
 "_id": "63994ed5-d532-8752-a20f-8f58512846a2"
}






SCHD_JOBS


{
 "irn": "irn:blueprint:irma:schd_jobs",
 "version": "0.0.1",
 "added": "2025-01-17T09:22:46.229773",
 "blueprint_origin": "",
 "description": "Job Types",
 "fields": [
  {
   "cardinality": "single",
   "default": "",
   "hint": "Job type name",
   "label": "Name",
   "layer": "0",
   "multilingual": false,
   "name": "name",
   "order": "1",
   "required": true,
   "semantic": "hs:name",
   "source": "schd_jobs:_id:name",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Whether this job type is available or not",
   "label": "Status",
   "layer": "0",
   "multilingual": false,
   "name": "status",
   "options": {
    "available": "Available",
    "not_available": "Not Available"
   },
   "order": "2",
   "required": true,
   "semantic": "hs:status",
   "source": "",
   "type": "string",
   "widget": "select"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Semantic Version of the job type",
   "label": "Version",
   "layer": "0",
   "multilingual": false,
   "name": "version",
   "order": "3",
   "required": false,
   "semantic": "hs:version",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Route to the handler",
   "label": "Handler",
   "layer": "0",
   "multilingual": false,
   "name": "handler",
   "order": "4",
   "required": true,
   "semantic": "hs:handler",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Describe what this job does",
   "label": "Description",
   "layer": "0",
   "multilingual": false,
   "name": "description",
   "order": "5",
   "required": false,
   "semantic": "hs:description",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Type of job (e.g, Control, Acquisition, Publishing, Training, Inference, Research, etc)",
   "label": "Type",
   "layer": "0",
   "multilingual": false,
   "name": "type",
   "options": {
    "control": "Control",
    "data_acquisition": "Data Acquisition",
    "generation": "Generation",
    "inference": "Inference",
    "publishing": "Publishing",
    "research": "Research",
    "supervision": "Supervision",
    "training": "Training",
    "transaction": "Transaction",
    "validation": "Validation",
    "verification": "Verification"
   },
   "order": "6",
   "required": true,
   "semantic": "hs:type",
   "source": "",
   "type": "string",
   "widget": "text"
  }
 ],
 "handle": "irma",
 "label": "Job Types",
 "license": "CC BY",
 "name": "schd_jobs",
 "public": true,
 "singleton": false,
 "status": "final",
 "uri": "https://tank7075.helloirma.com/_blueprint/irma/schd_jobs/1.0.1",
 "_id": "5e834ed5-d532-4852-a20f-5928a76c2a19"
}



SCHD_RUNS


{
 "irn": "irn:blueprint:irma:schd_runs",
 "version": "0.0.1",
 "added": "2025-01-17T09:22:46.229773",
 "blueprint_origin": "",
 "description": "Job Runs",
 "fields": [
  {
   "cardinality": "single",
   "default": "",
   "hint": "A job is a group of actions executed to achieve a specific goal.",
   "label": "Job Type",
   "layer": "0",
   "multilingual": false,
   "name": "schd_jobs_id",
   "order": "1",
   "required": true,
   "semantic": "hs:job",
   "source": "schd_jobs:_id:name",
   "type": "string",
   "widget": "select"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "State of the run",
   "label": "Status",
   "layer": "0",
   "multilingual": false,
   "name": "status",
   "options": {
    "executed": "Executed",
    "failed": "Failed",
    "new": "New"
   },
   "order": "2",
   "required": true,
   "semantic": "hs:status",
   "source": "",
   "type": "string",
   "widget": "select"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "What triggered the job run?",
   "label": "Trigger",
   "layer": "0",
   "multilingual": false,
   "name": "trigger",
   "options": {
    "api": "call",
    "cron": "cron",
    "manual": "manual"
   },
   "order": "3",
   "required": true,
   "semantic": "hs:trigger",
   "source": "",
   "type": "string",
   "widget": "select"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Id of the entity that triggered the job run",
   "label": "Triggered by",
   "layer": "0",
   "multilingual": false,
   "name": "author",
   "order": "4",
   "required": true,
   "semantic": "hs:author",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Job run results",
   "label": "Output",
   "layer": "1",
   "multilingual": false,
   "name": "output",
   "order": "5",
   "required": false,
   "semantic": "hs:results",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Time the job run was put in the pipeline",
   "label": "Time Queued",
   "layer": "0",
   "multilingual": false,
   "name": "time_queued",
   "order": "6",
   "required": false,
   "semantic": "hs:time",
   "source": "",
   "type": "string",
   "widget": "text"
  },
  {
   "cardinality": "single",
   "default": "",
   "hint": "Time the job run finished executing",
   "label": "Time Executed",
   "layer": "0",
   "multilingual": false,
   "name": "time_executed",
   "order": "7",
   "required": false,
   "semantic": "hs:time",
   "source": "",
   "type": "string",
   "widget": "text"
  }
 ],
 "handle": "irma",
 "label": "Job Runs",
 "license": "CC BY",
 "name": "schd_runs",
 "public": true,
 "singleton": false,
 "status": "final",
 "uri": "https://tank7075.helloirma.com/_blueprint/irma/schd_runs/1.0.1",
 "_id": "5e834ed5-d532-4852-a20f-4857a6b1984ad"
}





Step 9: Setup your development and deployment environment. 

- As an early MVP, TankTower used Zappa to deploy the application. 
- You need to setup the aws credentials in the ~/.aws/credentials file 
- For that enter the credentials that you got from the console. 

