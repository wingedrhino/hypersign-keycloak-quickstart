#!/usr/bin/python3

# Stdlib Imports
import os
import subprocess
import json
from .env import shell_encoding
from .keycloak import singleton

AUTH_FLOW_NAME = os.getenv('AUTH_FLOW_NAME')
HYPERSIGN_EXECUTION_NAME = os.getenv('HYPERSIGN_EXECUTION_NAME')

# Create HyperSign Execution
def step_create_execution(
  kc = singleton,
  auth_flow_name=AUTH_FLOW_NAME,
  execution_name=HYPERSIGN_EXECUTION_NAME,
):

  print('Checking if HyperSign Execution is present...')
  is_execution_present = False
  # Same command as:
  # ${KCBASE}/bin/kcadm.sh get authentication/flows/${AUTH_FLOW_NAME}/executions --fields displayName --format json -r master
  execution_presence_json = subprocess.check_output([
    kc.kcadm_cli,
    'get', f'authentication/flows/{auth_flow_name}/executions',
    '--fields', 'displayName',
    '--format', 'json',
    '-r', 'master',
  ])
  # The output looks something like:
  # You can examine that yourself by replacing ${AUTH_FLOW_NAME} with 'browser'
  # [
  #   {
  #     "displayName": "Cookie"
  #   },
  #   {
  #     "displayName": "Condition - user configured"
  #   },
  #   {
  #     "displayName": "OTP Form"
  #   }
  # ]
  execution_presence = json.loads(execution_presence_json.decode(shell_encoding()))
  for ep in execution_presence:
    print(f'Found flow {ep.displayName}')
    if ep.displayName == execution_name:
      is_execution_present = True
    # TODO fill me up and figure out the right check
  if is_execution_present:
    print(f'Execution {execution_name} is already configured with "{auth_flow_name}" Auth Flow.')
  else :
    print(f'Creating execution: {execution_name}')
    # This is the same as running
    # ${KCBASE}/bin/kcadm.sh create authentication/flows/${AUTH_FLOW_NAME}/executions/execution -r master -s provider=hyerpsign-qrocde-authenticator -s requirement=REQUIRED
    create_execution_output = subprocess.check_output([
      kc.kcadm_cli,
      'create', f'authentication/flows/{auth_flow_name}/executions/execution',
      '-r', 'master',
      '-s', 'provider=hyerpsign-qrocde-authenticator',
      '-s', 'requirement=REQUIRED'
    ])
    print(f'Creation of execution {execution_name} successful!')