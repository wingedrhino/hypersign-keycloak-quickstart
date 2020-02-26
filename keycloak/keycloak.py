#!/usr/bin/python3

# Stdlib Imports
import subprocess
import os
import time
import sys
import json
from pathlib import Path

# Local imports
import strutil

# Environment Variable Arguments
KEYCLOAK_USER = os.getenv('KEYCLOAK_USER')
KEYCLOAK_PASSWORD = os.getenv('KEYCLOAK_PASSWORD')
KCBASE=Path(os.getenv('KCBASE'))
KC_EXECUTION_STRATEGY = os.getenv('KC_EXECUTION_STRATEGY')
KC_BASEURL = os.getenv('KC_BASEURL')

# Constants
STARTUP_WAIT_SLEEP_TIME = 5 # each time wait 5 seconds
STARTUP_WAIT_MAX_RETRIES = 20 # don't retry more than these many times

class KeycloakError(Exception):
  def __str__(self):
    return self.message

class JbossCliError(KeycloakError):
  def __init__(self, exitcode, output, cmdname, commands):
    self.exitcode = exitcode
    self.output = output
    self.cmdname = cmdname
    self.commands = commands
    self.message = f'JBOSS CLI Error.\n\Cmdname: {cmdname}.\n\nCommands:\n{commands}\n\n Exit Code: {exitcode}.\n\nOutput:\n{output}\n\n'

class KeycloakWaitTimeExceededError(KeycloakError):
  def __init__(self):
    self.max_wait_time = STARTUP_WAIT_MAX_RETRIES * STARTUP_WAIT_SLEEP_TIME
    self.message = f'Startup exceeds max wait time of {self.max_wait_time} seconds'

# KeycloakHandle is a handle to the main keycloak instance, within docker
class KeycloakHandle:

  # The constructor needs to know the keycloak base directory and either the
  # execution strategy (docker/kcdist) or a custom start command.
  # If you provide docker or kcdist as the execution strategy, the start command
  # is automatically inferred.
  # Usually start command is ${KCBASE}/bin/standalone.sh but by default we use
  # Docker's own entrypoint
  def __init__(self, kcbase, execution_strategy, custom_startcmd = []):
    
    self.handle = None
    self.running = False

    cli_suffix = 'bat' if os.name == 'nt' else 'sh'

    self._kcbase = kcbase

    self._jboss_cli = str(kcbase.joinpath('bin').joinpath(f'jboss-cli.{cli_suffix}'))
    self._kcadm_cli = str(kcbase.joinpath('bin').joinpath(f'kcadm.{cli_suffix}'))

    startcmd = []
    if execution_strategy == 'docker':
      startcmd = ['/opt/jboss/tools/docker-entrypoint.sh', '-b', '0.0.0.0']
    elif execution_strategy == 'kcdist':
      startcmd = [f'{kcbase}/bin/standalone.sh']
    elif custom_startcmd:
      startcmd = custom_startcmd
    else:
      print('If execution_strategy is not docker or kcdist, provide a custom start command!')
      sys.exit(1)

    # This would be used to start/stop keycloak
    self.startcmd = startcmd

  def start(self):
    if self.running:
      return
    print('Starting KeyCloak...')
    self.handle = subprocess.Popen(
      self.startcmd, # invoke the configured start command, whatever it might be
      preexec_fn=lambda: os.setuid(1000) # We run KeyCloak as non-root user
    )
    self.wait_ready()
    self.running = True
    print('...Started KeyCloak!')

  # kcadm_cli returns where kcadm_cli.sh/kcadm_cli.bat is located
  def kcadm_cli(self) -> str:
    return self.kcadm_cli
  
  # Create ${KCBASE}/cmdname.hskc.jboss.cli with the contents of commands and
  # then invoke it via jboss_cli.sh --output-json --file=cmdname.hskc.jboss.cli
  # The contents of ${KCBASE}/cmdname.jboss.cli are left intact, so you can
  # manually execute them later for debugging.
  def invoke_jboss_cli(self, cmdname, commands):
    cli_name = f'{cmdname}.hskc.jboss.cli'
    cli_location = self._kcbase.joinpath(cli_name)
    strutil.write_to_file(cli_location, commands)
    cmd = f'{self._jboss_cli} --echo-command --output-json --file="{cli_location}"'
    exitcode, output = subprocess.getstatusoutput(cmd)
    return exitcode, output
  
  def invoke_jboss_cli_raise_error(self, cmdname, commands):
    exitcode, output = self.invoke_jboss_cli(cmdname, commands)
    if exitcode != 0:
      raise JbossCliError(exitcode, output, cmdname, commands)

  def is_ready(self):
    exitcode, output = self.invoke_jboss_cli('is-kc-up', 'connect\n:read-attribute(name=server-state)')
    is_json, res = json.loads(output)
    print(f'Keycloak is_ready check. exitcode: {exitcode}. output:\n{output}\n')
    if exitcode != 0 or not is_json or res.get('outcome') != 'success' or res.get('result') != 'running':
      return False
    return True

  def wait_ready(self):

    print('Waiting for keycloak to start....')
  
    total_wait = 0
    def zzz():
      print(f'Going to sleep now for {STARTUP_WAIT_SLEEP_TIME} seconds')
      time.sleep(STARTUP_WAIT_SLEEP_TIME)
      total_wait += STARTUP_WAIT_SLEEP_TIME

    is_ready = False
    for i in range(STARTUP_WAIT_MAX_RETRIES):
      print(f'Checking if keycloak has started. Iteration #{i}')
      is_ready = self.is_ready()
      if is_ready:
        break
      else:
        zzz()
  
    if not is_ready:
      print(f'Max wait time of {STARTUP_WAIT_SLEEP_TIME * STARTUP_WAIT_MAX_RETRIES} seconds exceeded! Throwing exception.')
      raise KeycloakWaitTimeExceededError
    else:
      print(f'Keycloak startup wait took {total_wait} seconds!')

  def stop(self):
    if not self.running:
      return
    print('Stopping KeyCloak...')
    self.handle.terminate()
    self.handle.wait()
    print('...Stopped KeyCloak!')
    self.running = False

  def restart(self):
    print('Restarting KeyCloak...')
    self.stop()
    self.start()
    print('...Restarted KeyCloak!')
  
  def is_running(self):
    return self.running
  
  def login(self):
    print('Logging into KeyCloak...')
    # Same command as:
    # ${KCBASE}/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user ${KEYCLOAK_USER} --password ${KEYCLOAK_PASSWORD}
    subprocess.run([
      self.kcadm_cli(), 'config', 'credentials',
      '--server', f'{KC_BASEURL}/auth',
      '--realm', 'master',
      '--user', KEYCLOAK_USER,
      '--password', KEYCLOAK_PASSWORD,
    ]).check_returncode()
    print('...Successfully logged into KeyCloak!')

  def kill(self):
    self.invoke_jboss_cli_raise_error('shutdown', 'connect\nshutdown')

  def __del__(self):
    if self.running:
      print(f'Keycloak Destructor: Premature destruction of running keycloak handle! Calling stop.')
      self.stop()
      print(f'Keycloak Destructor: Keycloak has (hopefully) been shutdown gracefully. Bye now!')

singleton = KeycloakHandle(KCBASE, KC_EXECUTION_STRATEGY)

# When invoked as a script, simply start and login to keycloak!
if __name__ == '__main__':
  singleton.start()
  singleton.login()
  subprocess.run(['sleep', 'infinity'])