#!/usr/bin/python3

# Stdlib Imports
import os
import shutil
import time
import json
import xml.etree.ElementTree as ET
from subprocess import Popen, getstatusoutput, run as sub_run
from pathlib import Path
from typing import List, Tuple, Any, Type, Union


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

        self._handle = Type[Popen]
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

    def get_providers(self) -> List[str]:
        cfg_path = self.get_cfg_path()
        cfg = ET.parse(str(cfg_path))
        xpath_str = './/{urn:jboss:domain:keycloak-server:1.1}subsystem/{urn:jboss:domain:keycloak-server:1.1}providers'
        providers_node = cfg.find(xpath_str)
        providers: List[str] = []
        child: ET.Element
        for child in providers_node:
            provider_key = str(child.text).strip()
            providers.append(provider_key)
        return providers

    def is_module_registered(self, module_name: str) -> bool:
        return f'module:{module_name}' in self.get_providers()

    # https://www.keycloak.org/docs/latest/server_development/#register-a-provider-using-modules
    # We are automating the above step by using jboss_cli's write-attribute feature
    # This needs the server to be running. It'll fail otherwise!
    def register_module(self, module_name: str) -> None:
        if self.is_module_registered(module_name):
            return
        providers = self.get_providers()
        providers.append(f'module:{module_name}')
        cli_name = f'add-module-{module_name}'
        cli_cmd = (
            'connect\n'
            f'/subsystem=keycloak-server/:write-attribute(name=providers,value={json.dumps(providers)})'
        )
        self.jboss_cli(cli_name, cli_cmd)
        pass

    # Example output:
    # [ {
    #   "id" : "f53c539b-fdcd-46bf-b529-0b62f38d7f83",
    #   "alias" : "browser",
    #   "description" : "browser based authentication",
    #   "providerId" : "basic-flow",
    #   "topLevel" : true,
    #   "builtIn" : true,
    #   "authenticationExecutions" : [ {
    #     "authenticator" : "auth-cookie",
    #     "requirement" : "ALTERNATIVE",
    #     "priority" : 10,
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : false
    #   }, {
    #     "authenticator" : "auth-spnego",
    #     "requirement" : "DISABLED",
    #     "priority" : 20,
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : false
    #   }, {
    #     "authenticator" : "identity-provider_id-redirector",
    #     "requirement" : "ALTERNATIVE",
    #     "priority" : 25,
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : false
    #   }, {
    #     "requirement" : "ALTERNATIVE",
    #     "priority" : 30,
    #     "flowAlias" : "forms",
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : true
    #   } ]
    # }, {
    #   "id" : "d7e31e5a-9cac-4403-aeb1-c82ba4b51a1f",
    #   "alias" : "direct grant",
    #   "description" : "OpenID Connect Resource Owner Grant",
    #   "providerId" : "basic-flow",
    #   "topLevel" : true,
    #   "builtIn" : true,
    #   "authenticationExecutions" : [ {
    #     "authenticator" : "direct-grant-validate-username",
    #     "requirement" : "REQUIRED",
    #     "priority" : 10,
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : false
    #   }, {
    #     "authenticator" : "direct-grant-validate-password",
    #     "requirement" : "REQUIRED",
    #     "priority" : 20,
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : false
    #   }, {
    #     "requirement" : "CONDITIONAL",
    #     "priority" : 30,
    #     "flowAlias" : "Direct Grant - Conditional OTP",
    #     "userSetupAllowed" : false,
    #     "autheticatorFlow" : true
    #   } ]
    # } ]
    # TODO create a class to serialize the authentication flows output into
    # so that auto-complete works properly
    def list_authentication_flows(self, realm: str) -> Any:
        args = f'get authentication/flows --format json --noquotes -r {realm}'
        flows = self.kcadm_cli_as_json_raise_error(args)
        return flows

    def list_authentication_flow_names(self, realm: str) -> List[str]:
        flows = self.list_authentication_flows(realm)
        return list(map(lambda flow: str(flow.get('alias')), flows))

    def create_authentication_flow(
            self,
            realm: str,
            alias: str,
            provider_id: str,
            description: str,
            top_level: bool,
            built_in: bool,
    ) -> None:
        args = (
            'create authentication/flows'
            f' -s alias="{alias}"'
            f' -s providerId="{provider_id}"'
            f' -s description="{description}"'
            f' -s topLevel={str(top_level).lower()}'
            f' -s builtIn={str(built_in).lower()}'
            f' -r {realm}'
        )
        self.kcadm_cli_raise_error(args)

    # Example output:
    #
    # [ {
    #   "id" : "3f2a3b49-bcf3-4476-a403-4906977de2ac",
    #   "requirement" : "DISABLED",
    #   "displayName" : "HyperSign QRCode",
    #   "requirementChoices" : [ "REQUIRED", "DISABLED", "ALTERNATIVE" ],
    #   "configurable" : true,
    #   "providerId" : "hyerpsign-qrocde-authenticator",
    #   "level" : 0,
    #   "index" : 0
    # } ]
    #
    def list_executions(self, realm: str, auth_flow_name: str) -> Any:
        args = f'get authentication/flows/{auth_flow_name}/executions --format json -r {realm}'
        return self.kcadm_cli_as_json_raise_error(args)

    def list_execution_names(self, realm: str, auth_flow_name: str) -> List[str]:
        executions = self.list_executions(realm, auth_flow_name)
        return list(map(lambda execution: str(execution.get('displayName')), executions))

    def create_execution(self, realm: str, auth_flow_name: str, provider_id: str, requirement: str) -> None:
        args = (
            f'create authentication/flows/{auth_flow_name}/executions/execution'
            f' -r {realm}'
            f' -s provider="{provider_id}"'
            f' -s requirement={requirement}'
        )
        self.kcadm_cli_raise_error(args)

    def create_required_execution(self, realm: str, auth_flow_name: str, provider: str) -> None:
        self.create_execution(realm, auth_flow_name, provider, 'REQUIRED')

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
        # time.sleep(60)
        self.wait_ready()
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
        cmd = f'{self._jboss_cli} --output-json --file="{cli_location}"'
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

    # Returns if this KeycloakHandle points to a currently running inmstance
    def is_running(self) -> bool:
        return self._running

    # Attempts to login to currently running keycloak instance
    def login(self) -> None:
        print('Logging into KeyCloak...')
        cli_args = f'config credentials --server http://localhost:8080/auth --realm master --user {self._kc_user} --password {self._kc_pass}'
        self.kcadm_cli_raise_error(cli_args)
        print('...Successfully logged into KeyCloak!')

    # Force kills a keycloak instance that's running anywhere on localhost
    def kill(self) -> None:
        print('Attempting to kill Keycloak...')
        _, msg = self.jboss_cli('shutdown', 'connect\nshutdown')
        print(msg)
        print('...Done attempting to kill Keycloak!')

    def __del__(self) -> None:
        if self._running:
            print(f'Keycloak Destructor: Premature destruction of running keycloak handle! Calling stop.')
            self.stop()
            print(f'Keycloak Destructor: Keycloak has (hopefully) been shutdown gracefully. Bye now!')


singleton = KeycloakHandle(KCBASE, KEYCLOAK_MODE, KEYCLOAK_USER, KEYCLOAK_PASSWORD, KC_EXECUTION_STRATEGY)

# When invoked as a script, simply start and login to keycloak!
if __name__ == '__main__':
    singleton.kill()
    singleton.start()
    singleton.login()
    sub_run(['sleep', 'infinity'])
