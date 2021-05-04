#!/usr/bin/python3

"""Helper script for Github CI matrix definition."""

import fileinput
import re

TEMPLATE = '''- python_version: "{}"
  tox_env: "{}"'''

for line in fileinput.input():
    line = line.strip()
    m = re.match(r"^py(\d)(\d+)-", line)
    python_version = "{}.{}".format(*m.groups())
    print(TEMPLATE.format(python_version, line))
