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

Create the Virtual Environment in the root folder of the project

`python3.12 -m venv venv`

Activate the Virtual Environment

`source venv/bin/activate`

Install all packages indicated in requirements.txt

`pip install -r requirements.txt`


#### Step 7: Correcting issues in the Template files

- While it is easier to just fix the problem in your local clone, you should fix the Template in the original template repository. 
- That way, everybody will benefit from your fixes. 
- However, it ok to fix something locally to test it works and then change the template (double work). Git will merge both changes as one.
- Your local copy will never send changes to the Template. 









