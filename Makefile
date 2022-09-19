PYTHON_BIN ?= poetry run python

format: isort black
	exit 0

black:
	$(PYTHON_BIN) -m black --target-version py310 src

isort:
	$(PYTHON_BIN) -m isort src
