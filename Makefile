# Load environment variables from .env when available.
ifneq (,$(wildcard .env))
include .env
export
endif

SHELL := /bin/bash
MAKEFLAGS += --no-print-directory

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip
PYTEST ?= $(VENV)/bin/pytest
RUFF ?= $(VENV)/bin/ruff
BLACK ?= $(VENV)/bin/black
MANAGE := $(PYTHON) manage.py

CSV ?= TODOS\ OS\ PRODUTOS.csv
XLSX ?=
DEPARTMENT ?= ETA Centro
SOLICITANTE_USERNAME ?= solicitante
SOLICITANTE_PASSWORD ?= solicitante123
CHEFE_USERNAME ?= chefe_secao
CHEFE_PASSWORD ?= chefe123
ALMOX_USERNAME ?= almoxarifado
ALMOX_PASSWORD ?= almox123

.PHONY: help venv install bootstrap dev qa \
	migrate makemigrations run run-prod shell dbshell collectstatic \
	lint format format-check check test test-requests test-material-search \
	import-materials seed-request-users \
	verify-spreadsheet-check verify-spreadsheet-repair verify-spreadsheet-repair-no-sync

help: ## Lista os comandos disponíveis
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-36s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

venv: ## Cria o ambiente virtual em .venv (se não existir)
	@test -d "$(VENV)" || python3 -m venv "$(VENV)"

install: venv ## Instala dependências de runtime e desenvolvimento
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt

bootstrap: install migrate ## Setup inicial completo (deps + migrate)

dev: run ## Alias para subir o servidor de desenvolvimento

qa: lint check test ## Executa lint + checks + testes

migrate: ## Executa migrações
	$(MANAGE) migrate

makemigrations: ## Gera novas migrações
	$(MANAGE) makemigrations

run: ## Executa servidor local (Django runserver)
	$(MANAGE) runserver

run-prod: ## Executa com gunicorn (se instalado)
	$(PYTHON) -m gunicorn config.wsgi:application

shell: ## Abre shell do Django
	$(MANAGE) shell

dbshell: ## Abre shell do banco de dados
	$(MANAGE) dbshell

collectstatic: ## Coleta arquivos estáticos
	$(MANAGE) collectstatic --noinput

lint: ## Roda Ruff e Black em modo checagem
	$(RUFF) check .
	$(BLACK) --check .

format: ## Corrige lint automático com Ruff e formata com Black
	$(RUFF) check . --fix
	$(BLACK) .

format-check: ## Verifica apenas formatação do Black
	$(BLACK) --check .

check: ## Executa django system checks
	$(MANAGE) check

test: ## Roda toda a suíte de testes
	$(PYTEST)

test-requests: ## Roda testes da app requests
	$(PYTEST) -q apps/requests/tests.py

test-material-search: ## Roda apenas testes de busca de materiais
	$(PYTEST) -q apps/requests/tests.py -k material_search

import-materials: ## Importa materiais via CSV (CSV="arquivo.csv")
	$(MANAGE) import_materials_csv "$(CSV)"

seed-request-users: ## Cria/atualiza usuários base de solicitacao (solicitante/chefe/almox)
	$(MANAGE) seed_request_users \
		--department "$(DEPARTMENT)" \
		--solicitante-username "$(SOLICITANTE_USERNAME)" \
		--solicitante-password "$(SOLICITANTE_PASSWORD)" \
		--chefe-username "$(CHEFE_USERNAME)" \
		--chefe-password "$(CHEFE_PASSWORD)" \
		--almox-username "$(ALMOX_USERNAME)" \
		--almox-password "$(ALMOX_PASSWORD)"

verify-spreadsheet-check: ## Verifica planilha de saídas sem reparar
	$(MANAGE) verify_issue_spreadsheet --check-only $(if $(XLSX),--path "$(XLSX)",)

verify-spreadsheet-repair: ## Repara planilha de saídas e sincroniza Drive
	$(MANAGE) verify_issue_spreadsheet $(if $(XLSX),--path "$(XLSX)",)

verify-spreadsheet-repair-no-sync: ## Repara planilha sem sincronizar Drive
	$(MANAGE) verify_issue_spreadsheet --no-sync-drive $(if $(XLSX),--path "$(XLSX)",)
