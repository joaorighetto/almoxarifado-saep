# Comandos e Testes do Projeto

Este documento centraliza os comandos de desenvolvimento, qualidade, importação e verificação já existentes no projeto.

# Pré-requisitos

- Python 3.12
- Ambiente virtual em `.venv`
- Dependências instaladas:

```bash
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

# Setup rápido

```bash
source .venv/bin/activate
make bootstrap
make run
```

# Qualidade de código

## Ruff

```bash
ruff check .
ruff check . --fix
```

## Black

```bash
black .
```

## Check do Django

```bash
python manage.py check
```

# Testes

## Rodar todos

```bash
pytest
```

## Rodar por app

```bash
pytest -q apps/requests/tests.py
pytest -q apps/inventory/tests.py
```

## Rodar subconjunto (busca de materiais)

```bash
pytest -q apps/requests/tests.py -k material_search
```

# Comandos de gestão (management commands)

## Importar materiais e estoque via CSV

Comando: `import_materials_csv`

Colunas esperadas no CSV:

- `CADPRO`
- `DISC1`
- `UNID1`
- `QUAN3`

Uso básico:

```bash
python manage.py import_materials_csv "CAMINHO_DO_CSV.csv"
```

Opções:

- `--dry-run`: valida sem persistir no banco
- `--reset`: zera `StockBalance` e desativa materiais antes de importar

Exemplos:

```bash
python manage.py import_materials_csv "TODOS OS PRODUTOS.csv" --dry-run
python manage.py import_materials_csv "TODOS OS PRODUTOS.csv" --reset
```

## Verificar/Reparar planilha mestre de saídas

Comando: `verify_issue_spreadsheet`

Uso básico:

```bash
python manage.py verify_issue_spreadsheet
```

Opções:

- `--check-only`: apenas verifica divergência, sem reescrever
- `--path`: caminho customizado do XLSX
- `--no-sync-drive`: não sincroniza Google Drive após reparo

Exemplos:

```bash
python manage.py verify_issue_spreadsheet --check-only
python manage.py verify_issue_spreadsheet --path "var/exports/controle_saidas.xlsx"
python manage.py verify_issue_spreadsheet --no-sync-drive
```

## Alvos padronizados (Makefile)

O projeto possui `Makefile` para reduzir variação de comandos entre ambientes.

```bash
make help
make venv
make install
make bootstrap
make dev
make qa
make makemigrations
make migrate
make run
make run-prod
make shell
make dbshell
make collectstatic
make lint
make format
make check
make test
make test-requests
make test-material-search
make import-materials CSV="TODOS OS PRODUTOS.csv"
make verify-spreadsheet-check
make verify-spreadsheet-repair
make verify-spreadsheet-repair-no-sync
```

## Variáveis úteis do Makefile

- `CSV`: caminho do CSV para importação de materiais
- `XLSX`: caminho customizado para verificação/reparo da planilha

Exemplos:

```bash
make import-materials CSV="TODOS OS PRODUTOS.csv"
make verify-spreadsheet-check XLSX="var/exports/controle_saidas.xlsx"
make verify-spreadsheet-repair-no-sync XLSX="var/exports/controle_saidas.xlsx"
```

## Troubleshooting

## Erro de conexão com PostgreSQL ao rodar `pytest`

Se ocorrer erro de conexão em `localhost:5432`, verifique:

- serviço do PostgreSQL ativo
- `DATABASE_URL` no `.env`
- permissões de rede no ambiente/sandbox

Para execução local simplificada em SQLite:

```bash
DATABASE_URL=sqlite:///db.sqlite3 pytest -q apps/requests/tests.py -k material_search
```

## 404 de arquivos estáticos

Confirme:

- `STATIC_URL = "/static/"`
- `STATICFILES_DIRS` inclui `BASE_DIR / "static"`
- hard refresh no navegador após alterações de CSS/JS (`Cmd+Shift+R`)
