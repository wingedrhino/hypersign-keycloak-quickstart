#!/usr/bin/python3

# Stdlib imports
import os

# Local imports
from keycloak import KeycloakHandle, singleton

AUTH_FLOW_NAME = os.getenv('AUTH_FLOW_NAME', '')


# Ensure that HyperSign Flow is present
def step_ensure_hs_flow(kc: KeycloakHandle = singleton) -> None:
    kc.start()
    kc.login()
    print('Checking if HyperSign flow is present...')
    is_hs_flow_present = False
    args = 'get authentication/flows --fields alias --format json --noquotes -r master'
    auth_flows = kc.kcadm_cli_as_json_raise_error(args)
    for af in auth_flows:
        print(f'Found flow {af}')
        if af.get('alias') == AUTH_FLOW_NAME:
            print('...setting is_hs_flow_present to true!')
            is_hs_flow_present = True

    if is_hs_flow_present:
        print(f'Skipping flow creation since flow "{AUTH_FLOW_NAME}" was found')
    else:
        print(f'Creating flow "{AUTH_FLOW_NAME}"')
        args = f'create authentication/flows -s alias={AUTH_FLOW_NAME} -s providerId=basic-flow -s  description={AUTH_FLOW_NAME} -s  topLevel=true  -s builtIn=false -r master'
        create_flow_result = kc.kcadm_cli_raise_error(args)
        # You'd get an output like this:
        # Created new flow with id 'c07da8f0-a563-47dc-8755-8b1c128a4f9a'
        # We just want the last id
        flow_id = create_flow_result  # TODO why does this output empty string?
        print(f'Created HyperSign Flow with Flow ID "{flow_id}"')
        kc.restart()


# Main()
if __name__ == '__main__':
    step_ensure_hs_flow()
