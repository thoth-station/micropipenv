#!/bin/bash

# Get the latest pip release
python3 -m venv venv
./venv/bin/pip install --upgrade pip
PIP_VERSION=$(./venv/bin/pip --version | awk '{print $2}')

# Replace it in the micropipenv.py
sed -i "/_SUPPORTED_PIP_STR/s/<=[^\"]*\"/<=$PIP_VERSION\"/" micropipenv.py

# Is there any change to propose?
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  echo "New pip available"

  # Commit the change
  git config --global user.email "lbalhar@redhat.com"
  git config --global user.name "Lumír Balhar"
  git checkout -b update-pip-$PIP_VERSION
  git add micropipenv.py
  git commit -m "Update supported pip to $PIP_VERSION"
  GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=no' git push origin update-pip-$PIP_VERSION

  # Create a pull request using GitHub CLI
  gh pr create --title "Update supported pip to $PIP_VERSION" --body "SSIA"

else
  echo "There is nothing to be done…"
fi
