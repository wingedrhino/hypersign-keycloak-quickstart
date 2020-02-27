#!/usr/bin/python3

# Stdlib Imports
import os
import time
import sys
from subprocess import Popen, getstatusoutput, run as sub_run
from pathlib import Path
from typing import List, Tuple, Any, Type

# Local imports
import strutil

# Environment Variable Arguments
KEYCLOAK_USER = os.getenv('KEYCLOAK_USER', '')
KEYCLOAK_PASSWORD = os.getenv('KEYCLOAK_PASSWORD', '')
KCBASE = os.getenv('KCBASE', '')
KC_EXECUTION_STRATEGY = os.getenv('KC_EXECUTION_STRATEGY', '')
KC_BASEURL = os.getenv('KC_BASEURL', '')

# Constants
STARTUP_WAIT_SLEEP_TIME = 5  # each time wait 5 seconds
STARTUP_WAIT_MAX_RETRIES = 20  # don't retry more than these many times


# Used to run keycloak as non-root user
def pre_exec_fn() -> None:
    os.setuid(1000)


class KeycloakError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


class JBossCLIError(KeycloakError):
    def __init__(self, exitcode: int, output: str, cmd_name: str, commands: str) -> None:
        self.exitcode = exitcode
        self.output = output
        self.cmd_name = cmd_name
        self.commands = commands
        self.message = f'Exception in jboss_cli.\ncmd_name: {cmd_name}.\n\nCommands:\n{commands}\n\n Exit Code: {exitcode}.\n\nOutput:\n{output}\n\n'


class KeycloakAdminCLIError(KeycloakError):
    def __init__(self, exitcode: int, output: str, cli_args: str) -> None:
        self.exitcode = exitcode
        self.output = output
        self.cli_args = cli_args
        self.message = f'Exception in kcadm_cli. cli_args: "{cli_args}". Exit Code: {exitcode}. Output:\n{output}\n\n'


class KeycloakWaitTimeExceededError(KeycloakError):
    def __init__(self) -> None:
        self.max_wait_time = STARTUP_WAIT_MAX_RETRIES * STARTUP_WAIT_SLEEP_TIME
        self.message = f'Startup exceeds max wait time of {self.max_wait_time} seconds'


# KeycloakHandle is a handle to the main keycloak instance, within docker
class KeycloakHandle:

    # The constructor needs to know the keycloak base directory and either the
    # execution strategy (docker for dockerized keycloak and kcdist if you
    # downloaded keycloak via the bundle on the official website) or a custom
    # start command (in a list form, like ['ls', '-l']).
    def __init__(self, kcbase: str, execution_strategy: str, custom_start_cmd: List[str] = []) -> None:

        self._handle = Type[Popen[Any]]
        self.running = False

        cli_suffix = 'bat' if os.name == 'nt' else 'sh'

        self._kcbase = Path(kcbase)

        self._jboss_cli = str(self._kcbase.joinpath('bin').joinpath(f'jboss-cli.{cli_suffix}'))
        self._kcadm_cli = str(self._kcbase.joinpath('bin').joinpath(f'kcadm.{cli_suffix}'))

        start_cmd: List[str] = []
        if execution_strategy == 'docker':
            start_cmd = ['/opt/jboss/tools/docker-entrypoint.sh', '-b', '0.0.0.0']
        elif execution_strategy == 'kcdist':
            start_cmd = [f'{kcbase}/bin/standalone.sh']
        elif custom_start_cmd:
            start_cmd = custom_start_cmd
        else:
            print('If execution_strategy is not docker or kcdist, provide a custom start command!')
            sys.exit(1)

        # This would be used to start/stop keycloak
        self._start_cmd = start_cmd

    def start(self) -> None:
        if self.running:
            return
        print('Starting KeyCloak...')
        self._handle = Popen(self._start_cmd, preexec_fn=pre_exec_fn)
        time.sleep(60)
        # self.wait_ready()
        self.running = True
        print('...Started KeyCloak!')

    # kcadm_cli invokes the kcadm_cli with the provided cli_args
    # it returns the exitcode and the output of the command
    def kcadm_cli(self, cli_args: str) -> Tuple[int, str]:
        return getstatusoutput(f'{self._kcadm_cli} {cli_args}')

    def kcadm_cli_raise_error(self, cli_args: str) -> str:
        exitcode, output = self.kcadm_cli(cli_args)
        if exitcode != 0:
            raise KeycloakAdminCLIError(exitcode, output, cli_args)
        return output

    def kcadm_cli_as_json_raise_error(self, cli_args: str) -> Any:
        output = self.kcadm_cli_raise_error(cli_args)
        _, json_output = strutil.to_json_if_json(output)
        return json_output

    # Create ${KCBASE}/cmd_name.hskc.jboss.cli with the contents of commands and
    # then invoke it via jboss_cli.sh --output-json --file=cmd_name.hskc.jboss.cli
    # The contents of ${KCBASE}/cmd_name.jboss.cli are left intact, so you can
    # manually execute them later for debugging.
    def jboss_cli(self, cmd_name: str, commands: str) -> Tuple[int, str]:
        cli_name = f'{cmd_name}.hskc.jboss.cli'
        cli_location = self._kcbase.joinpath(cli_name)
        strutil.write_to_file(cli_location, commands)
        cmd = f'{self._jboss_cli} --echo-command --output-json --file="{cli_location}"'
        exitcode, output = getstatusoutput(cmd)
        return exitcode, output

    def jboss_cli_raise_error(self, cmd_name: str, commands: str) -> str:
        exitcode, output = self.jboss_cli(cmd_name, commands)
        if exitcode != 0:
            raise JBossCLIError(exitcode, output, cmd_name, commands)
        return output

    def is_ready(self) -> bool:
        exitcode, output = self.jboss_cli('is-kc-up', 'connect\n:read-attribute(name=server-state)')
        is_json, res = strutil.to_json_if_json(output)
        print(f'Keycloak is_ready check. exitcode: {exitcode}. output:\n{output}\n')
        if exitcode != 0 or not is_json or res.get('outcome') != 'success' or res.get('result') != 'running':
            return False
        return True

    def wait_ready(self) -> None:

        print('Waiting for keycloak to start....')

        total_wait = 0

        is_ready = False
        for i in range(STARTUP_WAIT_MAX_RETRIES):
            print(f'Checking if keycloak has started. Iteration #{i}')
            is_ready = self.is_ready()
            if is_ready:
                break
            else:
                print(f'Going to sleep now for {STARTUP_WAIT_SLEEP_TIME} seconds')
                time.sleep(STARTUP_WAIT_SLEEP_TIME)
                total_wait += STARTUP_WAIT_SLEEP_TIME

        if not is_ready:
            print(
                f'Max wait time of {STARTUP_WAIT_SLEEP_TIME * STARTUP_WAIT_MAX_RETRIES} seconds exceeded! Throwing exception.')
            raise KeycloakWaitTimeExceededError
        else:
            print(f'Keycloak startup wait took {total_wait} seconds!')

    # Stops the keycloak instance pointed to by this KeycloakHandle
    # Returns False if the keycloak instance was already stopped
    def stop(self) -> bool:
        if not self.running:
            return False
        print('Stopping KeyCloak...')
        self._handle.terminate()
        self._handle.wait()
        print('...Stopped KeyCloak!')
        self.running = False
        return True

    # Shortcut to manually calling stop() then start()
    def restart(self) -> None:
        print('Restarting KeyCloak...')
        self.stop()
        self.start()
        print('...Restarted KeyCloak!')

    # Returns if this KeycloakHandle points to a currently running inmstance
    def is_running(self) -> bool:
        return self.running

    # Attempts to login to currently running keycloak instance
    def login(self) -> None:
        print('Logging into KeyCloak...')
        cli_args = f'config credentials --server http://localhost:8080/auth --realm master --user {KEYCLOAK_USER} --password {KEYCLOAK_PASSWORD}'
        self.kcadm_cli_raise_error(cli_args)
        print('...Successfully logged into KeyCloak!')

    # Force kills a keycloak instance that's running anywhere on localhost
    def kill(self) -> None:
        print('Attempting to kill Keycloak...')
        _, msg = self.jboss_cli('shutdown', 'connect\nshutdown')
        print(msg)
        print('...Done attempting to kill Keycloak!')

    def __del__(self) -> None:
        if self.running:
            print(f'Keycloak Destructor: Premature destruction of running keycloak handle! Calling stop.')
            self.stop()
            print(f'Keycloak Destructor: Keycloak has (hopefully) been shutdown gracefully. Bye now!')


singleton = KeycloakHandle(KCBASE, KC_EXECUTION_STRATEGY)

# When invoked as a script, simply start and login to keycloak!
if __name__ == '__main__':
    singleton.kill()
    singleton.start()
    singleton.login()
    sub_run(['sleep', 'infinity'])
