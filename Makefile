UV ?= uv

.PHONY: setup dev dev-native-api dev-native-dashboard worker test lint typecheck build clean health migrate check
setup:
	npm ci
	$(UV) sync --frozen
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build --wait --wait-timeout 180
dev-native-api:
	$(UV) run uvicorn kubesentinel_api.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000 --no-access-log
dev-native-dashboard:
	npm run dev
worker:
	$(UV) run python scripts/setup/run_worker.py
migrate:
	$(UV) run alembic -c apps/api/alembic.ini upgrade head
test:
	npm test
	$(UV) run pytest
lint:
	npm run check:lock
	npm run lint
	npm run lint:docs
	npm run diagrams
	$(UV) run ruff check .
	$(UV) run ruff format --check .
typecheck:
	npm run typecheck
	$(UV) run mypy
build:
	npm run build
	docker compose build
health:
	$(UV) run python scripts/setup/smoke.py
clean:
	docker compose down --remove-orphans
check: lint typecheck test
	$(UV) run python scripts/validate_repository.py
	git diff --check

.PHONY: ml-setup ml-data ml-train ml-evaluate ml-serve ml-test
ml-setup:
	$(UV) sync --frozen --extra ml
ml-data:
	$(UV) run --extra ml python scripts/ml.py generate
ml-train:
	$(UV) run --extra ml python scripts/ml.py train
ml-evaluate:
	$(UV) run --extra ml python scripts/ml.py evaluate --output .cache/ml/repeated
ml-serve:
	$(UV) run python scripts/serve_detector.py
ml-test:
	$(UV) run --extra ml pytest -m "not postgres"

.PHONY: operator-test operator-generate operator-lab operator-clean
operator-test:
	go -C operator test ./... -count=1
	go -C operator vet ./...
operator-generate:
	$(UV) run python scripts/recovery_lab.py generate
operator-lab:
	$(UV) run python scripts/recovery_lab.py bootstrap
operator-clean:
	$(UV) run python scripts/recovery_lab.py clean

.PHONY: operations-setup operations-demo operations-dashboard operations-e2e
operations-setup:
	$(UV) sync --frozen --extra ops
	$(UV) run python scripts/setup/operations_env.py --development
operations-demo:
	$(UV) run python scripts/setup/operations_env.py --development --demo
	$(UV) run python scripts/seed_operations_demo.py
operations-dashboard:
	$(UV) run python scripts/setup/run_operations_dashboard.py
operations-e2e:
	npm run test:e2e:operations
