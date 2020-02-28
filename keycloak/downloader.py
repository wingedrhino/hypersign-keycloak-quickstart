import hashlib
from typing import Any, Tuple
from pathlib import Path
from urllib import request
from urllib.parse import urlparse
from os.path import basename
from os import getcwd


class ChecksumMismatchError(Exception):

    def __init__(self, filepath: Path, expected: str, actual: str):
        self.filepath = filepath
        self.expected_value = expected
        self.actual_value = actual

    def __str__(self) -> str:
        return (
            'Checksum Mismatch.\n'
            f'File: {self.filepath}\n'
            f'Expected Checksum: {self.expected_value}\n'
            f'Actual Checksum: {self.actual_value}\n'
            f'Please delete {self.filepath} and try again!'
        )


def sha512sum(filepath: Path) -> str:
    hash_val = hashlib.sha512()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filepath, 'rb', buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            hash_val.update(mv[:n])
    return hash_val.hexdigest()


# is_sha512_valid returns true or false depending on whether a file's expected_checksum
# matched the value provided to it
def is_sha512_valid(filepath: Path, expected_hash: str) -> Tuple[bool, Any]:
    actual_hash = sha512sum(filepath)
    if actual_hash != expected_hash:
        return False, actual_hash
    return True, actual_hash


# dld_with_checks downloads a file and verifies its expected_checksum.
# Algorithm:
# * File Already Present: Calculate expected_checksum
#   * Checksum matches: Continue successfully
#   * Checksum mismatch: Error out. Need to delete file manually now
#  * File not yet Present: download & calculate expected_checksum
#    * Checksum matches: Continue successfully
#    * Checksum mismatch: Error out. Need to delete file manually now
def dld_with_checks(url: str, filepath: Path, expected_checksum: str) -> None:
    if filepath.exists():
        checksum_verified, actual_checksum = is_sha512_valid(filepath, expected_checksum)

        if checksum_verified:
            print(f"Download '{filepath}' from '{url}' already exists. Skipping....")
            return

        else:
            print(f"Download '{filepath}' from '{url}' has expected_checksum '{actual_checksum}' but expected expected_checksum '{expected_checksum}'.")
            print(f"Either update the expected_checksum in this script or delete '{filepath}' and try again!")

    else:
        print(f"Downloading '{url}' to '{filepath}'...")
        request.urlretrieve(url, filepath)
        checksum_verified, actual_checksum = is_sha512_valid(filepath, expected_checksum)

    if not checksum_verified:
        raise ChecksumMismatchError(filepath, expected_checksum, actual_checksum)


# This derives a file's name from its URL
# See: https://stackoverflow.com/a/18727481/1202231
# TODO: check if this works on Windows. It uses back-slash for paths!
def derive_file_name(url: str) -> str:  # eg: https://example.com/path/to/filename.png?token=1111
    parsed_url = urlparse(url)  # breaks the URL down to its components
    url_path_section = parsed_url.path  # returns /path/to/filename.png
    file_name = basename(url_path_section)  # returns filename.png
    return file_name


# dld_with_checks_infer_name downloads the file pointed to by a URL into
# the current directory. It infers the name of the file from the URL
# It returns the path to the downloaded file.
def dld_with_checks_get_path(url: str, expected_checksum: str) -> Path:
    file_name = derive_file_name(url)
    cwd = Path(getcwd())
    dld_file_path = cwd.joinpath(file_name)
    dld_with_checks(url, dld_file_path, expected_checksum)
    return dld_file_path
    pass
