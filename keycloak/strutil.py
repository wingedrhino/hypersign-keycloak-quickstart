import json

# Writes some text to a file
def write_to_file(filepath: str, text: str):
  with open(filepath, 'w') as fp:
    fp.write(text)

# Reads text from file as string
def read_from_file(filepath: str) -> str:
  with open(filepath, 'r') as fp:
    content = fp.read()
  return content

# Checks if this text is JSON and then returns the json-encoded text
def to_json_if_json(txt: str):
  try:
    json_obj = json.loads(txt)
  except ValueError:
    return False, None
  return True, json_obj
