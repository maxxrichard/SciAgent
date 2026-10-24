PY ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: install lint format typecheck test eval run mcp pipelines docs compose-up compose-down clean

install:
	uv venv $(VENV) --python $(PY) || $(PY) -m venv $(VENV)
	uv pip install --python $(BIN)/python -e ".[dev,docs]" || $(BIN)/pip install -e ".[dev,docs]"
	$(BIN)/pre-commit install || true

lint:
	$(BIN)/ruff check src tests dags
	$(BIN)/ruff format --check src tests dags

format:
	$(BIN)/ruff format src tests dags
	$(BIN)/ruff check --fix src tests dags

typecheck:
	$(BIN)/mypy

test:
	$(BIN)/pytest --cov --cov-report=term-missing --cov-report=xml

eval:
	$(BIN)/sciagent eval --gate evals/gate.yaml --out evals/reports/latest

run:
	$(BIN)/sciagent serve --reload

mcp:
	$(BIN)/python -m sciagent.mcp_servers imaging --port 8101 & \
	$(BIN)/python -m sciagent.mcp_servers genomics --port 8102 & \
	$(BIN)/python -m sciagent.mcp_servers clinical --port 8103 & wait

pipelines:
	$(BIN)/sciagent pipelines run all

docs:
	$(BIN)/mkdocs serve

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov site .lake *.db evals/reports
