# Stdlib imports
import json
from typing import Any, Tuple, Union
from pathlib import Path

# Local imports
import env


# Writes some text to a file
def write_to_file(filepath: Union[str, Path], text: str) -> None:
    with open(filepath, 'w') as fp:
        fp.write(text)


# Reads text from file as string
def read_from_file(filepath: Union[str, Path]) -> str:
    with open(filepath, 'r') as fp:
        content = fp.read()
    return content


# Checks if this text is JSON and then returns the json-encoded text
def to_json_if_json(txt: str) -> Tuple[bool, Any]:
    try:
        json_obj = json.loads(txt, encoding=env.shell_encoding())
    except ValueError:
        return False, None
    return True, json_obj
