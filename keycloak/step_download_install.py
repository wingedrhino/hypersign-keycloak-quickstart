#!/usr/bin/python3

# Stdlib Imports
import os
import shutil
from pathlib import Path
import tarfile
from typing import List, Type

# Local Imports
from downloader import dld_with_checks_get_path
from keycloak import KeycloakHandle, singleton

# Environment Variables
AUTHENTICATOR_BUILD_URL = os.getenv('AUTHENTICATOR_BUILD_URL', '')
AUTHENTICATOR_CHECKSUM = os.getenv('AUTHENTICATOR_CHECKSUM', '')
HS_AUTH_SERVER_ENDPOINT = os.getenv('HS_AUTH_SERVER_ENDPOINT', '')

# Constants
MODULE_NAME = 'hs-plugin-keycloak-ejb'
THEME_TARBALL_NAME = 'hs-theme.tar.gz'


def get_files_in_tarfile(tarball_path: Path) -> List[str]:
    with tarfile.open(tarball_path, mode='r') as archive:
        files = archive.getnames()
    return files


def get_extract_dir(tarball_path: Path) -> Path:
    files = get_files_in_tarfile(tarball_path)
    common_prefix = os.path.commonpath(files)
    return Path(common_prefix)


def get_jar_path(tarball_path: Path) -> Path:

    files = get_files_in_tarfile(tarball_path)

    def ends_with(s: str) -> bool:
        return s.endswith('.jar')

    jar_relative_path = list(filter(ends_with, files))[0]
    cwd = Path(os.getcwd())
    jar_path = cwd.joinpath(jar_relative_path)

    return jar_path


def extract_files(tarball_path: Path) -> None:
    extract_dir = get_extract_dir(tarball_path)
    if extract_dir.exists():
        print(f"Deleting directory '{extract_dir}' because it already exists")
        shutil.rmtree(extract_dir)
    with tarfile.open(tarball_path) as archive:
        archive.extractall()


def install_theme(kc: KeycloakHandle, tarball_path: Path) -> None:
    extract_dir = get_extract_dir(tarball_path)
    themes_tarball = extract_dir.joinpath(THEME_TARBALL_NAME)
    with tarfile.open(themes_tarball) as archive:
        archive.extractall()
    themes_dir = get_extract_dir(themes_tarball)
    file_paths: List[Path] = []
    dir_entry: os.DirEntry
    print(f'Themes have been extracted to {themes_dir}')
    for dir_entry in os.scandir(themes_dir):  # find all files
        file_path = Path(dir_entry.path)
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


def deploy_module(kc: KeycloakHandle, module_name: str, tarball_path: Path) -> None:
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
    jar_path = get_jar_path(tarball_path)
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
    print(f'Downloading plugin from {AUTHENTICATOR_BUILD_URL}')
    hs_tarball = dld_with_checks_get_path(AUTHENTICATOR_BUILD_URL, AUTHENTICATOR_CHECKSUM)
    print(f'Plugin tarball downloaded to {hs_tarball}')
    print('Extracting files...')
    extract_files(hs_tarball)
    print('Installing theme...')
    install_theme(kc, hs_tarball)
    print(f'Deploying configuration. hs-auth-server is at {HS_AUTH_SERVER_ENDPOINT}')
    deploy_config(kc, HS_AUTH_SERVER_ENDPOINT)
    print(f'Deploying module {MODULE_NAME}')
    deploy_module(kc, MODULE_NAME, hs_tarball)
    kc.start()
    if not kc.is_module_registered(MODULE_NAME):
        print(f'Registering module {MODULE_NAME}')
        register_module(kc, MODULE_NAME)
        kc.restart()
    else:
        print(f'Not registering module {MODULE_NAME} since it is already registered!')


# Main()
if __name__ == '__main__':
    step_download_extract_install()
