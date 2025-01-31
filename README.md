# TANK

## INSTALLATION

To use this template: 

### Step 1: Create a new repository from this template 
Go to `https://github.com/renglo/tank` and clicking "Use this template"

The name of the repository should be <projectname>_tank

### Step 2: Clone a local copy to your development environment

`git clone https://github.com/renglo/<projectname>_tank.git`

### Step 3: Declare the upstream repository in the new local clone to be able to receive updates from the template

`git remote add upstream https://github.com/renglo/tank.git`

You can check like this:

`git remote -v`


origin  https://github.com/renglo/<projectname>_tank.git (fetch)
origin  https://github.com/renglo/<projetname>_tank.git (push)
upstream        https://github.com/renglo/tank.git (fetch)
upstream        https://github.com/renglo/tank.git (push)


### Step 4: To acquire changes from the template run

`git fetch upstream`

And then reapply your changes on top of the latest template updates, avoiding a merge commit.

`git rebase upstream/main`


If there are conflicts you'll have to resolve them. 
To avoid conflicts avoid overwriting template files.


### Step 5: 

