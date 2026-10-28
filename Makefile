.PHONY: up build demo load refresh model dashboard test integration down kaku-load kaku-dashboard

# Fixed window for the supplied 2026-10-27 dump. Override both dates for a newer snapshot.
KAKU_START_DATE ?= 2026-09-28
KAKU_END_DATE ?= 2026-10-27

up:
	docker compose up -d warehouse metabase

build:
	docker compose build pipeline

demo:
	docker compose --profile demo up -d --wait warehouse source
	docker compose build pipeline
	docker compose run --rm pipeline python -m ingestion.pipeline --mode full
	docker compose run --rm pipeline dbt build --project-dir warehouse
	docker compose up -d metabase

load:
	docker compose run --rm pipeline python -m ingestion.pipeline --config config/companies.local.json --mode full
	docker compose run --rm pipeline dbt build --project-dir warehouse

refresh:
	docker compose run --rm pipeline python -m ingestion.pipeline --config config/companies.local.json --mode incremental
	docker compose run --rm pipeline dbt build --project-dir warehouse

model:
	docker compose run --rm pipeline dbt build --project-dir warehouse

dashboard:
	docker compose run --rm pipeline python -m dashboards.provision

test:
	uv run --python 3.12 --extra dev pytest -q

integration:
	docker compose --profile demo up -d --wait warehouse source
	docker compose run --rm -e RUN_INTEGRATION=1 pipeline sh -c 'pip install pytest && pytest -q tests/test_integration.py'

down:
	docker compose --profile demo --profile dump --profile kaku down

kaku-load:
	docker compose --profile kaku up -d --wait warehouse kaku-source
	docker compose run --rm pipeline python -m ingestion.pipeline --config config/companies.kaku.json --company kaku --mode full --start-date $(KAKU_START_DATE) --end-date $(KAKU_END_DATE)
	docker compose run --rm pipeline dbt build --project-dir warehouse

kaku-dashboard:
	docker compose run --rm pipeline python -m dashboards.provision --company kaku
