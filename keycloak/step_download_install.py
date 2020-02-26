#!/usr/bin/python3

# Stdlib Imports
import os
import shutil
import sys
from pathlib import Path
import tarfile
import subprocess

# Third Party Imports
from bs4 import BeautifulSoup # Ensure LXML is installed

# Local Imports
from downloader import dld_with_checks
from fileio import write_to_file
from fileio import read_from_file
from keycloak import singleton

# Environment Variables
AUTHENTICATOR_BUILD_URL = os.getenv('AUTHENTICATOR_BUILD_URL')
AUTHENTICATOR_TGZ_FILE = os.getenv('AUTHENTICATOR_TGZ_FILE')
HS_PLUGIN_JAR = os.getenv('HS_PLUGIN_JAR')
AUTHENTICATOR_CHECKSUM = os.getenv('AUTHENTICATOR_CHECKSUM')
HS_AUTH_SERVER_ENDPOINT = os.getenv('HS_AUTH_SERVER_ENDPOINT')
KCBASE = os.getenv('KCBASE')
HYPERSIGN_WORKDIR = os.getenv('HYPERSIGN_WORKDIR')

# Constants
MODULE_NAME = 'hs-plugin-keycloak-ejb'
EXTRACT_DIR_NAME = 'hs-authenticator'

# Derive Paths for use by other methods
workdir = Path(HYPERSIGN_WORKDIR)
if not workdir.exists():
  print(f'Exiting because HYPERSIGN_WORKDIR was set to {workdir}, a path that doesn\'t exist.')
  sys.exit(1)
extract_dir = workdir.joinpath(EXTRACT_DIR_NAME)
downloaded_tarball = workdir.joinpath(AUTHENTICATOR_TGZ_FILE)
dld_jar_path = extract_dir.joinpath(HS_PLUGIN_JAR)
kcbase = Path(KCBASE)
copy_jar_path = kcbase.joinpath(HS_PLUGIN_JAR)
module_basedir = kcbase.joinpath('modules').joinpath(MODULE_NAME)


def download_files():
  dld_with_checks(AUTHENTICATOR_BUILD_URL, downloaded_tarball, AUTHENTICATOR_CHECKSUM)

def extract_files():
  if extract_dir.exists():
    print(f"Deleting directory '{extract_dir}' because it already exists")
    shutil.rmtree(extract_dir)
  tarfile.open(downloaded_tarball).extractall(workdir)
  tarfile.open(extract_dir.joinpath('hs-theme.tar.gz')).extractall(extract_dir)

def install_theme():
  theme_extract_dir = extract_dir.joinpath('hs-themes')
  theme_install_dir = kcbase.joinpath('themes').joinpath('base').joinpath('login')
  print(f'Copying hypersign theme from {theme_extract_dir} to {theme_install_dir}...')
  for theme_file_name in ['hypersign-config.ftl', 'hypersign.ftl', 'hypersign-new.ftl']:
    extracted_file_handle = theme_extract_dir.joinpath(theme_file_name)
    installed_file_handle = theme_install_dir.joinpath(theme_file_name)
    if installed_file_handle.exists():
      print(f"File '{installed_file_handle}' already exists. It'll be replaced!")
      installed_file_handle.unlink()
    shutil.copy2(extracted_file_handle, theme_install_dir)
    print(f"Theme file '{theme_install_dir}' installed!")

# deploy_config generates a hypersign.properties file that has the
# auth-server-endpoint value correctly set, as per environment variable
def deploy_config():
  # Deploy HyperSign config file
  print('Deploying configuration file...')
  cfg_file = kcbase.joinpath('standalone').joinpath('configuration').joinpath('hypersign.properties')
  if cfg_file.exists():
    print(f'Found old copy of {cfg_file}. Deleting it!')
    cfg_file.unlink()
  cfg_text =  f'# hs auth server url\nauth-server-endpoint={HS_AUTH_SERVER_ENDPOINT}\n'
  write_to_file(cfg_file, cfg_text)

# Clear module deletes the installed module.
def clear_module():
  if module_basedir.exists():
    print(f'Module already exists at {module_basedir}. It will be deleted.')
    shutil.rmtree(module_basedir)
  if copy_jar_path.exists():
    print(f'File {copy_jar_path} exists. It will be deleted.')
    copy_jar_path.unlink()

# We don't currently use this. This version of deploy module copies files
# manually and assumes that a correctly formatted module.xml is available inside
# the workdir!
# # https://www.keycloak.org/docs/latest/server_development/index.html#register-a-provider-using-modules
def deploy_module_copyfiles():
  os.mkdir(module_basedir)
  module_maindir = module_basedir.joinpath('main')
  os.mkdir(module_maindir)
  shutil.copy2(workdir.joinpath('module.xml'), module_maindir)
  shutil.copy2(dld_jar_path, module_maindir)

# Deploy a module using jboss CLI's add command
# https://www.keycloak.org/docs/latest/server_development/index.html#register-a-provider-using-modules
def deploy_module_cli(kc = singleton):
  print(f'Copying {dld_jar_path} file into {kcbase}...')
  shutil.copy2(dld_jar_path, kcbase)

  # Terminal Command Equivalent:
  #
  # {$KCBASE}.bin/jboss-cli.sh --command="module add --name=hs-plugin-keycloak-ejb --resources=${KCBASE}/${HS_PLUGIN_JAR} --dependencies=org.keycloak.keycloak-common,org.keycloak.keycloak-core,org.keycloak.keycloak-services,org.keycloak.keycloak-model-jpa,org.keycloak.keycloak-server-spi,org.keycloak.keycloak-server-spi-private,javax.ws.rs.api,javax.persistence.api,org.hibernate,org.javassist,org.liquibase,com.fasterxml.jackson.core.jackson-core,com.fasterxml.jackson.core.jackson-databind,com.fasterxml.jackson.core.jackson-annotations,org.jboss.resteasy.resteasy-jaxrs,org.jboss.logging,org.apache.httpcomponents,org.apache.commons.codec,org.keycloak.keycloak-wildfly-adduser"

  # (Working Version): Create a .cli file with commands and pass this to the
  # JBoss CLI to execute
  def deploy_commandfile_cli():
    module_add_cmd = f'module add --name={MODULE_NAME} --resources={kcbase.joinpath(HS_PLUGIN_JAR)} --dependencies=org.keycloak.keycloak-common,org.keycloak.keycloak-core,org.keycloak.keycloak-services,org.keycloak.keycloak-model-jpa,org.keycloak.keycloak-server-spi,org.keycloak.keycloak-server-spi-private,javax.ws.rs.api,javax.persistence.api,org.hibernate,org.javassist,org.liquibase,com.fasterxml.jackson.core.jackson-core,com.fasterxml.jackson.core.jackson-databind,com.fasterxml.jackson.core.jackson-annotations,org.jboss.resteasy.resteasy-jaxrs,org.jboss.logging,org.apache.httpcomponents,org.apache.commons.codec,org.keycloak.keycloak-wildfly-adduser'
    deploy_cli = 'plugin_deploy.cli'
    write_to_file(deploy_cli, module_add_cmd)
    subprocess.run([kc.jboss_cli, f'--file={deploy_cli}']).check_returncode()

  # (Cleaner; non-working version): directly pass commands as arguments to the
  # JBoss CLI to execute.
  def deploy_args_cli():
    subprocess.run([
      kc.jboss_cli,
      f'--command="module add --name={MODULE_NAME} --resources={KCBASE}/{HS_PLUGIN_JAR} --dependencies=org.keycloak.keycloak-common,org.keycloak.keycloak-core,org.keycloak.keycloak-services,org.keycloak.keycloak-model-jpa,org.keycloak.keycloak-server-spi,org.keycloak.keycloak-server-spi-private,javax.ws.rs.api,javax.persistence.api,org.hibernate,org.javassist,org.liquibase,com.fasterxml.jackson.core.jackson-core,com.fasterxml.jackson.core.jackson-databind,com.fasterxml.jackson.core.jackson-annotations,org.jboss.resteasy.resteasy-jaxrs,org.jboss.logging,org.apache.httpcomponents,org.apache.commons.codec,org.keycloak.keycloak-wildfly-adduser"'
    ]).check_returncode()
  
  deploy_commandfile_cli() # Pick the safe option!

def deploy_module(kc = singleton):
  clear_module()
  deploy_module_cli()

# Register HyperSign as a KeyCloak provider using Modules
# https://www.keycloak.org/docs/latest/server_development/#register-a-provider-using-modules
def register_module():
  cfg_path = kcbase.joinpath('standalone') \
                             .joinpath('configuration') \
                             .joinpath('standalone-ha.xml')
  
  provider_key = f'module:{MODULE_NAME}'
  print(f'Inspecting {cfg_path} to see if {provider_key} is registered')

  # Read XML file and parse in Soup
  cfg_text = read_from_file(cfg_path)
  cfg_soup = BeautifulSoup(cfg_text, 'xml')
  
  # Find a subsystem element such that it's
  # xmlns attribute is urn:jboss:domain:keycloak-server:1.1
  # Then find the providers element inside that file.
  providers_node = cfg_soup.find(
    'subsystem',
    attrs={'xmlns':'urn:jboss:domain:keycloak-server:1.1'}
  ).find('providers')

  # Now search through text of each provider element
  is_registered = False
  for provider_node in providers_node.findAll('provider'):
    provider_key = provider_node.text.strip()
    if provider_key == provider_key:
      is_registered = True
      print(f'Found HyperSign Provider {provider_key}! Config update isn\'t needed.')
    else:
      print(f'Found provider {provider_key}')
  
  # Update configuration in-place
  if not is_registered:
    print('Editing Configuration...')
    new_provider_node = cfg_soup.new_tag('provider')
    new_provider_node.string = provider_key
    providers_node.append(new_provider_node)
    write_to_file(cfg_path, str(cfg_soup))

# Download HyperSign Keycloak Authenticator, Extract it and Install it!
def step_download_extract_install(kc = singleton):
  download_files()
  extract_files()
  install_theme()
  deploy_config()
  deploy_module(kc)
  register_module()

# Main()
if __name__ == '__main__':
  step_download_extract_install()