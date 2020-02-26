#!/usr/bin/python3

# Stdlib Imports
import subprocess
import os
import time
import sys
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
    self.message = f'Exception in jboss_cli.\n\Cmdname: {cmdname}.\n\nCommands:\n{commands}\n\n Exit Code: {exitcode}.\n\nOutput:\n{output}\n\n'

class KcadmcliError(KeycloakError):
  def __init__(self, exitcode, output, args):
    self.exitcode = exitcode
    self.output = output
    self.args = args
    self.message = f'Exception in kcadm_cli. Args: "{args}". Exit Code: {exitcode}. Output:\n{output}\n\n'

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
    time.sleep(60)
    # self.wait_ready()
    self.running = True
    print('...Started KeyCloak!')

  # kcadm_cli invokes the kcadm_cli with the provided args
  # it returns the exitcode and the output of the command
  def kcadm_cli(self, args):
    return subprocess.getstatusoutput(f'{self._kcadm_cli} {args}')
  
  def kcadm_cli_raise_error(self, args):
    exitcode, output = self.kcadm_cli(args)
    if exitcode != 0:
      raise KcadmcliError(exitcode, output, args)
    return output

  def kcadm_cli_as_json_raise_error(self, args):
    output = self.kcadm_cli_raise_error(args)
    _, json_output = strutil.to_json_if_json(output)
    return json_output

  # Create ${KCBASE}/cmdname.hskc.jboss.cli with the contents of commands and
  # then invoke it via jboss_cli.sh --output-json --file=cmdname.hskc.jboss.cli
  # The contents of ${KCBASE}/cmdname.jboss.cli are left intact, so you can
  # manually execute them later for debugging.
  def jboss_cli(self, cmdname, commands):
    cli_name = f'{cmdname}.hskc.jboss.cli'
    cli_location = self._kcbase.joinpath(cli_name)
    strutil.write_to_file(cli_location, commands)
    cmd = f'{self._jboss_cli} --echo-command --output-json --file="{cli_location}"'
    exitcode, output = subprocess.getstatusoutput(cmd)
    return exitcode, output
  
  def jboss_cli_raise_error(self, cmdname, commands):
    exitcode, output = self.jboss_cli(cmdname, commands)
    if exitcode != 0:
      raise JbossCliError(exitcode, output, cmdname, commands)
    return output

  def is_ready(self):
    exitcode, output = self.jboss_cli('is-kc-up', 'connect\n:read-attribute(name=server-state)')
    is_json, res = strutil.to_json_if_json(output)
    print(f'Keycloak is_ready check. exitcode: {exitcode}. output:\n{output}\n')
    if exitcode != 0 or not is_json or res.get('outcome') != 'success' or res.get('result') != 'running':
      return False
    return True

  def wait_ready(self):

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
    args = f'config credentials --server http://localhost:8080/auth --realm master --user {KEYCLOAK_USER} --password {KEYCLOAK_PASSWORD}'
    self.kcadm_cli_raise_error(args)
    print('...Successfully logged into KeyCloak!')

  def kill(self):
    print('Attempting to kill Keycloak...')
    _, msg = self.jboss_cli('shutdown', 'connect\nshutdown')
    print(msg)
    print('...Done attempting to kill Keycloak!')

  def __del__(self):
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
  subprocess.run(['sleep', 'infinity'])