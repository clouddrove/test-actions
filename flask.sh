#!/bin/bash

# bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euxo pipefail

# Do a second round of pip install of dev-requirements, if pip fails to install
# a dependency because it must be compiled then run `docker compose build reachtalent-app` once.
pip install --no-deps -r dev-requirements.txt

# Propagate arguments to this shell script to the flask cli.
flask "$@"