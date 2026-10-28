# Warehouse features, tools and techniques

## Current architecture

The running implementation uses PostgreSQL as the analytical warehouse.
ClickHouse was discussed as a future production option but is not used by this implementation.

```text
Live company MySQL databases ───────────────────────┐
                                                   │
Trusted SQL dump → isolated MySQL source restore ────┤
                                                   ▼
                                  Python read-only extraction
                                                   ▼
                                     PostgreSQL analytics
                                     raw → staging → core → marts
                                                   ▼
                                      Metabase / DBeaver
```

## Tools and responsibilities

| Tool | Responsibility | Implementation |
|---|---|---|
| Docker Compose | Local databases, network and services | `compose.yaml` |
| MySQL | Original operational data or isolated dump restoration | `source` and `kaku-source` services |
| Python / PyMySQL | Read source data in batches | `ingestion/pipeline.py` |
| Psycopg | Write PostgreSQL within transactions | `ingestion/pipeline.py` |
| PostgreSQL | Warehouse storage and analytical SQL | `raw`, `staging`, `core`, `marts` |
| dbt Core | SQL dependencies, models and data checks | `warehouse/` |
| Metabase | Saved questions and dashboards | `dashboards/provision.py` |
| DBeaver | Database exploration and SQL queries | Connection settings in `KAKU_IMPORT.md` |
| pytest / Ruff | Automated behavior tests and code checks | `tests/`, `pyproject.toml` |

Metabase has its own PostgreSQL application database named `metabase` for accounts and dashboard configuration.
Business reporting data lives in the separate `analytics` database.

## Implemented features

- Multiple company sources with stable company identities.
- Local and remote MySQL source configuration.
- Isolated restoration of selected tables from the supplied mysqldump format.
- Full loads and timestamp-based incremental loads for unrestricted companies.
- Explicit business-date windows for full transaction loads.
- Per-company checkpoints, load audit records and advisory locks.
- Atomic per-company publication into raw storage.
- Column allowlists excluding user credentials and customer contact fields from the warehouse.
- Sales, customer, product, route, employee and calendar models.
- Company/currency-separated reporting datasets.
- Separate company-scoped dashboards.

## Warehouse layers

### Raw

`raw.records` stores selected source fields as JSONB, keyed by company, table and source ID.
Financial decimals are serialized without floating-point conversion.
`raw.companies` stores source identity, last successful load and optional inclusive date coverage.
`raw.checkpoints` stores source modification-time watermarks.
`raw.load_runs` records success/failure, record counts and timestamps.

### Staging

`stg_sales_headers` and `stg_sales_lines` convert JSON values into typed SQL columns.
Invoice lines join their headers using `sales_code = invoice_no` within the same company.

### Core

`fact_sales_line` has one record per company/source sales line.
`dim_company`, `dim_customer`, `dim_product`, `dim_route`, `dim_employee` and `dim_date` supply descriptive data.
Route hierarchy includes branch, area and region.
Dimensions currently represent source master state, not historical slowly changing versions.

### Marts

`mart_sales_detail` combines facts with descriptive dimensions.
Daily, product, customer and route marts aggregate this data.
`mart_load_status` exposes loading status and date coverage.
The dbt models are views rather than stored analytical tables in this first version.

## Loading techniques

### Consistent extraction

Source reads use a read-only repeatable-read transaction with a consistent snapshot.
This requires transactional source tables for snapshot guarantees.
Rows are streamed in batches of 1,000.

### Identity and idempotency

The raw primary key is `(company_id, table_name, source_id)`.
Upserts replace the payload rather than duplicating existing records.
Every cross-table analytical join includes company identity.

### Atomic loads

All raw-table replacements/upserts, coverage updates and checkpoints for one company commit together.
A failure rolls back that company's data and records a failed run separately.
Other configured companies are still attempted.
Per-company advisory locks prevent simultaneous loads of the same company.

### Full and incremental modes

Full mode replaces the selected company's copies of the configured source tables.
Incremental mode rereads sales records modified within a 24-hour overlap and fully refreshes master data.
Hard deletions and backdated changes outside the overlap require periodic full reconciliation.
This is not CDC and does not provide an immutable audit archive.

### Date-window snapshots

`--start-date` and `--end-date` are inclusive business dates and must be supplied together with full mode.
Headers are selected by `sales_date`; lines are selected through their matching headers in that window.
Master data is loaded in full so referenced descriptions and hierarchies remain available.
A later date-window load replaces that company's prior raw transaction window.
An unrestricted incremental run is rejected for a company whose current coverage is date-limited.
To expand coverage, explicitly run another full load with the desired dates or no window.

## Reporting rules

Sales exclude tax and use the absolute taxable line amount for `sales` records.
Returns comprise `gr`, `expiry` and `damage`; net sales subtract these once.
Void invoices are excluded.
Currencies are never automatically combined or converted.
See `METRICS.md` for the complete metric contract, aggregation cautions and cost limitations.

## Checks and access

dbt checks required values, known transaction types, duplicate keys, orphan lines, join fanout and source-to-mart consistency.
Real-source reconciliation must still be performed independently by currency and period.
Models are views, so committed raw changes become visible without a separate quality-gated publication layer.

`analytics_reader` has SELECT access to marts only.
The `warehouse` account can inspect and modify all layers.
A company filter on a dashboard is not tenant authorization: current company dashboards are for trusted administrators.

## Scope still to implement

Collections, receivables, targets, inventory, deliveries and visits need additional facts and reconciliation rules.
Historical dimensions, automatic scheduling, tenant-restricted manager roles and production publication gates are not yet implemented.
ClickHouse migration, Cloud services and production CDC remain separate future work.
