#ENVIRONMENT README


##1. Create a Virtual Environment if it doesn't exist

`cd tank`
`python3.12 -m venv venv`
`source venv/bin/activate`

Activate it
`source venv/bin/active

##2. Install boto3
`pip install boto3`


##3. List available AWS profiles. There should be at least one
`aws configure list-profiles`

You should see the profile that points to the cloud you want to deploy this to. 


##4. Run the deploy environment for TT
This will create the Dynamo tables, create the Cognito user pool, create the IAM policy, create the Role and link everything together. 
Replace <environment_name> with the actual name of the environment you want to create. Replace <aws_profile> 

`cd installer`
`python deploy_environment.py <environment_name> --aws-region <aws_region>  --aws-profile <aws_profile>`


##5. NEXT STEPS
The next step is to run the Zappa installer. Go back to the document ../CLOUD_README.md

Bring with you the following information
a. <aws_region>
b. <bucket_name>


























#STOP HERE. DO NOT CONTINUE IF YOU ALREADY RAN deploy_environment.py successfully. 

#MANUAL PROCESS (Only needed for troubleshooting)


##T1. Create the DynamoDB tables
Replace <environment_name> with the actual name of the environment you want to create
Replace <aws_profile> with the target profile installed in your environment

`python create_dynamodb_tables.py <environment_name> --aws-profile <aws_profile>`

EXAMPLE:

IN >
python create_dynamodb_tables.py lquant --aws-profile default

OUT >
🔄 Using AWS Profile: default
✅ Table 'lquant_blueprints' already exists. Skipping creation.
✅ Table 'lquant_entities' already exists. Skipping creation.
✅ Table 'lquant_rel' already exists. Skipping creation.
🛠️  Creating table: lquant_data...
⏳ Waiting for table 'lquant_data' to become active...


##T2. Create Cognito user pools

`python create_cognito_user_pool.py <environment_name> --aws-region <aws_region> --aws-profile <aws_profile>`

EXAMPLE:

IN >
python create_cognito_user_pool.py lquant --aws-region us-east-1 --aws-profile default

OUT > 
UserPoolID   : us-east-1_QaC82Pxnp
UserPoolARN  : arn:aws:cognito-idp:us-east-1:339713094352:userpool/us-east-1_QaC82Pxnp
AppClientID  : 7n6pai9p45u3jci117rgpfpm00



##T3. Create the restricted IAM Policy for the application

`python create_iam_policy.py <environment_name> <cognito_user_pool_id>  --aws-region <aws_region> --aws-profile <aws_profile>`

EXAMPLE:

IN>
python create_iam_policy.py lquant us-east-1_QaC82Pxnp --aws-region us-east-1 --aws-profile default

OUT>
✅ IAM Policy Created Successfully!
🔹 Policy Name: lquant_tt_policy
🔹 Policy ARN: arn:aws:iam::339713094352:policy/lquant_tt_policy

🎯 IAM Policy Created Successfully!

Policy Name: lquant_tt_policy
Policy ARN : arn:aws:iam::339713094352:policy/lquant_tt_policy


##T4. Create the role for the application

`python create_iam_role.py <environment_name> --aws-region <aws_region> --aws-profile <aws_profile>`

EXAMPLE:

IN > 
python create_iam_role.py lquant --aws-region us-east-1 --aws-profile default

OUT > 
🛠️ Creating IAM Role: lquant_tt_role...
✅ IAM Role Created Successfully! ARN: arn:aws:iam::339713094352:role/lquant_tt_role
🔗 Attaching Policy: arn:aws:iam::339713094352:policy/lquant_tt_policy to Role: lquant_tt_role...
✅ Policy attached successfully!

🎯 IAM Role Created Successfully!

Role Name: lquant_tt_role
Role ARN : arn:aws:iam::339713094352:role/lquant_tt_role




##T5. Install the Default Blueprints

`python upload_blueprints.py <environment_name> --aws-profile <aws_profile>`

EXAMPLE: 

IN > 
python upload_blueprints.py lquant --aws-profile default

🔄 Using AWS Profile: default
📂 Loading blueprint files...
📋 Found 3 blueprint files
⬆️  Uploading blueprints to table: lquant_blueprints
✅ Uploaded blueprint: irn:blueprint:sys:entities@0.0.1
✅ Uploaded blueprint: irn:blueprint:irma:schd_jobs@0.0.1
✅ Uploaded blueprint: irn:blueprint:irma:schd_runs@0.0.1

📊 Upload Summary:
✅ Successfully uploaded 3 blueprints:
   • irn:blueprint:sys:entities@0.0.1
   • irn:blueprint:irma:schd_jobs@0.0.1
   • irn:blueprint:irma:schd_runs@0.0.1