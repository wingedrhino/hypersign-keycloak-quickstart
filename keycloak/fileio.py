# Writes some text to a file
def write_to_file(filepath: str, text: str):
  with open(filepath, 'w') as fp:
    fp.write(text)

# Reads text from file as string
def read_from_file(filepath: str) -> str:
  with open(filepath, 'r') as fp:
    content = fp.read()
  return content