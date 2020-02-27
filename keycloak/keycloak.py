#!/usr/bin/python3

# Stdlib Imports
import os
import shutil
import time
import json
from subprocess import Popen, getstatusoutput, run as sub_run
from pathlib import Path
from typing import List, Tuple, Any, Type, Union

# Third Party Imports
from bs4 import BeautifulSoup  # Ensure LXML is installed

# Environment Variable Arguments
KEYCLOAK_USER = os.getenv('KEYCLOAK_USER', '')
KEYCLOAK_PASSWORD = os.getenv('KEYCLOAK_PASSWORD', '')
KCBASE = os.getenv('KCBASE', '')
KEYCLOAK_MODE = os.getenv('KEYCLOAK_MODE', 'standalone') # standalone is a sane default!
KC_EXECUTION_STRATEGY = os.getenv('KC_EXECUTION_STRATEGY', '')
KC_BASEURL = os.getenv('KC_BASEURL', '')

# Constants
STARTUP_WAIT_SLEEP_TIME = 5  # each time wait 5 seconds
STARTUP_WAIT_MAX_RETRIES = 20  # don't retry more than these many times


# Writes some text to a file
def write_to_file(filepath: Union[str, Path], text: str) -> None:
    with open(filepath, 'w') as fp:
        fp.write(text)


# Reads text from file as string
def read_from_file(filepath: Union[str, Path]) -> str:
    with open(filepath, 'r') as fp:
        content = fp.read()
    return content


# Checks if this text is JSON and then returns the json-encoded text
def to_json_if_json(txt: str) -> Tuple[bool, Any]:
    try:
        json_obj = json.loads(txt, encoding='utf-8')
    except ValueError:
        return False, None
    return True, json_obj


# Used to run keycloak as non-root user
def pre_exec_fn() -> None:
    os.setuid(1000)


class KeycloakError(Exception):
    pass


class JBossCLIError(KeycloakError):

    def __init__(self, exitcode: int, output: str, cmd_name: str, commands: str) -> None:
        self.exitcode = exitcode
        self.output = output
        self.cmd_name = cmd_name
        self.commands = commands

    def __str__(self) -> str:
        return (
            'Error invoking jboss_cli.\n'
            f'Command Name: {self.cmd_name}\n'
            f'Exit Code: {self.exitcode}\n'
            f'Commands:\n{self.commands}\n'
            f'Output:\n{self.output}\n'
        )


class KeycloakAdminCLIError(KeycloakError):

    def __init__(self, exit_code: int, output: str, cli_args: str) -> None:
        self.exit_code = exit_code
        self.output = output
        self.cli_args = cli_args

    def __str__(self) -> str:
        return (
            'Error invoking kcadm_cli.\n'
            f'Exit Code: {self.exit_code}\n'
            f'CLI Args:\n{self.cli_args}\n'
            f'Output:\n{self.output}\n'
        )


class UnknownKeycloakStartupCommandError(KeycloakError):

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        return 'If execution_strategy is not docker or kcdist, provide a custom start command!'


class KeycloakWaitTimeExceededError(KeycloakError):

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        max_wait_time = STARTUP_WAIT_MAX_RETRIES * STARTUP_WAIT_SLEEP_TIME
        return f'Startup exceeds max wait time of {max_wait_time} seconds'


class InvalidKeycloakModeError(KeycloakError):

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        return 'Keycloak Mode be one of standalone, standalone-ha or domain'

# KeycloakHandle is a handle to the main keycloak instance, within docker
class KeycloakHandle:

    # The constructor needs to know the keycloak base directory and either the
    # execution strategy (docker for dockerized keycloak and kcdist if you
    # downloaded keycloak via the bundle on the official website) or a custom
    # start command (in a list form, like ['ls', '-l']).
    def __init__(
            self,
            kcbase: str,
            kc_mode: str,
            kc_user: str,
            kc_pass: str,
            execution_strategy: str,
            custom_start_cmd: List[str] = [],
    ) -> None:

        self._handle = Type[Popen[Any]]
        self._running = False
        self._kc_user = kc_user
        self._kc_pass = kc_pass

        # TODO add checks. this can only be standalone, standalone-ha or domain
        if kc_mode not in ['standalone', 'standalone-ha', 'domain']:
            raise InvalidKeycloakModeError
        self._kc_mode = kc_mode

        cli_suffix = 'bat' if os.name == 'nt' else 'sh'

        self._kcbase = Path(kcbase)

        self._jboss_cli = str(self._kcbase.joinpath('bin').joinpath(f'jboss-cli.{cli_suffix}'))
        self._kcadm_cli = str(self._kcbase.joinpath('bin').joinpath(f'kcadm.{cli_suffix}'))

        if execution_strategy == 'docker':
            self._start_cmd = ['/opt/jboss/tools/docker-entrypoint.sh', '-b', '0.0.0.0']
        elif execution_strategy == 'kcdist':
            self._start_cmd = [f'{kcbase}/bin/standalone.sh']
        elif custom_start_cmd:
            self._start_cmd = custom_start_cmd
        else:
            raise UnknownKeycloakStartupCommandError()

    @property
    def kcbase(self) -> Path:
        return self._kcbase

    def get_module_basedir(self, module_name: str) -> Path:
        return self._kcbase.joinpath('modules').joinpath(module_name)

    def delete_module(self, module_name: str) -> bool:
        module_basedir = self.get_module_basedir(module_name)
        if module_basedir.exists():
            shutil.rmtree(module_basedir)
            return True
        return False

    # https://www.keycloak.org/docs/latest/server_development/index.html#register-a-provider-using-modules
    def add_module(self, module_name: str, jar_path: Path, dependencies: List[str]) -> None:
        cli_name = f'add_module_{module_name}'
        cli_commands = f'module add --name={module_name} --resources={jar_path} --dependencies={",".join(dependencies)}'
        self.jboss_cli_raise_error(cli_name, cli_commands)

    def get_cfg_path(self) -> Path:
        return self._kcbase.joinpath('standalone').joinpath('configuration').joinpath(f'{self._kc_mode}.xml')

    def read_cfg(self) -> Any:
        cfg_path = self.get_cfg_path()
        cfg_txt = read_from_file(cfg_path)
        cfg_xml = BeautifulSoup(cfg_txt, 'xml')
        return cfg_xml

    def write_cfg(self, cfg: Any) -> None:
        cfg_path = self.get_cfg_path()
        write_to_file(cfg_path, str(cfg))

    def get_providers(self) -> Any:  # List[str]: is what we'd like if soup had type annotations
        cfg = self.read_cfg()
        providers_node = cfg.find('subsystem', attrs={'xmlns': 'urn:jboss:domain:keycloak-server:1.1'}).find('providers')
        providers = Type[List[str]]  # initialize empty array
        for provider_node in providers_node.findAll('provider'):
            provider_key = provider_node.text.strip()
            providers.append(provider_key)
        return providers

    def is_module_registered(self, module_name: str) -> bool:
        return f'module:{module_name}' in self.get_providers()

    # https://www.keycloak.org/docs/latest/server_development/#register-a-provider-using-modules
    def register_module(self, module_name: str) -> None:
        if self.is_module_registered(module_name):
            return
        cfg = self.read_cfg()
        providers_node = cfg.find('subsystem', attrs={'xmlns': 'urn:jboss:domain:keycloak-server:1.1'}).find('providers')
        new_provider_node = cfg.new_tag('provider')
        new_provider_node.string = f'module:{module_name}'
        providers_node.append(new_provider_node)
        self.write_cfg(cfg)

    # when provided a file name and text, it creates a config file with this and copies
    # it over to the appropriate location
    def add_config_file_content(self, file_name: str, file_text: str) -> None:
        file_path = self._kcbase.joinpath('standalone').joinpath('configuration').joinpath(file_name)
        write_to_file(file_path, file_text)

    def add_login_theme_files(self, files: List[Path]) -> None:
        install_dir = self._kcbase.joinpath('themes').joinpath('base').joinpath('login')
        for theme_file in files:
            shutil.copy2(theme_file, install_dir)
        pass

    def start(self) -> None:
        if self._running:
            return
        print('Starting KeyCloak...')
        self._handle = Popen(self._start_cmd, preexec_fn=pre_exec_fn)
        time.sleep(60)
        # self.wait_ready()
        self._running = True
        print('...Started KeyCloak!')

    # kcadm_cli invokes the kcadm_cli with the provided cli_args
    # it returns the exit_code and the output of the command
    def kcadm_cli(self, cli_args: str) -> Tuple[int, str]:
        return getstatusoutput(f'{self._kcadm_cli} {cli_args}')

    def kcadm_cli_raise_error(self, cli_args: str) -> str:
        exitcode, output = self.kcadm_cli(cli_args)
        if exitcode != 0:
            raise KeycloakAdminCLIError(exitcode, output, cli_args)
        return output

    def kcadm_cli_as_json_raise_error(self, cli_args: str) -> Any:
        output = self.kcadm_cli_raise_error(cli_args)
        _, json_output = to_json_if_json(output)
        return json_output

    # Create ${KCBASE}/cmd_name.hskc.jboss.cli with the contents of commands and
    # then invoke it via jboss_cli.sh --output-json --file=cmd_name.hskc.jboss.cli
    # The contents of ${KCBASE}/hskc.cmd_name.jboss.cli are left intact, so you can
    # manually execute them later for debugging.
    def jboss_cli(self, cmd_name: str, commands: str) -> Tuple[int, str]:
        cli_name = f'{cmd_name}.hskc.jboss.cli'
        cli_location = self._kcbase.joinpath(cli_name)
        write_to_file(cli_location, commands)
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
        is_json, res = to_json_if_json(output)
        print(f'Keycloak is_ready check. exitcode: {exitcode}. output:\n{output}\n')
        if exitcode != 0 or not is_json or res.get('outcome') != 'success' or res.get('result') != '_running':
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
        if not self._running:
            return False
        print('Stopping KeyCloak...')
        self._handle.terminate()
        self._handle.wait()
        print('...Stopped KeyCloak!')
        self._running = False
        return True

    # Shortcut to manually calling stop() then start()
    def restart(self) -> None:
        print('Restarting KeyCloak...')
        self.stop()
        self.start()
        print('...Restarted KeyCloak!')

    # Returns if this KeycloakHandle points to a currently _running inmstance
    def is_running(self) -> bool:
        return self._running

    # Attempts to login to currently _running keycloak instance
    def login(self) -> None:
        print('Logging into KeyCloak...')
        cli_args = f'config credentials --server http://localhost:8080/auth --realm master --user {self._kc_user} --password {self._kc_pass}'
        self.kcadm_cli_raise_error(cli_args)
        print('...Successfully logged into KeyCloak!')

    # Force kills a keycloak instance that's _running anywhere on localhost
    def kill(self) -> None:
        print('Attempting to kill Keycloak...')
        _, msg = self.jboss_cli('shutdown', 'connect\nshutdown')
        print(msg)
        print('...Done attempting to kill Keycloak!')

    def __del__(self) -> None:
        if self._running:
            print(f'Keycloak Destructor: Premature destruction of _running keycloak handle! Calling stop.')
            self.stop()
            print(f'Keycloak Destructor: Keycloak has (hopefully) been shutdown gracefully. Bye now!')


singleton = KeycloakHandle(KCBASE, KEYCLOAK_MODE, KEYCLOAK_USER, KEYCLOAK_PASSWORD, KC_EXECUTION_STRATEGY)

# When invoked as a script, simply start and login to keycloak!
if __name__ == '__main__':
    singleton.kill()
    singleton.start()
    singleton.login()
    sub_run(['sleep', 'infinity'])
