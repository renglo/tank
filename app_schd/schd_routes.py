#app_data.py
from flask import Blueprint,request,redirect,url_for, jsonify, current_app, session, render_template, make_response
from app_auth.login_required import login_required

from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt


from app_schd.schd_controller import SchdController

import time
import random

from env_config import TANK_BASE_URL

app_schd = Blueprint('app_scheduler', __name__, template_folder='templates',url_prefix='/_schd')


SHC = SchdController()


# Set the route and accepted methods

@app_schd.route('/')
@cognito_auth_required
def index():
   #Nothing to show here
    return jsonify(message='')


@app_schd.route('/time')
def timex():
    session['current_user'] = '7e5fb15bb'
    return {
        'time': time.time(),  # This should work correctly now
    }
   

# Cron Rules

#NOT IMPLEMENTED
# Used to get a list of cron rules in an organization
@app_schd.route('/<string:portfolio>/<string:org>/schd_rules',methods=['GET'])
def list_rules(portfolio,org):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to get information about an existing rule (it should reflect eventBridge)
@app_schd.route('/<string:portfolio>/<string:org>/schd_rules/<string:idx>',methods=['GET'])
def get_rule(portfolio,org,idx):   
    return {'success':False}

#NOT IMPLEMENTED. NOT TESTED
# Used to create a new cron rule
@app_schd.route('/<string:portfolio>/<string:org>/schd_rules',methods=['POST'])
def create_rule(portfolio,org):   
    current_app.logger.info('Running Create Rule')
    
    result = SHM.create_https_target_event(
        rule_name='cronrule_'+str(random.randint(1000, 9999)),
        schedule_expression='rate(1 minute)'
    )
      
    return jsonify(result)


#NOT IMPLEMENTED
# Used to modify an existing cron rule
@app_schd.route('/<string:portfolio>/<string:org>/schd_rules/<string:idx>',methods=['PUT'])
def update_rule(portfolio,org,idx):   
    return {'success':False}

#NOT IMPLEMENTED
# Used if you don't want a recurring run to be executed anymore. (Alternatively, you could deactivate it)
@app_schd.route('/<string:portfolio>/<string:org>/schd_rules/<string:idx>',methods=['DELETE'])
def delete_rule(portfolio,org,idx):   
    return {'success':False}


# Job Types

#NOT IMPLEMENTED
# Used to get a list of available jobs for an organization
@app_schd.route('/<string:portfolio>/<string:org>/schd_jobs',methods=['GET'])
def list_jobs(portfolio,org):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to get information about a job type
@app_schd.route('/<string:portfolio>/<string:org>/schd_jobs/<string:idx>',methods=['GET'])
def get_job(portfolio,org,idx):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to create a new job type
@app_schd.route('/<string:portfolio>/<string:org>/schd_jobs',methods=['POST'])
def create_job(portfolio,org):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to modify the parameters of an existing job
@app_schd.route('/<string:portfolio>/<string:org>/schd_jobs/<string:idx>',methods=['PUT'])
def update_job(portfolio,org,idx):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to delete a Job type that is no longer needed
@app_schd.route('/<string:portfolio>/<string:org>/schd_jobs/<string:idx>',methods=['DELETE'])
def delete_job(portfolio,org,idx):   
    return {'success':False}



# Job Runs

#NOT IMPLEMENTED
# Used to get a list of runs in the organization (for troubleshooting purposes)
@app_schd.route('/<string:portfolio>/<string:org>/schd_runs',methods=['GET'])
def list_runs(portfolio,org):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to check the results of a run (for troubleshooting purposes)
@app_schd.route('/<string:portfolio>/<string:org>/schd_runs/<string:idx>',methods=['GET'])
def get_run(portfolio,org,idx):   
    return {'success':False}


# Used to trigger a job execution
@app_schd.route('/<string:portfolio>/<string:org>/create_job_run',methods=['POST'])
def create_job_run(portfolio,org):  
    
    payload = request.get_json()
    response, status = SHC.create_job_run(portfolio,org,payload)
    
    return jsonify(response), status


#NOT IMPLEMENTED
# Used to update the run document with the results of the run
@app_schd.route('/<string:portfolio>/<string:org>/schd_runs/<string:idx>',methods=['PUT'])
def update_run(portfolio,org,idx):   
    return {'success':False}

#NOT IMPLEMENTED
# Used to delete a job run (not usual)
@app_schd.route('/<string:portfolio>/<string:org>/schd_runs/<string:idx>',methods=['DELETE'])
def delete_run(portfolio,org,idx):   
    return {'success':False}




# 1. Route to create a new rule. This is not your regular CRUD. This requires a specialized model

@app_schd.route('/create_rule',methods=['POST'])
def create_rule_x():

    current_app.logger.info('Running Create Rule')
    
    result = SHM.create_https_target_event(
        rule_name='cronrule_'+str(random.randint(1000, 9999)),
        schedule_expression='rate(1 minute)'
    )
    
    
    return jsonify(result)



@app_schd.route('/execute_run')
def execute_run():

    current_app.logger.info('Executing Rule')
    
    session['current_user'] = '7e5fb15bb'
    return {
        'time': time.time(),  # This should work correctly now
    }


