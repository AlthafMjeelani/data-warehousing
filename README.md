# Multi-company sales data warehouse

A standalone learning project and first sales-analytics implementation for multiple company databases.
It reads compatible MySQL source schemas, loads PostgreSQL, transforms data with dbt, and displays it in Metabase.
It does not modify the application repository or source business records.

## Project documentation

- [Architecture, features, tools and techniques](docs/ARCHITECTURE.md)
- [KAKU real-data import, dashboard and DBeaver instructions](docs/KAKU_IMPORT.md)
- [Metric definitions](docs/METRICS.md)
- [Verification history](docs/VERIFICATION.md)

KAKU's last-30-days snapshot (2026-09-28 through 2026-10-27) is available in the existing PostgreSQL warehouse.
Its dashboard is <http://localhost:3000/dashboard/3> in the current local environment.
ClickHouse is not part of the current implementation.

## What is included

- Direct MySQL connections for local or remote sources.
- An isolated MySQL container for synthetic demo data and SQL dump restoration.
- Stable company IDs, per-company checkpoints, batch loading and atomic per-company transactions.
- Full loads and timestamp-based incremental transaction loads with a 24-hour overlap.
- Explicit source-column allowlists that exclude customer contact details and user credentials.
- Sales dimensions, a line-grain fact, reporting views, and dbt data checks.
- A dashboard provisioner with company/currency-separated tables and a refresh-status panel.
- Unit tests and an opt-in integration test against the two synthetic demo companies.

This is a first sales slice, not a complete finance, inventory or operations warehouse.
See [metric definitions and limitations](docs/METRICS.md) before using the figures for decisions.

## 1. Prerequisites

- Docker Engine or Docker Desktop running, with Docker Compose.
- `make` for the convenience commands; the underlying Docker commands also work directly.
- Available localhost ports: `3000` (Metabase), `55432` (warehouse), `53306` (optional source).
- Internet access for the initial container images and Python dependencies.
- Optional: `uv` and Python 3.12 for development outside containers.

Check Docker first:

```sh
docker info
docker compose version
```

If `docker info` reports a missing socket, start your Docker runtime before continuing.

## 2. Try two demo companies

Run these commands from this project folder:

```sh
cp .env.example .env
make demo
```

`make demo` starts PostgreSQL and demo MySQL, builds the pipeline image, loads both companies, builds/tests dbt models, and starts Metabase.
The first run downloads images and dependencies.
Subsequent runs reuse persistent database volumes.

### Check your data immediately

```sh
docker compose exec warehouse psql -U warehouse -d analytics -c \
  'SELECT company_id, currency_code, SUM(net_sales_excluding_tax) FROM marts.mart_daily_sales GROUP BY 1,2 ORDER BY 1;'
```

Expected synthetic results:

| company_id | currency_code | net_sales_excluding_tax |
|---|---|---:|
| company_a | AED | 330.0000 |
| company_b | SAR | 330.0000 |

Each company has sales of 350 excluding tax and returns of 20.
A void invoice of 1,000 is excluded.
Company IDs, invoice numbers and product codes overlap deliberately to exercise isolation.
Do not add AED and SAR together as a single monetary total.

### Open Metabase

1. Open <http://localhost:3000> and create the initial administrator account.
2. Skip adding a database during onboarding if available; the provisioner adds it later.
3. In the administration settings, create an API key with administrator permissions.
4. Set `METABASE_API_KEY` in `.env` to the generated key.
5. Run `make dashboard`.
6. Open the dashboard URL printed by the command.

The provisioner creates/reuses a database connection, collection, dashboard and six table-based questions.
It also executes the questions and fails if they do not return successfully.
It manages the contents of its named dashboard; put custom questions in a different dashboard.
Use Metabase's editor to create additional charts or filtered questions from the marts.
Automated chart styling and dashboard filter wiring are not included in this first version.

### Manual database connection alternative

If you prefer to add the database in the browser:

| Setting | Value |
|---|---|
| Database type | PostgreSQL |
| Host | `warehouse` |
| Port | `5432` |
| Database | `analytics` |
| Username | `analytics_reader` |
| Password | `BI_PASSWORD` from `.env` |
| Schema | `marts` |

The BI role has access to reporting views, not raw data or database write privileges.
The configured password is established when the PostgreSQL volume is first initialized.
Editing `.env` later does not rotate existing database passwords.

## 3. Connect local or remote company databases

```sh
cp config/companies.example.json config/companies.local.json
```

Edit `config/companies.local.json` for each company:

```json
[
  {
    "company_id": "north_company",
    "name": "North Company",
    "host": "host.docker.internal",
    "port": 3306,
    "database": "north_business_db",
    "user": "warehouse_reader",
    "password_env": "NORTH_SOURCE_PASSWORD",
    "timezone": "+00:00"
  },
  {
    "company_id": "south_company",
    "name": "South Company",
    "host": "mysql.internal.example",
    "port": 3306,
    "database": "south_business_db",
    "user": "warehouse_reader",
    "password_env": "SOUTH_SOURCE_PASSWORD",
    "timezone": "+00:00"
  }
]
```

Add `NORTH_SOURCE_PASSWORD` and `SOUTH_SOURCE_PASSWORD` to your local `.env`.
The host and database names above are examples; replace them with your actual values.
For MySQL on your computer use `host.docker.internal`, not `localhost`, because the pipeline runs inside a container.
For remote MySQL use a reachable hostname and read-only credentials.
MySQL must permit connections from the pipeline's network.

Use the same source timezone on every run.
For legacy `DATETIME` modification columns, set it to the timezone used when the application writes those columns; do not guess.
Validate timestamp conventions before relying on incremental loads.

For TLS, optionally set `ssl_ca` to a CA file path inside the container and mount that certificate through a local Compose override.
The connection verifies the certificate and hostname when a CA is supplied.

The required table/column contract is defined in `ingestion/pipeline.py` under `TABLES`.
Each source database must contain the sales, customer, product, route and hierarchy tables listed there, using transactional InnoDB tables.
Schema validation runs before publishing any company data.
This loader does not automatically adapt arbitrary ERP schemas.

Start infrastructure, build and load:

```sh
make up
make build
make load
```

Load only one company when needed:

```sh
docker compose run --rm pipeline python -m ingestion.pipeline \
  --config config/companies.local.json --company north_company --mode full
make model
```

Keep `company_id` stable when moving from a dump to a direct connection.
Different companies must have different IDs even if invoice numbers or customer codes match.
Removing a company from configuration does not delete its existing warehouse history.
Use a separate warehouse environment for real data if you want to keep the demo independent.

## 4. SQL dump workflow

A dump is restored into the isolated `source` service, not into a production database.
The same loader then reads it like any other MySQL database.

```sh
docker compose --profile dump up -d --wait source
```

For a trusted, single-database dump containing table definitions/data without `CREATE DATABASE` or `USE` directives:

```sh
docker compose exec -T source sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root -e "CREATE DATABASE restored_north"'

docker compose exec -T source sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root restored_north' < dumps/north.sql
```

If the dump contains `CREATE DATABASE` / `USE`, inspect those statements and restore into its declared database instead.
Dump SQL is executable SQL; run only trusted dumps in this isolated instance.
Legacy routines, definers or collations can require a matching MySQL version or a compatible export.
Compressed dumps must be decompressed before these commands.

Create a dedicated read-only user for the restored database using the MySQL client:

```sh
docker compose exec source sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root'
```

Then execute, replacing the example password:

```sql
CREATE USER 'north_reader'@'%' IDENTIFIED BY 'replace-with-a-local-secret';
GRANT SELECT ON restored_north.* TO 'north_reader'@'%';
```

Configure this company with host `source`, port `3306`, database `restored_north`, and user `north_reader`.
Store its password in `.env` and reference the variable using `password_env`.
Run `make load`.
When replacing a dump, restore into a fresh database, update the connection while retaining the same company ID, and run a full load.
A static dump cannot provide ongoing updates until a newer dump is restored.

## 5. Refresh and reconcile

```sh
make refresh
```

Incremental mode rereads transaction records modified within a 24-hour overlap and upserts by company/table/source ID.
Master tables are refreshed fully each time.
Missing `modified_at` support causes a full refresh of that table rather than guessing a watermark.
Rows with null modification timestamps are reread every time.
Run `make load` periodically for full reconciliation of hard deletions and changes missed by source timestamps.
Long-running commits or backdated timestamps outside the overlap require a full load; CDC is a future extension.

A cron or another scheduler can invoke `make refresh` from this directory.
Per-company advisory locks prevent simultaneous loads for the same company.
A failed company keeps its previous raw data, other companies are attempted, and the overall command exits unsuccessfully.
`raw.load_runs` records failure types without storing source values or passwords in error messages.

The models are views, so successfully committed raw data is immediately reflected after initial model creation.
dbt tests detect invalid records but do not provide a separate quality-gated publication schema.
This first version is intended for development and controlled administrator use; add staged promotion before a production reporting SLA.

## 6. Tests

Unit tests:

```sh
make test
```

End-to-end tests against the synthetic demo only:

```sh
make build
make integration
```

The integration test runs real loaders and dbt builds, checks both company totals, reruns loads, edits an old line, cancels an invoice, simulates a failed connection, injects a mid-load failure to prove rollback, and reconciles a hard deletion.
It also proves the BI role can read marts while raw reads and writes are rejected.
It restores the synthetic data afterward.
Never point that integration test at real business databases.

Development checks:

```sh
uv run --python 3.12 --extra dev ruff check .
PGPASSWORD=validation-only DBT_PROFILES_DIR=warehouse \
  uv run --python 3.12 dbt parse --project-dir warehouse --no-partial-parse
```

`dbt parse` checks project parsing without a database; only `dbt build` executes SQL and data checks.

If Docker is unavailable but PostgreSQL and MySQL binaries are installed, an isolated native test runner is also included:

```sh
uv run --python 3.12 --extra dev python scripts/verify_local.py \
  --postgres-bin /path/to/postgresql/bin --mysql-bin /path/to/mysql/bin
```

Replace the paths with your installation directories.
The runner creates temporary databases on dynamically selected localhost ports, runs the integration test, then stops the servers and removes its temporary data.
It does not connect to existing databases and does not test Metabase.
`uv.lock` records dependency resolution; `requirements.txt` is its generated container-install export.
After intentional dependency changes, regenerate it with:

```sh
uv lock
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt
```

## 7. Learn by following the data

1. Read `config/companies.example.json` to understand company connections.
2. Read `ingestion/pipeline.py` to understand copying, checkpoints and transactions.
3. Query `raw.records`; source decimals are preserved as strings inside JSON to avoid floating-point loss.
4. Open `warehouse/models/staging` to see JSON converted into typed SQL columns.
5. Open `warehouse/models/core` to understand dimensions and the sales-line grain.
6. Open `warehouse/models/marts` to see dashboard-facing summaries.
7. Open `warehouse/tests` to see correctness checks.
8. Change a synthetic source record, refresh, and inspect the dashboard again.

## Access and production boundaries

The generated dashboard and its read-only database connection can read all company marts.
They are for authorized consolidated administrators.
A dashboard filter is not a security boundary.
Company-specific manager access, row-level security and separate BI credentials are not implemented in this first slice.
Do not share the consolidated connection with users who should only access one company.

Services bind to localhost and credentials belong in `.env`, which is excluded from version control and Docker builds.
The demo reader password is deliberately public synthetic-demo configuration.
Before hosting beyond your computer, configure access isolation, TLS, backups, dependency pinning and monitoring for that environment.

## Troubleshooting and stopping

```sh
docker compose logs warehouse
docker compose logs metabase
docker compose logs source
make down
```

Stopping services preserves volumes and warehouse data.
No convenience command deletes database volumes.
Schema or credential initialization changes apply automatically only to a new PostgreSQL volume; use explicit migrations/password rotation for an existing instance.
# data-warehousing
