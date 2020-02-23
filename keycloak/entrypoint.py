#!/usr/bin/python3
################################################################################
#                                                                              #
#           HyperSign Installer & Init Process for Dockerized KeyCloak         #
#           ==========================================================         #
#                                                                              #
# Note: This creates a lockfile for each step in the HYPERSIGN_WORKDIR folder. #
#       Don't delete the *.lock files in the directory you've set in the       #
#       HYPERSIGN_WORKDIR environment variable!                                #
#                                                                              #
################################################################################
import subprocess
import os
import glob
import urllib.request
import sys
import shutil
import tarfile
import time
import json
import hashlib
from typing import List
from pathlib import Path

# Constants also exported as environment variables so that all subprocesses
# have access to them.

# Set Environment Variables
AUTHENTICATOR_BUILD_URL = 'https://github.com/hypermine-bc/hs-authenticator/releases/download/v1.0.1/hs-authenticator.tar.gz'
os.environ['AUTHENTICATOR_BUILD_URL'] = AUTHENTICATOR_BUILD_URL
AUTHENTICATOR_TGZ_FILE = 'hs-authenticator.tar.gz'
os.environ['AUTHENTICATOR_TGZ_FILE'] = AUTHENTICATOR_TGZ_FILE
AUTHENTICATOR_CHECKSUM = '6ce34575a1e0664e56ae6a595d49596f65cf9bee3be626906da0d421b4b459789aabe1d167365174d4f57073e99f52e4e98a9d46712db50a8bf48e436e759424'
os.environ['AUTHENTICATOR_CHECKSUM'] = AUTHENTICATOR_CHECKSUM
HS_THEME_FILE = 'hs-theme.tar.gz'
os.environ['HS_THEME_FILE'] = HS_THEME_FILE
HS_PLUGIN_JAR = 'hs-plugin-keycloak-ejb-0.2-SNAPSHOT.jar'
os.environ['HS_PLUGIN_JAR'] = HS_PLUGIN_JAR
AUTH_FLOW_NAME = 'hs-auth-flow'
os.environ['AUTH_FLOW_NAME'] = AUTH_FLOW_NAME
HYPERSIGN_EXECUTION_NAME='HyperSign QRCode'

# Set Environment Variables that have defaults
SHELL_ENCODING = os.getenv('SHELL_ENCODING')
if not SHELL_ENCODING:
  SHELL_ENCODING = 'utf-8'

# Check Environment Variables are mandatory
envars = [
  'DB_VENDOR',
  'DB_ADDR',
  'DB_DATABASE',
  'DB_USER',
  'DB_SCHEMA',
  'DB_PASSWORD',
  'KEYCLOAK_USER',
  'KEYCLOAK_PASSWORD',
  'KCBASE',
  'HS_REDIRECT_URI',
  'HS_CLIENT_ALIAS',
  'HYPERSIGN_WORKDIR',
]

print('Performing Mandatory Envrionment Variable Check...')
for envar in envars:
  value = os.getenv(envar)
  print(f'{envar} = {value}')
  if not value:
    print(f'Exiting because {envar} is empty')
    sys.exit(1)
print('...Mandatory Environment Vairable Check Completed!')

KCBASE=Path(os.getenv('KCBASE'))

# KeyCloakHandle is a handle to the main keycloak instance
class KeyCloakHandle:

  def __init__(self):
    self.handle = None
    self.running = False

  def start(self):
    print('Starting KeyCloak...')
    self.handle = subprocess.Popen(
      ['/opt/jboss/tools/docker-entrypoint.sh', '-b', '0.0.0.0'],
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

KEYCLOAK_HANDLE = KeyCloakHandle()

def sha512sum(filepath):
    hash  = hashlib.sha512()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filepath, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            hash.update(mv[:n])
    return hash.hexdigest()

def expect_sha512(filepath, expected_value: str):
  actual_value = sha512sum(filepath)
  if actual_value != expected_value:
    return False, actual_value
  return True, actual_value

# dld_with_checks downloads a file and verifies its checksum.
# Algorithm:
# * File Already Present: Calculate checksum
#   * Checksum matches: Continue successfully
#   * Checksum mismatch: Error out. Need to delete file manually now
#  * File not yet Present: download & calculate checksum
#    * Checksum matches: Continue successfully
#    * Checksum mismatch: Error out. Need to delete file manually now
def dld_with_checks(url: str, filepath, expected_checksum: str):

  if filepath.exists():
    checksum_verified, actual_checksum = expect_sha512(filepath, expected_checksum)

    if checksum_verified:
      print(f"Download '{filepath}' from '{url}' already exists. Skipping....")
      return

    else:
      print(f"Download '{filepath}' from '{url}' has checksum '{actual_checksum}' but expected checksum '{expected_checksum}'.")
      print(f"Either update the checksum in this script or delete '{filepath}' and try again!")

  else:
    print(f"Downloading '{url}' to '{filepath}'...")
    urllib.request.urlretrieve(url, filepath)
    checksum_verified, actual_checksum = expect_sha512(filepath, expected_checksum)

  if not checksum_verified:
    print(f"Downloaded file '{filepath}' has checksum '{actual_checksum}' but expected'{expected_checksum}'")
    print(f"Either update the checksum in this script or delete '{filepath}' and try again!")
    sys.exit(1)

# We check if the step represented by this string is a file in workdir
def is_step_complete(step: str):
  step_file = workdir.joinpath(step)
  if step_file.exists():
    return True
  else:
    return False

# Mark step as incomplete
def set_step_incomplete(step: str):
  step_file = workdir.joinpath(step)
  if step_file.exists():
    step_file.remove()

# Mark step as complete
def set_step_complete(step: str):
  step_file = workdir.joinpath(step)
  step_file.touch()

# Run function as a step that only runs once
# Returns True if function was executed; false otherwise
def run_once(step) -> bool:
  step_name = step.__name__ # Yaay to reflection!
  print(f'Executing step {step_name}')
  if is_step_complete(step_name):
    print(f'Step {step_name} already completed! Moving on...')
    return False
  else:
    step()
    set_step_complete(step_name)
    print(f'Step {step_name} finished successfully!')
    return True

# Restart keycloak after this function runs; IF it was run
def run_once_restart(step):
  if run_once(step):
    KEYCLOAK_HANDLE.restart()

# Main execution start!

# Enter WORKDIR
workdir = os.getenv('HYPERSIGN_WORKDIR')
workdir = Path(workdir) # Converts string to Path
if not workdir.exists():
  print(f'Exiting because HYPERSIGN_WORKDIR was set to {workdir}, a path that doesn\'t exist.')
  sys.exit(1)
os.chdir(workdir)
print(f'Switched to HyperSign working directory {workdir}')

# Download HyperSign Keycloak Authenticator & Extract it
def step_download_extract():
  downloaded_tarball = workdir.joinpath(AUTHENTICATOR_TGZ_FILE)
  dld_with_checks(AUTHENTICATOR_BUILD_URL, downloaded_tarball, AUTHENTICATOR_CHECKSUM)
  extract_dir = workdir.joinpath('hs-authenticator')
  if extract_dir.exists():
    print(f"Deleting directory '{extract_dir}' because it already exists")
    shutil.rmtree(extract_dir)
  print('Uncompressing Plugin...')
  tarfile.open(downloaded_tarball).extractall(workdir)
  extract_dir = workdir.joinpath('hs-authenticator')
  os.chdir(extract_dir)
  tarfile.open(extract_dir.joinpath('hs-theme.tar.gz')).extractall(extract_dir)
  # Copy plugin JAR
  print(f'Copying {HS_PLUGIN_JAR} file into {str(KCBASE)}...')
  shutil.copy2(extract_dir.joinpath(HS_PLUGIN_JAR), KCBASE)
  # Copy theme
  theme_from_dir = extract_dir.joinpath('hs-themes')
  theme_to_dir = KCBASE.joinpath('themes').joinpath('base').joinpath('login')
  print(f'Copying hypersign theme from {theme_from_dir} to {theme_to_dir}...')
  shutil.copy2(theme_from_dir.joinpath('hypersign-config.ftl'), theme_to_dir)
  shutil.copy2(theme_from_dir.joinpath('hypersign.ftl'), theme_to_dir)
  shutil.copy2(theme_from_dir.joinpath('hypersign-new.ftl'), theme_to_dir)
  # Deploy HyperSign config file
  print('Deploying configuration file...')
  shutil.copy2('hypersign.properties', KCBASE.joinpath('standalone').joinpath('configuration'))
run_once(step_download_extract)

# Decide if we are on windows or Linux and then set the CLIs
cli_suffix = 'bat' if os.name == 'nt' else 'sh'
jboss_cli = str(KCBASE.joinpath('bin').joinpath(f'jboss-cli.{cli_suffix}'))
kcadm_cli = str(KCBASE.joinpath('bin').joinpath(f'kcadm.{cli_suffix}'))

# Start KeyCloak...
KEYCLOAK_HANDLE.start()

os.chdir(workdir)

# Deploy Plugin
def step_plugin_deploy():
  plugin_deploy_command = f'module add --name=hs-plugin-keycloak-ejb --resources={KCBASE.joinpath(HS_PLUGIN_JAR)} --dependencies=org.keycloak.keycloak-common,org.keycloak.keycloak-core,org.keycloak.keycloak-services,org.keycloak.keycloak-model-jpa,org.keycloak.keycloak-server-spi,org.keycloak.keycloak-server-spi-private,javax.ws.rs.api,javax.persistence.api,org.hibernate,org.javassist,org.liquibase,com.fasterxml.jackson.core.jackson-core,com.fasterxml.jackson.core.jackson-databind,com.fasterxml.jackson.core.jackson-annotations,org.jboss.resteasy.resteasy-jaxrs,org.jboss.logging,org.apache.httpcomponents,org.apache.commons.codec,org.keycloak.keycloak-wildfly-adduser'
  plugin_deploy_cli = open('plugin_deploy.cli', 'w')
  plugin_deploy_cli.write(plugin_deploy_command)
  plugin_deploy_cli.close()
  subprocess.run([jboss_cli, '--file=plugin_deploy.cli']).check_returncode()
run_once(step_plugin_deploy)

# Add HyperSign Module to KeyCloak Configuration
def step_add_hs_module_to_kc_config():
  print('Adding HyperSign module to KeyCloak configuration...')
  subprocess.run([
    jboss_cli,
    '--connect',
    '--controller=localhost:9990',
    '--command=\'/subsystem=keycloak-server/:write-attribute(name=providers,value=["classpath:${jboss.home.dir}/providers/*","module:hs-plugin-keycloak-ejb"])\'',
  ])
run_once_restart(step_add_hs_module_to_kc_config)

# kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user $KEYCLOAK_USER --password $KEYCLOAK_PASSWORD
print('Logging into KeyCloak...')
subprocess.run([
  kcadm_cli, 'config', 'credentials',
  '--server', 'http://localhost:8080/auth',
  '--realm', 'master',
  '--user', os.getenv('KEYCLOAK_USER'),
  '--password', os.getenv('KEYCLOAK_PASSWORD'),
]).check_returncode()
print('...Successfully logged into KeyCloak!')

# Ensure that HyperSign Flow is present
def ensure_hs_flow():
  print('Checking if HyperSign flow is present...')
  is_hs_flow_present = False
  auth_flows_json = subprocess.check_output([
    kcadm_cli,
    'get', 'authentication/flows',
    '--fields', 'alias',
    '--format', 'json',
    '--noquotes',
    '-r', 'master',
  ])
  auth_flows = json.loads(auth_flows_json.decode(SHELL_ENCODING))
  for af in auth_flows:
    print(f'Found flow {af}')
    if af.get('alias') == AUTH_FLOW_NAME:
      print('...setting is_hs_flow_present to true!')
      is_hs_flow_present = True

  if is_hs_flow_present:
    print(f'Skipping flow creation since flow "{AUTH_FLOW_NAME}" was found')
  else:
    print(f'Creating flow "{AUTH_FLOW_NAME}"')
    # kcadm.sh create authentication/flows -s alias=$AUTH_FLOW_NAME -s providerId=basic-flow -s  description=$AUTH_FLOW_NAME -s  topLevel=true  -s builtIn=false -r master
    create_flow_output = subprocess.check_output([
      kcadm_cli,
      'create', 'authentication/flows',
      '-s', f'alias={AUTH_FLOW_NAME}',
      '-s', 'providerId=basic-flow',
      '-s', f'description={AUTH_FLOW_NAME}', # TODO add a more elaborate description?
      '-s', 'topLevel=true',
      '-s', 'builtIn=false',
      '-r', 'master'
    ])
    # You'd get an output like this:
    # Created new flow with id 'c07da8f0-a563-47dc-8755-8b1c128a4f9a'
    # We just want the last id
    flow_id = create_flow_output # TODO FIXME why does this output empty string?
    print(f'Created HyperSign Flow with Flow ID "{flow_id}"')
run_once(ensure_hs_flow)

# Create HyperSign Execution
def step_create_execution():

  print('Checking if HyperSign Execution is present...')
  is_execution_present = False
  # Same command as:
  # kcadm.sh get authentication/flows/$AUTH_FLOW_NAME/executions --fields displayName --format json -r master
  execution_presence_json = subprocess.check_output([
    kcadm_cli,
    'get', f'authentication/flows/{AUTH_FLOW_NAME}/executions',
    '--fields', 'displayName',
    '--format', 'json',
    '-r', 'master',
  ])
  execution_presence = json.loads(execution_presence_json.decode(SHELL_ENCODING))
  for ep in execution_presence:
    print(f'Found flow {ep}')
    # TODO fill me up and figure out the right check
  if is_execution_present:
    print(f'Execution {HYPERSIGN_EXECUTION_NAME} is already configured with "{AUTH_FLOW_NAME}" Auth Flow.')
  else :
    print(f'Creating execution: {HYPERSIGN_EXECUTION_NAME}')
    create_execution_output = subprocess.check_output([
      kcadm_cli,
      'create', f'authentication/flows/{AUTH_FLOW_NAME}/executions/execution',
      '-r', 'master',
      '-s', 'provider=hyerpsign-qrocde-authenticator',
      '-s', 'requirement=REQUIRED'
    ])
    print(f'Creation of execution {HYPERSIGN_EXECUTION_NAME} successful!')

run_once(step_create_execution)

subprocess.run(['sleep', 'infinity'])

# At this point we've basically used Python like an init system

