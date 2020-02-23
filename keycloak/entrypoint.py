#!/usr/bin/python3
################################################################################
#                                                                              #
#           HyperSign Installer & Init Process for Dockerized KeyCloak         #
#                                                                              #
################################################################################
import subprocess
import os
import glob
import urllib.request
import pathlib
import sys
import shutil
import tarfile
import time
import json

# Constants
AUTHENTICATOR_BUILD_URL = 'https://github.com/hypermine-bc/hs-authenticator/releases/download/v1.0.1/hs-authenticator.tar.gz'
os.environ['AUTHENTICATOR_BUILD_URL'] = AUTHENTICATOR_BUILD_URL
AUTHENTICATOR_TGZ_FILE = 'hs-authenticator.tar.gz'
os.environ['AUTHENTICATOR_TGZ_FILE'] = AUTHENTICATOR_TGZ_FILE
HS_THEME_FILE = 'hs-theme.tar.gz'
os.environ['HS_THEME_FILE'] = HS_THEME_FILE
HS_PLUGIN_JAR = 'hs-plugin-keycloak-ejb-0.2-SNAPSHOT.jar'
os.environ['HS_PLUGIN_JAR'] = HS_PLUGIN_JAR
AUTH_FLOW_NAME = 'hs-auth-flow'
os.environ['AUTH_FLOW_NAME'] = AUTH_FLOW_NAME
HYPERSIGN_EXECUTION_NAME='HyperSign QRCode'
os.environ['HYPERSIGN_EXECUTION_NAME'] = HYPERSIGN_EXECUTION_NAME

SHELL_ENCODING = os.getenv('SHELL_ENCODING')
if not SHELL_ENCODING:
  SHELL_ENCODING = 'utf-8'

def start_kc():
  print('Starting KeyCloak...')
  handle = subprocess.Popen(
    ['/opt/jboss/tools/docker-entrypoint.sh', '-b', '0.0.0.0'],
    preexec_fn=lambda: os.setuid(1000) # We run KeyCloak as non-root user
  )
  # TODO figure out a better way to wait for startup?
  time.sleep(40)
  print('...Started KeyCloak!')
  return handle

def stop_kc(kc_process):
  print('Stopping KeyCloak...')
  kc_process.terminate()
  kc_process.wait()
  time.sleep(20)
  print('...Stopped KeyCloak!')

def restart_kc(kc_process):
  print('Restarting KeyCloak...')
  stop_kc(kc_process)
  kc_process = start_kc()
  print('...Restarted KeyCloak!')
  return kc_process

# Check ALL environment variables

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

print('Checking Envrionment Variables...')
for envar in envars:
  value = os.getenv(envar)
  print(f'{envar} = {value}')
  if not value:
    print(f'Exiting because {envar} is empty')
    sys.exit(1)

kcbase=pathlib.Path(os.getenv('KCBASE'))

# Start: Assume that working directory is present

# Delete and re-create working directory
workdir = os.getenv('HYPERSIGN_WORKDIR')
if not workdir:
  workdir = pathlib.Path.home().joinpath('hypersign-setup')
workdir = pathlib.Path(workdir) # Converts string back to Path
shutil.rmtree(workdir, ignore_errors=True)
os.mkdir(workdir)
os.chdir(workdir)

# Download HyperSign Keycloak Authenticator
print(f'Downloading Plugin from {AUTHENTICATOR_BUILD_URL}')
urllib.request.urlretrieve(AUTHENTICATOR_BUILD_URL, AUTHENTICATOR_TGZ_FILE)
print('Uncompressing Plugin...')
tarfile.open(AUTHENTICATOR_TGZ_FILE).extractall(workdir)
extract_dir = workdir.joinpath('hs-authenticator')
os.chdir(extract_dir)
tarfile.open(extract_dir.joinpath('hs-theme.tar.gz')).extractall(extract_dir)

print('Removing old install of HyperSign plugin if present...')
deletables = [
  kcbase.joinpath('hs-plugin-keycloak-ejb-0.2-SNAPSHOT.jar'),
  kcbase.joinpath('modules').joinpath('hs-plugin-keycloak-ejb'),
  kcbase.joinpath('standalone').joinpath('configuration').joinpath('hypersign.properties'),
]
for location in deletables:
  if os.path.exists(location):
    if os.path.isfile(location):
      print(f'Removing file {location}')
      os.remove(location)
    else:
      print(f'Removing directory {location}')
      shutil.rmtree(location)

# Copy plugin JAR
print(f'Copying {HS_PLUGIN_JAR} file into {str(kcbase)}...')
shutil.copy2(extract_dir.joinpath(HS_PLUGIN_JAR), kcbase)

# Copy theme
theme_from_dir = extract_dir.joinpath('hs-themes')
theme_to_dir = kcbase.joinpath('themes').joinpath('base').joinpath('login')
print(f'Copying hypersign theme from {theme_from_dir} to {theme_to_dir}...')
shutil.copy2(theme_from_dir.joinpath('hypersign-config.ftl'), theme_to_dir)
shutil.copy2(theme_from_dir.joinpath('hypersign.ftl'), theme_to_dir)
shutil.copy2(theme_from_dir.joinpath('hypersign-new.ftl'), theme_to_dir)

# Deploy HyperSign config file
print('Deploying configuration file...')
shutil.copy2('hypersign.properties', kcbase.joinpath('standalone').joinpath('configuration'))

# Decide if we are on windows or Linux and then set the CLIs
cli_suffix = 'bat' if os.name == 'nt' else 'sh'
jboss_cli = str(kcbase.joinpath('bin').joinpath(f'jboss-cli.{cli_suffix}'))
kcadm_cli = str(kcbase.joinpath('bin').joinpath(f'kcadm.{cli_suffix}'))

os.chdir(workdir)

print('Deploying the HyperSign plugin...')
plugin_deploy_command = f'module add --name=hs-plugin-keycloak-ejb --resources={kcbase.joinpath(HS_PLUGIN_JAR)} --dependencies=org.keycloak.keycloak-common,org.keycloak.keycloak-core,org.keycloak.keycloak-services,org.keycloak.keycloak-model-jpa,org.keycloak.keycloak-server-spi,org.keycloak.keycloak-server-spi-private,javax.ws.rs.api,javax.persistence.api,org.hibernate,org.javassist,org.liquibase,com.fasterxml.jackson.core.jackson-core,com.fasterxml.jackson.core.jackson-databind,com.fasterxml.jackson.core.jackson-annotations,org.jboss.resteasy.resteasy-jaxrs,org.jboss.logging,org.apache.httpcomponents,org.apache.commons.codec,org.keycloak.keycloak-wildfly-adduser'
plugin_deploy_cli = open('plugin_deploy.cli', 'w')
plugin_deploy_cli.write(plugin_deploy_command)
plugin_deploy_cli.close()
subprocess.run([jboss_cli, '--file=plugin_deploy.cli']).check_returncode()

# Start KeyCloak...
kc_process = start_kc()
print('Adding HyperSign module to KeyCloak configuration...')
subprocess.run([
  jboss_cli,
  '--connect',
  '--controller=localhost:9990',
  '--command=\'/subsystem=keycloak-server/:write-attribute(name=providers,value=["classpath:${jboss.home.dir}/providers/*","module:hs-plugin-keycloak-ejb"])\'',
])

# Restart KeyCloak...
kc_process = restart_kc(kc_process)

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
  

# Restart KeyCloak
kc_process = restart_kc(kc_process)
subprocess.run(['sleep', 'infinity'])

# At this point we've basically used Python like an init system

