#!/usr/bin/python3

# Stdlib Imports
import os
import shutil
import sys
from pathlib import Path
import tarfile

# Third Party Imports
from bs4 import BeautifulSoup # Ensure LXML is installed

# Local Imports
from .downloader import dld_with_checks
from .fileio import write_to_file
from .fileio import read_from_file

AUTHENTICATOR_BUILD_URL = os.getenv('AUTHENTICATOR_BUILD_URL')
AUTHENTICATOR_TGZ_FILE = os.getenv('AUTHENTICATOR_TGZ_FILE')
HS_PLUGIN_JAR = os.getenv('HS_PLUGIN_JAR')
AUTHENTICATOR_CHECKSUM = os.getenv('AUTHENTICATOR_CHECKSUM')
HS_AUTH_SERVER_ENDPOINT = os.getenv('HS_AUTH_SERVER_ENDPOINT')
KCBASE = os.getenv('KCBASE')
HYPERSIGN_WORKDIR = os.getenv('HYPERSIGN_WORKDIR')

# Download HyperSign Keycloak Authenticator, Extract it and Install it!
def step_download_extract_install(workdir_str = HYPERSIGN_WORKDIR):

  original_cwd = os.getcwd()
  workdir = Path(workdir_str)
  if not workdir.exists():
    print(f'Exiting because HYPERSIGN_WORKDIR was set to {workdir}, a path that doesn\'t exist.')
    sys.exit(1)
  os.chdir(workdir)
  print(f'Switched to HyperSign working directory {workdir}')

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

  # Copy theme
  theme_extract_dir = extract_dir.joinpath('hs-themes')
  theme_install_dir = KCBASE.joinpath('themes').joinpath('base').joinpath('login')
  print(f'Copying hypersign theme from {theme_extract_dir} to {theme_install_dir}...')
  for theme_file_name in ['hypersign-config.ftl', 'hypersign.ftl', 'hypersign-new.ftl']:
    extracted_file_handle = theme_extract_dir.joinpath(theme_file_name)
    installed_file_handle = theme_install_dir.joinpath(theme_file_name)
    if installed_file_handle.exists():
      print(f"File '{installed_file_handle}' already exists. It'll be replaced!")
      installed_file_handle.unlink()
    shutil.copy2(extracted_file_handle, theme_install_dir)
    print(f"Theme file '{theme_install_dir}' installed!")

  # Deploy HyperSign config file
  print('Deploying configuration file...')
  cfg_file = KCBASE.joinpath('standalone').joinpath('configuration').joinpath('hypersign.properties')
  if cfg_file.exists():
    print(f'Found old copy of {cfg_file}. Deleting it!')
    cfg_file.unlink()
  cfg_text =  f'# hs auth server url\nauth-server-endpoint={HS_AUTH_SERVER_ENDPOINT}\n'
  write_to_file(cfg_file, cfg_text)

  # Copy plugin JAR
  dld_jar_path = extract_dir.joinpath(HS_PLUGIN_JAR)
  # copy_jar_path = KCBASE.joinpath(HS_PLUGIN_JAR)
  # if copy_jar_path.exists():
  #   print(f'Fike {copy_jar_path} exists. It will be replaced...')
  #   copy_jar_path.unlink()
  # print(f'Copying {dld_jar_path} file into {KCBASE}...')
  # shutil.copy2(dld_jar_path, KCBASE)

  # Note: The next two sections follow from
  # https://www.keycloak.org/docs/latest/server_development/index.html#register-a-provider-using-modules

  # Create a Module for HyperSign
  # We copy the hypersign's jar (extracted) and module.xml (included) into
  # ${KCBASE}/hs-plugin-keycloak-ejb/main
  module_basedir = KCBASE.joinpath('modules').joinpath('hs-plugin-keycloak-ejb')
  if module_basedir.exists():
    print(f'Module already exists at {module_basedir}. It will be deleted & re-created.')
    shutil.rmtree(module_basedir)

  # Okay, I know this sort of variable re-using is bad. But given the situation
  # It is kinda appropria
  os.mkdir(module_basedir)
  module_basedir = module_basedir.joinpath('main')
  os.mkdir(module_basedir)
  shutil.copy2(workdir.joinpath('module.xml'), module_basedir)
  shutil.copy2(dld_jar_path, module_basedir)

  # We are using a command file, however, because it's less unstable
  # module_add_cmd = f'module add --name=hs-plugin-keycloak-ejb --resources={KCBASE.joinpath(HS_PLUGIN_JAR)} --dependencies=org.keycloak.keycloak-common,org.keycloak.keycloak-core,org.keycloak.keycloak-services,org.keycloak.keycloak-model-jpa,org.keycloak.keycloak-server-spi,org.keycloak.keycloak-server-spi-private,javax.ws.rs.api,javax.persistence.api,org.hibernate,org.javassist,org.liquibase,com.fasterxml.jackson.core.jackson-core,com.fasterxml.jackson.core.jackson-databind,com.fasterxml.jackson.core.jackson-annotations,org.jboss.resteasy.resteasy-jaxrs,org.jboss.logging,org.apache.httpcomponents,org.apache.commons.codec,org.keycloak.keycloak-wildfly-adduser'
  # write_to_file('plugin_deploy.cli', module_add_cmd)
  # subprocess.run([jboss_cli, '--file=plugin_deploy.cli']).check_returncode()

  # Register HyperSign as a KeyCloak provider using Modules
  # https://www.keycloak.org/docs/latest/server_development/#register-a-provider-using-modules

  standalone_ha_path = KCBASE.joinpath('standalone') \
                             .joinpath('configuration') \
                             .joinpath('standalone-ha.xml')
  
  hs_provider_key = 'module:hs-plugin-keycloak-ejb'
  print(f'Inspecting {standalone_ha_path} to see if {hs_provider_key} is registered')

  # Read XML file and parse in Soup
  standalone_ha_text = read_from_file(standalone_ha_path)
  standalone_ha_soup = BeautifulSoup(standalone_ha_text, 'xml')
  
  # Find a subsystem element such that it's
  # xmlns attribute is urn:jboss:domain:keycloak-server:1.1
  # Then find the providers element inside that file.
  providers_node = standalone_ha_soup.find(
    'subsystem',
    attrs={'xmlns':'urn:jboss:domain:keycloak-server:1.1'}
  ).find('providers')

  # Now search through text of each provider element
  is_registered = False
  for provider_node in providers_node.findAll('provider'):
    provider_key = provider_node.text.strip()
    if provider_key == hs_provider_key:
      is_registered = True
      print(f'Found HyperSign Provider {provider_key}! Config update isn\'t needed.')
    else:
      print(f'Found provider {provider_key}')
  
  # Update configuration in-place
  if not is_registered:
    print('Editing Configuration...')
    new_provider_node = standalone_ha_soup.new_tag('provider')
    new_provider_node.string = hs_provider_key
    providers_node.append(new_provider_node)
    write_to_file(standalone_ha_path, str(standalone_ha_soup))

  # Finally, come back to original directory
  os.chdir(original_cwd)