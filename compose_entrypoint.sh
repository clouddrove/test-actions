#!/bin/bash

# bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euxo pipefail

# Do a second round of pip install of dev-requirements, if pip fails to install
# a dependency because it must be compiled then run `docker compose build reachtalent-app` once.
pip install --no-deps -r dev-requirements.txt

# This will ensure local development db schema is up to date.
if [[ "$ENABLE_DB_UPGRADE" -eq 1 ]]; then
  echo "Running flask db upgrade..."
  flask db upgrade
  flask auth sync_data
  flask core update-data --force-update
else
  echo "flask db upgrade: SKIPPED"
fi

# Finally run the http service
# All configurations are pulled from the environment variables. See
# `reachtalent-app/reachtalent/config.py` and `devops/local_docker_compose/.env`
flask run -h 0.0.0.0 -p 8000