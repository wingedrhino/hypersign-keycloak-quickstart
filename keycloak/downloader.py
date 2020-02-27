import hashlib
from typing import Any, Tuple
from pathlib import Path
from urllib import request


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


# is_sha512_valid returns true or false depending on whether a file's checksum
# matched the value provided to it
def is_sha512_valid(filepath: Path, expected_hash: str) -> Tuple[bool, Any]:
    actual_hash = sha512sum(filepath)
    if actual_hash != expected_hash:
        return False, actual_hash
    return True, actual_hash


# dld_with_checks downloads a file and verifies its checksum.
# Algorithm:
# * File Already Present: Calculate checksum
#   * Checksum matches: Continue successfully
#   * Checksum mismatch: Error out. Need to delete file manually now
#  * File not yet Present: download & calculate checksum
#    * Checksum matches: Continue successfully
#    * Checksum mismatch: Error out. Need to delete file manually now
def dld_with_checks(url: str, filepath: Path, expected_checksum: str) -> None:
    if filepath.exists():
        checksum_verified, actual_checksum = is_sha512_valid(filepath, expected_checksum)

        if checksum_verified:
            print(f"Download '{filepath}' from '{url}' already exists. Skipping....")
            return

        else:
            print(f"Download '{filepath}' from '{url}' has checksum '{actual_checksum}' but expected checksum '{expected_checksum}'.")
            print(f"Either update the checksum in this script or delete '{filepath}' and try again!")

    else:
        print(f"Downloading '{url}' to '{filepath}'...")
        request.urlretrieve(url, filepath)
        checksum_verified, actual_checksum = is_sha512_valid(filepath, expected_checksum)

    if not checksum_verified:
        raise ChecksumMismatchError(filepath, expected_checksum, actual_checksum)
