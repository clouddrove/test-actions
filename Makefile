.PHONY: requirements

requirements:
	pip-compile --generate-hashes --resolver backtracking -o requirements.txt pyproject.toml
	pip-compile --generate-hashes --resolver backtracking --extra dev -o dev-requirements.txt pyproject.toml