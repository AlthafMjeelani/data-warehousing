# KAKU last-30-days import

## Source and scope

Source dump: `/Users/texol/dump-tenant_kaku_1-202610271853.sql`.
The dump identifies the original database as `tenant_kaku_1` and the source server as MySQL 9.6.0.
The original dump was not modified.

SHA256:

```text
f46f1bc23c41ca43923c54171d1515d226f9e895314ff0706a5c943a8aad2f7b
```

Company ID: `kaku`.
Warehouse: PostgreSQL `analytics`.
Requested window: **2026-09-28 through 2026-10-27, inclusive**, interpreted as the last 30 days of the supplied snapshot.
Actual invoice dates in this window: **2026-10-07 through 2026-10-26**.

## Restoration

The initial whole-database restoration timed out before the sales tables were restored.
Its partial database `tenant_kaku_1` is not used by the warehouse.

The successful restore created a separate database, `tenant_kaku_sales`, in `kaku-source` (MySQL 9.6).
`scripts/restore_sales_dump.py` streamed only CREATE TABLE and INSERT statements for these 11 allowlisted tables:

```text
area, branches, customer, p_category, p_subcategory, product,
region, route, sales_details, sales_summary, users
```

Replication metadata, application triggers, routines, views and unrelated tables were not replayed.
This is a selective analytics-source restore, not a complete application backup restoration.
The helper understands the trusted mysqldump statement layout used by this file, not arbitrary SQL exports.
It refuses to replace an existing target database.

Source restoration contains full history for those selected tables.
Only the requested transaction date window is extracted into the warehouse; master tables are loaded fully.

For a fresh target, the restoration command is:

```sh
docker compose --profile kaku up -d --wait kaku-source
uv run --python 3.12 python scripts/restore_sales_dump.py \
  /Users/texol/dump-tenant_kaku_1-202610271853.sql --database tenant_kaku_sales
```

The database already exists in the current environment, so do not rerun that creation command against it.
For another restore, choose a new target name and update the local company configuration accordingly.

## Extraction credentials

The source user `kaku_reader` has SELECT access only to `tenant_kaku_sales`.
Its password comes from `KAKU_SOURCE_PASSWORD`; the local Compose default is `kaku-local-reader`.
Connection configuration is in `config/companies.kaku.json`.

On a fresh restore, create the reader from the pipeline container:

```sh
docker compose run --rm pipeline python -c 'import os,pymysql; db=pymysql.connect(host="kaku-source",user="root",password=os.environ["MYSQL_ROOT_PASSWORD"],autocommit=True); c=db.cursor(); c.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",("kaku_reader","%",os.environ["KAKU_SOURCE_PASSWORD"])); c.execute("GRANT SELECT ON tenant_kaku_sales.* TO %s@%s",("kaku_reader","%")); db.close()'
```

## Load or repeat the snapshot

```sh
make build
make kaku-load
```

This runs a full company load with the fixed requested dates, followed by dbt build/tests.
It does not expand KAKU's transaction history beyond this window.
Run model rebuilds outside active dashboard usage: rebuilding upstream PostgreSQL views can temporarily remove dependent marts until dbt recreates them.
If a query reports a missing mart during a rebuild, wait for a successful build and rerun the query.
To intentionally change the window for a suitable source snapshot:

```sh
make kaku-load KAKU_START_DATE=2026-10-01 KAKU_END_DATE=2026-10-27
```

Running without a date window would replace KAKU's snapshot with all available source history.
Do not use the generic unrestricted load command unless that is intentional.
Incremental mode is blocked while KAKU's current coverage is date-limited.

## Reconciled results

| Currency | Invoices | Lines | Sales excluding tax | Returns excluding tax | Net sales excluding tax |
|---|---:|---:|---:|---:|---:|
| SAR | 52 | 95 | 4,170.8300 | 2,335.6800 | 1,835.1500 |
| INR | 1 | 1 | 500.0000 | 0.0000 | 500.0000 |

Total invoice count: 53.
Total line count: 96, comprising 79 sales, 16 goods-return and one expiry line.
No invoices in the loaded window are marked void.
Do not add the SAR and INR amounts into one monetary total.

The load contains 5,591 raw records including all master records needed for analysis.
The source MySQL aggregation and warehouse fact aggregation matched separately for each currency.
Repeating the same window load retained exactly 53 invoices and 96 fact lines, with zero out-of-window records.
These are line-derived metrics under `METRICS.md`, not a claim that every legacy application report uses identical definitions.

## Open the dashboard

KAKU dashboard: <http://localhost:3000/dashboard/3>.
Use the existing local Metabase administrator login.
The dashboard has six saved questions, each explicitly scoped to `company_id = 'kaku'`.
The refresh-status question shows the requested coverage dates.

To recreate/update it, set a Metabase administrator API key in local `.env` and run:

```sh
make kaku-dashboard
```

The returned dashboard ID may differ in another environment.
Do not share the administrator connection as a substitute for tenant-specific permissions.

## Connect DBeaver

| Setting | Reporting access | All-layer inspection |
|---|---|---|
| Driver | PostgreSQL | PostgreSQL |
| Host | `localhost` | `localhost` |
| Port | `55432` | `55432` |
| Database | `analytics` | `analytics` |
| Username | `analytics_reader` | `warehouse` |
| Password source | `BI_PASSWORD` in `.env` | `POSTGRES_PASSWORD` in `.env` |
| Schema | `marts` | `raw`, `staging`, `core`, `marts` |

Refresh the connection navigator after loading.
`permission denied for schema raw` is expected when using `analytics_reader`.
The inspection account has write privileges; use the reporting account for ordinary analysis.

```sql
SELECT
    currency_code,
    SUM(sales_excluding_tax) AS sales,
    SUM(returns_excluding_tax) AS returns,
    SUM(net_sales_excluding_tax) AS net_sales
FROM marts.mart_daily_sales
WHERE company_id = 'kaku'
GROUP BY currency_code
ORDER BY currency_code;

SELECT *
FROM marts.mart_sales_detail
WHERE company_id = 'kaku'
ORDER BY sales_date, invoice_no, sales_line_id;

SELECT *
FROM marts.mart_load_status
WHERE company_id = 'kaku';
```
