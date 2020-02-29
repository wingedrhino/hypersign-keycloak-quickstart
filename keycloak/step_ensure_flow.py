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
    flow_names = kc.list_authentication_flow_names('master')
    if AUTH_FLOW_NAME in flow_names:
        is_hs_flow_present = True

    if is_hs_flow_present:
        print(f'Skipping flow creation since flow "{AUTH_FLOW_NAME}" was found')

    else:
        print(f'Creating flow "{AUTH_FLOW_NAME}"')
        kc.create_authentication_flow(
            realm='master',
            alias=AUTH_FLOW_NAME,
            provider_id='basic-flow',
            description=AUTH_FLOW_NAME,
            top_level=True,
            built_in=False)
        print(f'Created HyperSign Flow with Flow ID "{AUTH_FLOW_NAME}"')
        kc.restart()


# Main()
if __name__ == '__main__':
    step_ensure_hs_flow()
