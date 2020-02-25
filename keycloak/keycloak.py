#!/usr/bin/python3

# Stdlib Imports
import subprocess
import os
import time
from pathlib import Path

KEYCLOAK_USER = os.getenv('KEYCLOAK_USER')
KEYCLOAK_PASSWORD = os.getenv('KEYCLOAK_PASSWORD')
KCBASE=Path(os.getenv('KCBASE'))
KC_EXECUTION_STRATEGY = os.getenv('KC_EXECUTION_STRATEGY')
KC_BASEURL = os.getenv('KC_BASEURL')

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
    
    self.jboss_cli = str(kcbase.joinpath('bin').joinpath(f'jboss-cli.{cli_suffix}'))
    self.kcadm_cli = str(kcbase.joinpath('bin').joinpath(f'kcadm.{cli_suffix}'))

    startcmd = []
    if execution_strategy == 'docker':
      startcmd = ['/opt/jboss/tools/docker-entrypoint.sh', '-b', '0.0.0.0']
    elif execution_strategy == 'kcdist':
      startcmd = [f'{kcbase}/bin/standalone.sh']
    elif custom_startcmd:
      startcmd = custom_startcmd
    else:
      print('If execution_strategy is not docker or kcdist, provide a custom start command!')

  def start(self):
    print('Starting KeyCloak...')
    self.handle = subprocess.Popen(
      self.startcmd,
      preexec_fn=lambda: os.setuid(1000) # We run KeyCloak as non-root user
    )
    time.sleep(60) # TODO figure out a better way to wait for startup?
    self.running = True
    print('...Started KeyCloak!')

  def stop(self):
    print('Stopping KeyCloak...')
    self.handle.terminate()
    self.handle.wait()
    time.sleep(20)
    print('...Stopped KeyCloak!')
    self.running = False

  def restart(self):
    print('Restarting KeyCloak...')
    self.stop()
    self.start()
    print('...Restarted KeyCloak!')
  
  def is_running(self):
    return self.running
  
  def kcadm_cli(self):
    return self.kcadm_cli
  
  def jboss_cli(self):
    return self.jboss_cli
  
  def login(self):
    print('Logging into KeyCloak...')
    # Same command as:
    # ${KCBASE}/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user ${KEYCLOAK_USER} --password ${KEYCLOAK_PASSWORD}
    subprocess.run([
      self.kcadm_cli, 'config', 'credentials',
      '--server', f'{KC_BASEURL}/auth',
      '--realm', 'master',
      '--user', KEYCLOAK_USER,
      '--password', KEYCLOAK_PASSWORD,
    ]).check_returncode()
    print('...Successfully logged into KeyCloak!')

singleton = KeycloakHandle(KCBASE, KC_EXECUTION_STRATEGY)