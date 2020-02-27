import os
import sys
from typing import List


# check_env accepts a list of strings to check that need to be defined as
def check_env(envars: List[str]) -> bool:
    print('Performing Mandatory Environment Variable Check...')
    for envar in envars:
        value = os.getenv(envar)
        print(f'{envar} = {value}')
        if not value:
            print(f'Exiting because {envar} is empty')
            sys.exit(1)
            return False
    print('...Mandatory Environment Variable Check Completed!')
    return True


# shell_encoding fetches the variable SHELL_ENCODING from the shell
# If it isn't set, it sets it to utf-8 and then returns the SHELL_ENCODING
# TODO this is a hack; need to know how to _actually_ get this info!
def shell_encoding() -> str:
    val = os.getenv('SHELL_ENCODING')
    if not val:
        val = 'utf-8'
        os.environ['SHELL_ENCODING'] = val
    return val
