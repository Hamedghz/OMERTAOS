.PHONY: dev-control doctor bundle edge-setup test status logs restart start stop \
	setup train train-ci guard model-all run-user run-pro run-ent install-deps \
	lint verify structure-audit compose-config compose-up compose-down \
	compose-clean build-image bootstrap claude-install claude-bootstrap \
	claude-status desktop-dev desktop-build

PY ?= python3
CLI = $(PY) -m aion_core.cli
COMPOSE_FILE ?= deploy/docker/compose/quickstart.yml
COMPOSE = docker compose --project-directory . -f $(COMPOSE_FILE)

dev-control:
	PYTHONPATH=$(CURDIR) uvicorn control.app.main:app --reload --port 8000

doctor:
	bash scripts/doctor.sh

bundle:
	@tar czf deploy/bundles/example.tgz -C deploy/bundles/example .

edge-setup:
	sudo deploy/native/scripts/aion-edge-setup.sh

test:
	PYTHONPATH=$(CURDIR) $(PY) -m pytest -q

APP_DIR ?= /opt/aion/OMERTAOS

status:
	systemctl status omertaos-runtime || true
	systemctl status omertaos-control || true
	systemctl status omertaos-gateway || true
	systemctl status omertaos-console || true

logs:
	journalctl -u omertaos-runtime -n 50 --no-pager
	journalctl -u omertaos-control -n 50 --no-pager
	journalctl -u omertaos-gateway -n 50 --no-pager
	journalctl -u omertaos-console -n 50 --no-pager

restart:
	systemctl restart omertaos-runtime omertaos-control omertaos-gateway omertaos-console

start:
	systemctl start omertaos-runtime omertaos-control omertaos-gateway omertaos-console

stop:
	systemctl stop omertaos-runtime omertaos-control omertaos-gateway omertaos-console

setup:
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e .[control,dev]

train:
	$(PY) scripts/train_eval.py --config policies/training.yaml

train-ci:
	$(PY) scripts/train_eval.py --config policies/training.yaml --ci

guard:
	$(PY) scripts/guard_generalization.py

model-all: setup train guard

run-user:
	AION_PROFILE=user OMERTA_PROFILE=lite $(COMPOSE) up -d

run-pro:
	AION_PROFILE=professional OMERTA_PROFILE=full $(COMPOSE) up -d

run-ent:
	AION_PROFILE=enterprise-vip OMERTA_PROFILE=enterprise FEATURE_SEAL=1 $(COMPOSE) up -d

# Developer quality gates
install-deps:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	npm ci --prefix gateway
	corepack enable
	corepack prepare pnpm@11.13.1 --activate
	pnpm --dir console install --frozen-lockfile

lint:
	pre-commit run --all-files
	npm run lint --prefix gateway --if-present
	pnpm --dir console build

verify:
	bash deploy/ci/verify.sh

structure-audit:
	$(PY) scripts/check_structure_consistency.py

# Docker Compose helpers for the quickstart stack
compose-config:
	$(COMPOSE) config

compose-up:
	$(COMPOSE) up --build -d

compose-down:
	$(COMPOSE) down

compose-clean:
	$(COMPOSE) down -v --remove-orphans

build-image:
	$(COMPOSE) build

bootstrap:
	./quick-install.sh

claude-install:
	bash scripts/claude/install-claude-code.sh

claude-bootstrap:
	bash scripts/claude/bootstrap-marketplace.sh

claude-status:
	bash scripts/claude/status.sh

desktop-dev:
	cd console/desktop-shell && npm run tauri:dev

desktop-build:
	cd console/desktop-shell && npm run tauri:build
