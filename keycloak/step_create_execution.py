#!/usr/bin/python3, ''

# Stdlib Imports
import os

# Local Imports
from keycloak import KeycloakHandle, singleton

# Environment Variables
AUTH_FLOW_NAME = os.getenv('AUTH_FLOW_NAME', '')
HYPERSIGN_EXECUTION_NAME = os.getenv('HYPERSIGN_EXECUTION_NAME', '')

# Constants
HYPERSIGN_PROVIDER = 'hyerpsign-qrocde-authenticator'


# Create HyperSign Execution
def step_create_execution(
        kc: KeycloakHandle = singleton,
        auth_flow_name: str = AUTH_FLOW_NAME,
        execution_name: str = HYPERSIGN_EXECUTION_NAME) -> None:
    kc.start()
    kc.login()
    print('Checking if HyperSign Execution is present...')
    available_executions = kc.list_execution_names('master', auth_flow_name)
    if execution_name in available_executions:
        print(f'Execution {execution_name} is already configured with "{auth_flow_name}" Auth Flow.')
    else:
        print(f'Creating execution: {execution_name}')
        kc.create_required_execution(auth_flow_name=auth_flow_name, realm='master', provider=HYPERSIGN_PROVIDER)
        print(f'Creation of execution {execution_name} successful!')


# Main()
if __name__ == '__main__':
    step_create_execution()
