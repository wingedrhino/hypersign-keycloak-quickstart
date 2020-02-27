#!/usr/bin/python3

# Stdlib Imports
import os
import sys
import shutil
from pathlib import Path
import tarfile
from typing import List, Type

# Local Imports
from downloader import dld_with_checks
from keycloak import KeycloakHandle, singleton

# Environment Variables
AUTHENTICATOR_BUILD_URL = os.getenv('AUTHENTICATOR_BUILD_URL', '')
AUTHENTICATOR_TGZ_FILE = os.getenv('AUTHENTICATOR_TGZ_FILE', '')
HS_PLUGIN_JAR = os.getenv('HS_PLUGIN_JAR', '')
AUTHENTICATOR_CHECKSUM = os.getenv('AUTHENTICATOR_CHECKSUM', '')
HS_AUTH_SERVER_ENDPOINT = os.getenv('HS_AUTH_SERVER_ENDPOINT', '')
KCBASE = os.getenv('KCBASE', '')
HYPERSIGN_WORKDIR = os.getenv('HYPERSIGN_WORKDIR', '')

# Constants
MODULE_NAME = 'hs-plugin-keycloak-ejb'
EXTRACT_DIR_NAME = 'hs-authenticator'


def extract_files(workdir: Path, extract_dir: Path, tarball_path: Path) -> None:
    if extract_dir.exists():
        print(f"Deleting directory '{extract_dir}' because it already exists")
        shutil.rmtree(extract_dir)
    tarfile.open(tarball_path).extractall(workdir)
    tarfile.open(extract_dir.joinpath('hs-theme.tar.gz')).extractall(extract_dir)


def install_theme(kc: KeycloakHandle, extract_dir: Path) -> None:
    themes_dir = extract_dir.joinpath('hs-themes')
    files = ['hypersign-config.ftl', 'hypersign.ftl', 'hypersign-new.ftl']
    file_paths = Type[List[Path]]
    for file_name in files:
        file_path = themes_dir.joinpath(file_name)
        file_paths.append(file_path)
    kc.add_login_theme_files(file_paths)


# deploy_config generates a hypersign.properties file that has the
# auth-server-endpoint value correctly set, as per environment variable
def deploy_config(kc: KeycloakHandle, auth_server_endpoint: str) -> None:
    file_name = 'hypersign.properties'
    file_text = (
        '# Hypersign Auth Server (hs-auth-server node app) URL\n'
        f'auth-server-endpoint={auth_server_endpoint}\n'
    )
    kc.add_config_file_content(file_name, file_text)


def deploy_module(kc: KeycloakHandle, module_name: str, jar_path: Path) -> None:

    kc.delete_module(module_name)
    dependencies = [
        'org.keycloak.keycloak-common',
        'org.keycloak.keycloak-core',
        'org.keycloak.keycloak-services',
        'org.keycloak.keycloak-model-jpa',
        'org.keycloak.keycloak-server-spi',
        'org.keycloak.keycloak-server-spi-private',
        'javax.ws.rs.api',
        'javax.persistence.api',
        'org.hibernate',
        'org.javassist',
        'org.liquibase',
        'com.fasterxml.jackson.core.jackson-core',
        'com.fasterxml.jackson.core.jackson-databind',
        'com.fasterxml.jackson.core.jackson-annotations',
        'org.jboss.resteasy.resteasy-jaxrs',
        'org.jboss.logging',
        'org.apache.httpcomponents',
        'org.apache.commons.codec',
        'org.keycloak.keycloak-wildfly-adduser',
    ]

    kc.add_module(module_name, jar_path, dependencies)


def register_module(kc: KeycloakHandle, module_name: str) -> None:
    is_registered = kc.is_module_registered(module_name)
    if is_registered:
        print(f'Module {module_name} is already registered!')
        return
    kc.register_module(module_name)
    print(f'Module {module_name} registered in keycloak!')


# Download HyperSign Keycloak Authenticator, Extract it and Install it!
def step_download_extract_install(kc: KeycloakHandle = singleton) -> None:
    workdir = Path(HYPERSIGN_WORKDIR)
    if not workdir.exists():
        print(f'Exiting because HYPERSIGN_WORKDIR was set to {workdir}, a path that doesn\'t exist.')
        sys.exit(1)
    extract_dir = workdir.joinpath(EXTRACT_DIR_NAME)
    downloaded_tarball = workdir.joinpath(AUTHENTICATOR_TGZ_FILE)
    dld_jar_path = extract_dir.joinpath(HS_PLUGIN_JAR)
    kcbase = Path(KCBASE)\

    dld_with_checks(AUTHENTICATOR_TGZ_FILE, dld_jar_path, AUTHENTICATOR_CHECKSUM)
    extract_files(workdir, extract_dir, downloaded_tarball)
    install_theme(kc, extract_dir)
    deploy_config(kc, HS_AUTH_SERVER_ENDPOINT)
    deploy_module(kc, MODULE_NAME, dld_jar_path)
    register_module(kc, MODULE_NAME)


# Main()
if __name__ == '__main__':

    step_download_extract_install()
