import os
from typing import List


class EnvarEmptyError(Exception):
    def __init__(self, var_name: str):
        self.var_name = var_name

    def __str__(self) -> str:
        return f'EnVar {self.var_name} is empty'


# check_env accepts a list of strings to check that need to be defined as
def check_env(envars: List[str]) -> bool:
    print('Performing Mandatory Environment Variable Check...')
    for envar in envars:
        value = os.getenv(envar)
        print(f'{envar} = {value}')
        if not value:
            print(f'Exiting because {envar} is empty')
            raise EnvarEmptyError(envar)
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
