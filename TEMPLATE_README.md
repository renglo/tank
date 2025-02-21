# TANK

## INSTALLATION

To use this template: 

#### Step 1: Create a new repository from this template 
Go to `https://github.com/renglo/tank` and clicking "Use this template"

The name of the repository should be <projectname>_tank

#### Step 2: Clone a local copy to your development environment

`git clone https://github.com/renglo/<projectname>_tank.git`

#### Step 3: Declare the upstream repository in the new local clone to be able to receive updates from the template

`git remote add upstream https://github.com/renglo/tank.git`

You can check like this:

`git remote -v`


origin  https://github.com/renglo/<projectname>_tank.git (fetch)
origin  https://github.com/renglo/<projetname>_tank.git (push)
upstream        https://github.com/renglo/tank.git (fetch)
upstream        https://github.com/renglo/tank.git (push)


#### Step 4: To acquire changes from the template run

`git fetch upstream`

And then reapply your changes on top of the latest template updates, avoiding a merge commit.

`git rebase upstream/main`


If there are conflicts you'll have to resolve them. 
To avoid conflicts avoid overwriting template files.


#### STEP 4b: Commit template changes to your project repository

`git add . `
`git commit -m 'some message'`
`git push -u -origin`

If there is a conflict indicating that the origin branch has been rebased, use the following command and try again

`git config pull.rebase true`


Your code will be untouched as template files will be overriden by your changes.



#### Step 5: Setup the configuration file around the current environment.

Rename env_config.py.TEMPLATE to env_config.py


### Step 6: Create the Virtual Environment and install all the dependencies

First, check if you have python3.12 installed

`python3.12`

You should see something like this

```
Python 3.12.8 (main, Dec  3 2024, 18:42:41) [Clang 16.0.0 (clang-1600.0.26.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> 
```

If python3.12 is not installed, install it using Homebrew
`brew install python@3.12`

Create the Virtual Environment in the root folder of the project

`python3.12 -m venv venv`

Activate the Virtual Environment

`source venv/bin/activate`

Install all packages indicated in requirements.txt

`pip install -r requirements.txt`

Try running Flask. 
`flask run`

If there are any errors, fix them. If the error are in the Template files read the following:
- While it is easier to just fix the problem in your local clone, you should fix the Template in the original template repository. 
- That way, everybody will benefit from your fixes. 
- However, it ok to fix something locally to test it works and then change the template (double work). Git will merge both changes as one.
- Your local copy will never send changes to the Template. 


#### Step 7: Connect to the FrontEnd local copy

- Tank and Tower work together. Tank is the back-end while Tower is the front-end. 
- Both Tank and Tower are bundled together before deployment
- However in development environments, they live in separate folders. 
- A symbolic link connects them together. The symbolic link is called `_tank-frontend`

run this command to see where the symbolic link is pointing to: 
`ls -l `

You should see something like this: 
`_tank-frontend -> ../tank-frontend/dist`


You need to modify the symbolic link to point to the right folder that contains the Tower clone of your application. 

First, remove the existing symbolic link. This removes the link but not the target folder.
`rm _tank-frontend`

Then, create the new symbolic link
`ln -s ../<projectname>_tower/dist _tank-frontend`

This assumes that both Tank and Tower root folders are at the same level inside of the same folder

parent_folder
    |
    |__ /<projectname>_tank
    |__ /<projectname>_tower


While the symbolic link will be created, it will not work until you clone Tower in that location for this project.

-Refer to the TEMPLATE_README.md file in the Tower repository for instructions on how to clone and setup that project. 




# MILESTONE

Tank is a fully functional API now.

Once the FE reaches MILESTONE 1, it will be able to send traffic to the TANK API. You should be able to see DB data in the UI


STOP >>>>> INSTALL TOWER FIRST BEFORE MOVING TO THE NEXT STEP





STEP 8: Deploy to AWS using Zappa

Note: Apparently Zappa only works with Python 3.8 and 3.10

Install Zappa

`pip install zappa`

Run their init wizard that will walk you through the creation of the environment

`zappa init`

Follow the steps and you'll get a URL that looks like this: 

`https://xyz.execute-api.us-east-1.amazonaws.com/abc_environment`

You should be able to test whether the app is there by going to 

`https://xyz.execute-api.us-east-1.amazonaws.com/abc_environment/timex` 
 It should return the local time. 

 - You won't be able to access the Application yet, because this url is already using the first position in the path. Tank and Tower depend on the URL for their routing

STEP 9: Setup a customized domain

- Go to the AWS console > API Gateway and create a new Custom Domain Name
- Select a new subdomain under an existing ACM Certificate. 
- If you must use a new domain, you need to create the ACM certificate first (out of the scope of this document)
- Create a  Custom Domain and go to the API mappings. You'll be able to select the API that you just deployed and the stage, save that. 
- This alone won't automatically redirect all traffic to your application. You still need to create a CN Record in your domain.

VERY IMPORTANT: The value of the CNRECORD is not the gateaway URL but the CUSTOM DOMAIN URL. They look similar but they are not the same

- To get the right value, go to API Gateway > Custom Domain Names 
- Select the Custom Domain Name and look for "API Gateway domain name" copy and paste it as is
- Save that record and almost immediately you'll be able to see your app in that subdomain. 





MILESTONE 2: The Vanilla version of TowerTank is in the cloud 



STEP 10: Install Tools.

- Tank comes with two default tool handlers: Data and Schd. Hoever you might want to install additional apps designed for specific use cases. 
- Some tools use the Data handlers and don't need custom handlers.
- Some tools require specialized handlers. A handler is a function in the back-end that can be called to do something in specific. 
- Handlers are stand alone Python classes that have a run() method that gets called by a job run. The class is listed in the job document

To install a custom handler, create a new folder inside the "handler" folder and put the handler classes in there.



parent_folder
    |
    |__ /<projectname>_tank/handler/<custom_handler_name> |
                                                          |__ /<custom_handler_class>.py



- NOTE: The new handler might have its own set of dependencies. Check README.MD in the custom_handler_name









