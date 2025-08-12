# Virtual environment paths
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

.PHONY: venv install keys env up initdb run test lint clean help

# Default target
help:
	@echo "Available targets:"
	@echo "  venv     - Create virtual environment"
	@echo "  install  - Install requirements into venv"
	@echo "  keys     - Generate JWT RSA keys"
	@echo "  env      - Copy .env.example to .env if missing"
	@echo "  up       - Start Redis via docker compose"
	@echo "  initdb   - Initialize database and create admin user"
	@echo "  run      - Start FastAPI development server"
	@echo "  test     - Run all tests"
	@echo "  lint     - Format and lint code"
	@echo "  clean    - Clean cache files"

# Create virtual environment if it doesn't exist
venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		python3.12 -m venv $(VENV); \
		$(PIP) install --upgrade pip wheel; \
	else \
		echo "Virtual environment already exists"; \
	fi

# Install requirements (creates venv if needed)
install: venv
	@echo "Installing requirements..."
	@export PYTHONPATH="$(PWD)" && $(PIP) install -r requirements.txt

# Generate JWT keys
keys:
	@echo "Generating JWT RSA keys..."
	@mkdir -p keys
	@if [ ! -f keys/jwtRS256.key ]; then \
		openssl genrsa -out keys/jwtRS256.key 2048; \
		openssl rsa -in keys/jwtRS256.key -pubout -out keys/jwtRS256.key.pub; \
		echo "JWT keys generated"; \
	else \
		echo "JWT keys already exist"; \
	fi

# Copy env file if missing
env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env file created from .env.example"; \
	else \
		echo ".env file already exists"; \
	fi

# Start Redis service
up:
	@echo "Starting Redis..."
	@docker compose up -d redis

# Initialize database
initdb: venv env keys
	@echo "Initializing database..."
	@export PYTHONPATH="$(PWD)" && $(PYTHON) -m app.db.init_db

# Run development server
run: venv
	@echo "Starting FastAPI development server..."
	@export PYTHONPATH="$(PWD)" && $(PYTHON) -m uvicorn app.main:app --reload --port 8000

# Run tests
test: venv
	@echo "Running tests..."
	@export PYTHONPATH="$(PWD)" && $(PYTHON) -m pytest -q

# Lint and format code
lint: venv
	@echo "Formatting and linting code..."
	@export PYTHONPATH="$(PWD)" && $(PYTHON) -m black app/ tests/
	@export PYTHONPATH="$(PWD)" && $(PYTHON) -m ruff app/ tests/
	@export PYTHONPATH="$(PWD)" && $(PYTHON) -m mypy app/

# Clean cache files
clean:
	@echo "Cleaning cache files..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	@find . -name "*.pyc" -delete

# Complete setup from scratch
setup: venv install keys env up initdb
	@echo "Setup complete! Run 'make run' to start the server."

# Docker commands
docker-build:
	@docker compose build

docker-up:
	@docker compose up -d

docker-down:
	@docker compose down

docker-logs:
	@docker compose logs -f api
