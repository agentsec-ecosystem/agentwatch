.PHONY: help setup format lint typecheck test security-scan release-dry-run stack-up stack-down clean migrate api seed-e2e migrate-db web-install web-typecheck web-test e2e stack-smoke fieldtest fieldtest-gen fieldtest-case fieldtest-v020 fieldtest-suite fieldtest-clean

PYTHON ?= python3
PACKAGES := packages/python-sdk services/api services/analytics

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install all Python packages (with dev extras) for local dev.
	@for pkg in $(PACKAGES); do \
		echo "==> pip install -e $$pkg[dev]"; \
		$(PYTHON) -m pip install -e "$$pkg[dev]"; \
	done

format: ## Auto-format Python (ruff).
	@for pkg in $(PACKAGES); do \
		(cd $$pkg && ruff format . && ruff check . --fix); \
	done

lint: ## Lint Python (ruff).
	@for pkg in $(PACKAGES); do \
		(cd $$pkg && ruff check .); \
	done

typecheck: ## Type-check Python (mypy strict).
	@for pkg in $(PACKAGES); do \
		(cd $$pkg && mypy --strict .); \
	done

test: ## Run all unit tests + coverage gate + repo guard.
	@rc=0; \
	for pkg in $(PACKAGES); do \
		echo "==> pytest $$pkg"; \
		(cd $$pkg && pytest --cov --cov-report=term --cov-fail-under=95) || rc=1; \
	done; \
	echo "==> pytest tests (repo guard)"; \
	$(PYTHON) -m pytest tests || rc=1; \
	exit $$rc

security-scan: ## Run the first-party security scan (gitleaks + trufflehog + pip-audit + egress).
	bash scripts/security_scan.sh

release-dry-run: ## Build + SBOM + checksums + verify-release locally (unsigned; M24 24.4).
	bash scripts/release/dry_run.sh

stack-up: ## Boot the local docker compose stack.
	docker compose up -d

stack-down: ## Tear down the local docker compose stack.
	docker compose down

migrate: ## Run Alembic migrations for the analytics service.
	cd services/analytics && alembic upgrade head

api: ## Run the API service locally.
	cd services/api && uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

migrate-db: ## Create read-model tables in the compose Postgres (the analytics worker also ensure_schema()s).
	@python3 scripts/migrate-db.py

seed-e2e: ## Seed the compose Postgres with mock demo data for e2e testing.
	python3 scripts/seed-e2e-data.py

web-install: ## Install the web app dependencies.
	cd apps/web && npm ci

web-typecheck: ## Type-check the web app.
	cd apps/web && npm run typecheck

web-test: ## Run web unit + axe accessibility tests.
	cd apps/web && npm test

e2e: ## Boot the stack and run the Playwright E2E suite.
	bash scripts/run-e2e.sh

stack-smoke: ## Boot the stack and check that the API and web app answer.
	bash scripts/stack-smoke.sh

fieldtest-gen: ## Regenerate field-test case specs + steps from the registry.
	python3 scripts/fieldtest/gen_cases.py

fieldtest: ## Run the Docker-backed field-test suite (results under field-test/v0.1.0/results/).
	bash scripts/fieldtest/run-all.sh

fieldtest-case: ## Run one field-test case: make fieldtest-case ID=FT-04
	@test -n "$(ID)" || (echo "usage: make fieldtest-case ID=FT-04" >&2 && exit 2)
	bash scripts/fieldtest/run-case.sh "$(ID)"

fieldtest-v020: ## Run the v0.2.0 field-test suite (results under field-test/v0.2.0/results/).
	FT_VERSION=v0.2.0 bash scripts/fieldtest/run-all.sh

fieldtest-suite: ## Run one v0.2.0 suite: make fieldtest-suite SUITE=s1-install
	@test -n "$(SUITE)" || (echo "usage: make fieldtest-suite SUITE=s1-install" >&2 && exit 2)
	FT_VERSION=v0.2.0 bash scripts/fieldtest/run-suite.sh "$(SUITE)"

fieldtest-clean: ## Remove field-test run artifacts (keeps the results .gitkeep).
	find field-test/v0.1.0/results field-test/v0.2.0/results -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null || true

clean: ## Remove generated artifacts.
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned generated artifacts."