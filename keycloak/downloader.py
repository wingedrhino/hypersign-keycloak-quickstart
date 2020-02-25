import hashlib
import urllib
import sys
import os

# sha512csum calculates the sha512 checksum of a file
def sha512sum(filepath):
    hash  = hashlib.sha512()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filepath, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            hash.update(mv[:n])
    return hash.hexdigest()

# is_sha512_valid returns true or false depending on whether a file's checksum
# matched the value provided to it
def is_sha512_valid(filepath, expected_value: str) -> bool:
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
    checksum_verified, actual_checksum = is_sha512_valid(filepath, expected_checksum)

    if checksum_verified:
      print(f"Download '{filepath}' from '{url}' already exists. Skipping....")
      return

    else:
      print(f"Download '{filepath}' from '{url}' has checksum '{actual_checksum}' but expected checksum '{expected_checksum}'.")
      print(f"Either update the checksum in this script or delete '{filepath}' and try again!")

  else:
    print(f"Downloading '{url}' to '{filepath}'...")
    urllib.request.urlretrieve(url, filepath)
    checksum_verified, actual_checksum = is_sha512_valid(filepath, expected_checksum)

  if not checksum_verified:
    print(f"Downloaded file '{filepath}' has checksum '{actual_checksum}' but expected'{expected_checksum}'")
    print(f"Either update the checksum in this script or delete '{filepath}' and try again!")
    sys.exit(1)
