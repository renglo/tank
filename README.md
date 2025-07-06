# Initiating the local environment

### A) CLONING THE REPOSITORIES

#### Step 1 
Create a container folder with the name of the project. You are going to clone a couple of repositories inside of this folder

```
mkdir <project_name>
cd <project_name>
```

#### Step 2 
Clone Tank and Tower 

```
git clone https://github.com/renglo/tank.git
git clone https://github.com/renglo/tower.git
```

#### Step 3 
Create a new folder called Tools. You are going to clone all the tools inside of that folder

```
mkdir tools
cd tools
```

#### Step 4
Clone the auxiliary DATA, SCHD and TWITTER tools. 

```
git clone https://github.com/renglo/schd.git
git clone https://github.com/renglo/data.git
git clone https://github.com/renglo/twitter.git
```


#### Step 5
Clone the application specific tools.

```
git clone https://github.com/renglo/<tool_name>.git
```



### B) INSTALLING DEPENDENCIES

#### Step 6
Installing Tank dependencies

Go to the tank folder
```
cd ../tank
```

First, check if you have python3.12 installed

```
python3.12
```

You should see something like this

```
Python 3.12.8 (main, Dec  3 2024, 18:42:41) [Clang 16.0.0 (clang-1600.0.26.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
```

If python3.12 is not installed, install it using Homebrew 

```
brew install python@3.12
```

Create the Virtual Environment in the root folder of the project

```
python3.12 -m venv venv
```

Activate the Virtual Environment

```
source venv/bin/activate
```

Install all packages indicated in requirements.txt
```
pip install -r requirements.txt
```

Set the new configuration file
```
cp env_config.py.TEMPLATE env_config.py
```

Set the run script
```
cp run.sh.TEMPLATE run.sh
vim run.sh
```
Specify the project namespace and the region in run.sh
```
#!/bin/bash
export AWS_PROFILE=<PROJECT>
export AWS_DEFAULT_REGION=<REGION>
flask run
```


Open the config files and esourcenter the tokens, secrets and IDs that belong to the environment you are deploying to. 
Many of those settings will be available to you until you set the cloud (Step 10). 


Try running Flask

```
flask run
```

You are going to see a message showing the server has started like the following

```
INFO:werkzeug:WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
INFO:werkzeug:Press CTRL+C to quit
```

Flask is up and running but it won't work properly until you set the right secrets and tokens later in the process. 



#### Step 7 
Connect the Tower to Tank

Tank and Tower work together. Tank is the back-end while Tower is the front-end.
Both Tank and Tower are bundled together before deployment
However in development environments, they live in separate folders.
A symbolic link connects them together. The symbolic link is called _tank-frontend

Run this command to see where the symbolic link is pointing to

```
ls -l
```

You should see something like this:

```
_tower -> ../tower/dist
```

The symbolic link already exists in your clone, if you install Tank and Tower in the same folder you don’t need to do anything. However, if you need to modify the symbolic link to point to another folder that contains the Tower clone of your application, 
first, remove the existing symbolic link. This command removes the link but not the target folder. 

```
rm _tower
```

Then, create the new symbolic link

```
ln -s ../<new_dist_location> _tower
```

While the symbolic link will be created, it will not work until you clone Tower in that location for this project.


#### Step 8
Installing Tower dependencies

Go to the tower folder
```
cd ../tower
```


Run npm to install dependencies
```
npm install
npm install vite
```

Install Crypto JS

```
npm install crypto-js
```

Set the Configuration files

You are going to create two new files in the tower root folder called .env.development and .env.production based on the .env.development.TEMPLATE and .env.production.TEMPLATE files as a starting point. 

```
cp .env.development.TEMPLATE .env.development
cp .env.production.TEMPLATE .env.production
```


Don't delete the template files!

Enter the tokens, secrets and IDs that belong to the environment you are deploying to. 

Many of those settings will be available to you until you set the cloud later in the process. Don't worry about them for the time being

Run the dev server

```
npm run dev
```


If you are getting errors, clear the libraries and start over

```
rm -rf node_modules
rm package-lock.json
npm install
```


If you are still getting errors, update the nvm version

```
nvm install 18
```

Set the Tools manifest. Copy the contents of the tools template

```
cd tower/src
cp tools.json.TEMPLATE tools.json
```


Then try running the dev server again

```
npm run dev
```

You should get a message like this one:


```
VITE v5.4.14  ready in 433 ms

➜  Local:   http://127.0.0.1:5173/
➜  press h + enter to show help
  ```

Adding the logo and welcome images

Create two images. 

A small one (500x500 px, Max 100Kb, name: small_logo.jpg) for the Menu header and 

A large one (1000x1000 px, Max 500kb, name: large_logo.jpg) for the log-in page

Place both images in tower/public 

```
cd tools/public
```

The image names are listed in the .gitignore and in the .env.* files. For that reason you must use those names. 



Build the FrontEnd
Tank interacts with the Tower build not with its raw components. 
The Tower build is a compiled version of the application that exists in  tower/dist 

Run the following command in the tower root to generate a build.

```
yarn build
```

If this is a new installation, you'll get a build error like this one: 

```
[vite]: Rollup failed to resolve import "recharts"
```

Go to the next step to resolve it.


### Step 9: Installing the Tool dependencies

Because the tools live outside the Tower repository, they don't share the libraries. 
You need to install the libraries used by the tools in the /tools folder. 

```
cd ../tools
npm install recharts
npm install lucide-react
npm install react-resizable-panels
```

This will automatically create the `node_modules` folder and the files `package-lock.json`, `package.json` and `tscongif.json`

Create a file called `tsconfig.json` file and place it inside of /tools. The contents of the file are as follows:

```
{
    "compilerOptions": {
        "baseUrl": ".",
        "paths": {
        "*": ["tower/node_modules/*"],
        "@tools/*": ["tools/*"]
        }
    }
}
```

Now, try running the build command again

```
cd ../tower
yarn build
```

You should get a message like this one

```
✓ built in 4.08s
✨  Done in 7.42s.
```


### Step 11: Setting up the cloud

IMPORTANT: If you are NOT creating a brand new Cloud Environment and instead are collaborating on an existing one, skip this step and go to Step 12. 

The continuation of this process is explained in the document 

```
tank/CLOUD_README.md
```

You can repeat this process in any computer that will be developing a TankTower tool.




### Step 12: Setting up AWS Credentials


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
 YOUR_ACCESS_KEY, YOUR_SECRET_KEY should be provided by your Cloud Admin.

```
AWS Access Key ID [None]: YOUR_ACCESS_KEY
AWS Secret Access Key [None]: YOUR_SECRET_KEY
Default region name [None]: us-east-1  # (or your preferred region)
Default output format [None]: json
```


### Step 13: Setting up the configuration files

You need to install 3 configuration files in your local environments for your local copy to be able to connect to the cloud: 

Ask your project admin for the config files for your project. 

`tank/env_config.py`
`tower/.env.development.*`
`tower/.env.production.*`

















