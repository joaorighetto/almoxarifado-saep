# Development management facilities
#
# This file specifies useful routines to streamline development management.
# See https://www.gnu.org/software/make/.


# Consume environment variables
ifneq (,$(wildcard .env))
	include .env
endif

# Tool configuration
SHELL := /bin/bash
GNUMAKEFLAGS += --no-print-directory

# Path record
ROOT_DIR ?= $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
STATIC_DIR ?= $(ROOT_DIR)/static

# Target files
ENV_FILE ?= .env
PID_FILE ?= .pid
REQUIREMENTS_TXT ?= requirements.txt
MANAGE_PY ?= manage.py
EPHEMERAL_ARCHIVES ?= \
	$(PID_FILE) \
	$(STATIC_DIR) \
	db.sqlite3

# Executables definition
PYTHON_VERSION ?= 3.11
PYTHON ?= $(VENV_DIR)/bin/python$(PYTHON_VERSION)
PIP ?= $(PYTHON) -m pip
DJANGO_ADMIN ?= $(PYTHON) $(MANAGE_PY)
GUNICORN ?= $(PYTHON) -m gunicorn

# Execution configuration
VENV_DIR ?= venv
DJANGO_SETTINGS_MODULE ?= __project__.settings
DJANGO_WSGI_MODULE ?= __project__.wsgi
GUNICORN_SETTINGS_MODULE ?= __project__.gunicorn
LOAD_FIXTURES ?= sample.yaml


%: # Treat unrecognized targets
	@ printf "\033[31;1mUnrecognized routine: '$(*)'\033[0m\n"
	$(MAKE) help

help:: ## Show this help
	@ printf "\033[33;1mGNU-Make available routines:\n"
	egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[37;1m%-20s\033[0m %s\n", $$1, $$2}'

prepare:: ## Inicialize virtual environment
	test -z $(VENV_DIR) -o -d $(VENV_DIR) || python$(PYTHON_VERSION) -m venv $(VENV_DIR)
	test -r $(ENV_FILE) -o ! -r $(ENV_FILE).example || cp $(ENV_FILE).example $(ENV_FILE)

init:: veryclean prepare $(REQUIREMENTS_TXT) ## Configure development environment
	$(PIP) install --upgrade pip
	$(PIP) install -r $(REQUIREMENTS_TXT) --upgrade

execute:: setup run ## Setup and run application

setup:: clean compile ## Process source code into an executable program
	$(DJANGO_ADMIN) makemigrations
	$(DJANGO_ADMIN) migrate --run-syncdb
	test -z $(LOAD_FIXTURES) || $(DJANGO_ADMIN) loaddata $(LOAD_FIXTURES)

compile:: ## Treat file generation
	$(DJANGO_ADMIN) collectstatic --noinput --clear --link

run:: ## Launch application locally
	$(GUNICORN) \
		--pid $(PID_FILE) \
		--config python:$(GUNICORN_SETTINGS_MODULE) \
		$(DJANGO_WSGI_MODULE)

test:: ## Perform unit tests routine
	-rm -fr .pytest_cache/
	-pytest

finish:: ## Stop application execution
	-test -r $(PID_FILE) && pkill --echo --pidfile $(PID_FILE)

clean:: ## Delete project ephemeral archives
	-rm -fr $(EPHEMERAL_ARCHIVES)
	-find . -path "*/migrations/*.py" \
			-not -name "__init__.py" \
			-not -path "./$(VENV_DIR)/*" \
			-delete

veryclean:: clean ## Delete all generated files
	-rm -fr $(VENV_DIR)
	find . -iname "*.pyc" -iname "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +


.EXPORT_ALL_VARIABLES:
.ONESHELL:
.PHONY: help prepare init execute setup compile run test finish clean veryclean
