#!/usr/bin/python3

# Stdlib imports
import subprocess
import json
import os

# Local imports
from env import shell_encoding
from keycloak import singleton

AUTH_FLOW_NAME = os.getenv('AUTH_FLOW_NAME')


# Ensure that HyperSign Flow is present
def ensure_hs_flow(kc = singleton):
  print('Checking if HyperSign flow is present...')
  is_hs_flow_present = False
  # This command is the equivalent of
  # ${KCBASE}/bin/kcadm.sh get authentication/flows --fields alias --format json --noquotes -r master
  auth_flows_json = subprocess.check_output([
    kc.kcadm_cli,
    'get', 'authentication/flows',
    '--fields', 'alias',
    '--format', 'json',
    '--noquotes',
    '-r', 'master',
  ])
  auth_flows = json.loads(auth_flows_json.decode(shell_encoding()))
  for af in auth_flows:
    print(f'Found flow {af}')
    if af.get('alias') == AUTH_FLOW_NAME:
      print('...setting is_hs_flow_present to true!')
      is_hs_flow_present = True

  if is_hs_flow_present:
    print(f'Skipping flow creation since flow "{AUTH_FLOW_NAME}" was found')
  else:
    print(f'Creating flow "{AUTH_FLOW_NAME}"')
    # ${KCBASE}/bin/kcadm.sh create authentication/flows -s alias=${AUTH_FLOW_NAME} -s providerId=basic-flow -s  description=${AUTH_FLOW_NAME} -s  topLevel=true  -s builtIn=false -r master
    create_flow_output = subprocess.check_output([
      kc.kcadm_cli,
      'create', 'authentication/flows',
      '-s', f'alias={AUTH_FLOW_NAME}',
      '-s', 'providerId=basic-flow',
      '-s', f'description={AUTH_FLOW_NAME}', # TODO add a more elaborate description?
      '-s', 'topLevel=true',
      '-s', 'builtIn=false',
      '-r', 'master'
    ])
    # You'd get an output like this:
    # Created new flow with id 'c07da8f0-a563-47dc-8755-8b1c128a4f9a'
    # We just want the last id
    flow_id = create_flow_output # TODO why does this output empty string?
    print(f'Created HyperSign Flow with Flow ID "{flow_id}"')
    kc.restart()

# Main()
if __name__ == '__main__':
  ensure_hs_flow()
