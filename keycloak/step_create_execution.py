#!/usr/bin/python3, ''

# Stdlib Imports
import os

# Local Imports
from keycloak import KeycloakHandle, singleton

AUTH_FLOW_NAME = os.getenv('AUTH_FLOW_NAME', '')
HYPERSIGN_EXECUTION_NAME = os.getenv('HYPERSIGN_EXECUTION_NAME', '')


# Create HyperSign Execution
def step_create_execution(
        kc: KeycloakHandle = singleton,
        auth_flow_name: str = AUTH_FLOW_NAME,
        execution_name: str = HYPERSIGN_EXECUTION_NAME) -> None:
    kc.start()
    kc.login()
    print('Checking if HyperSign Execution is present...')
    is_execution_present = False
    args = f'get authentication/flows/{AUTH_FLOW_NAME}/executions --fields displayName --format json -r master'
    available_executions = kc.kcadm_cli_as_json_raise_error(args)

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

    for ae in available_executions:
        print(f'Found flow {ae.displayName}')
        if ae.displayName == execution_name:
            is_execution_present = True
    if is_execution_present:
        print(f'Execution {execution_name} is already configured with "{auth_flow_name}" Auth Flow.')
    else:
        print(f'Creating execution: {execution_name}')
        # This is the same as _running
        # ${KCBASE}/bin/kcadm.sh create authentication/flows/${AUTH_FLOW_NAME}/executions/execution -r master -s provider=hyerpsign-qrocde-authenticator -s requirement=REQUIRED
        args = f'create authentication/flows/{AUTH_FLOW_NAME}/executions/execution -r master -s provider=hyerpsign-qrocde-authenticator -s requirement=REQUIRED'
        create_execution_result = kc.kcadm_cli_raise_error(args)
        print(f'Creation of execution {execution_name} successful!')


# Main()
if __name__ == '__main__':
    step_create_execution()
