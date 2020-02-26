#!/usr/bin/python3
################################################################################
#                                                                              #
#                      HyperSign Installer  for KeyCloak                       #
#                                                                              #
################################################################################

# Stdlib Imports
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

# Local Imports
import env
from step_download_install import step_download_extract_install
from step_ensure_flow import step_ensure_hs_flow
from step_create_execution import step_create_execution

# Look for environment variables that are mandatory
env.check_env( [
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
  'AUTHENTICATOR_BUILD_URL',
  'AUTHENTICATOR_TGZ_FILE',
  'AUTHENTICATOR_CHECKSUM',
  'HS_THEME_FILE',
  'HS_PLUGIN_JAR',
  'AUTH_FLOW_NAME',
  'HYPERSIGN_EXECUTION_NAME',
  'HS_AUTH_SERVER_ENDPOINT',
  'KC_EXECUTION_STRATEGY',
  'KC_BASEURL',
])

# Begin Execution
step_download_extract_install()
step_ensure_hs_flow()
step_create_execution()
subprocess.run(['sleep', 'infinity'])
