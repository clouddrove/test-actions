# reachtalent-app
ReachTalent Application - Auth, API

## Development Environment Setup

```shell
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -U -r dev-requirements.txt
```

## Run Development Server
```shell
flask --app reachtalent --debug run -h 0.0.0.0 -p 8000
```
Then visit http://localhost:8000

## Run Tests
```shell
pytest
```

## Build Image For Deployment
```shell
GIT_COMMIT=$(git rev-parse --short HEAD)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo $GIT_COMMIT $GIT_BRANCH

docker build --target deploy \
  -t reachtalent-app \
  --label branch=$GIT_BRANCH \
  --label commit=$GIT_COMMIT \
  .
```

## Managing Dependencies

When updating adding a new dependency or updating the version of a dependency 
modify the pyproject.toml. Put application requirments in `dependencies` under 
`[project]` with fully qualified version. For test/build/development dependencies, 
add to the `dev` list under `[project.optional-dependencies]`. Then run 
`make requirements` which will run `pip-compile` to update both `requirements.txt` 
and `dev-requirements.txt`. 
