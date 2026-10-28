"""All tables for a company are published in one PostgreSQL transaction."""

import argparse
import datetime as dt
import decimal
import json
import logging
import os
import sys
import uuid

import psycopg
import pymysql
from psycopg.types.json import Jsonb

from ingestion.config import load_companies

LOG = logging.getLogger(__name__)

# Explicit allowlists avoid copying customer addresses, contact details or user credentials.
# Fields after the required columns are optional across source schema versions.
TABLES = {
    "sales_summary": (
        "id invoice_no sales_date customer_code route_code salesman_code currency_code",
        "customer_name route_name salesman_name void modified_at created_at "
        "net_amount total_taxable_amount tax_amount total_discount currency_exchange_rate",
    ),
    "sales_details": (
        "id detail_code sales_code product_code sales_type net_amount total_taxable_amount "
        "tax_amount multipack_quantity multiplier",
        "product_name cost_price discount_amount modified_at created_at base_multipack_code",
    ),
    "customer": ("id code name", "active deleted_at modified_at"),
    "product": ("id code name", "category subcategory active deleted_at modified_at"),
    "route": ("id code name", "branch active deleted_at modified_at"),
    "branches": ("id code name", "area deleted_at"),
    "area": ("id code name", "region deleted_at"),
    "region": ("id code name", "deleted_at"),
    "p_category": ("id code name", "deleted_at"),
    "p_subcategory": ("id code name", "deleted_at"),
    "users": ("id code name", "deleted_at active"),
}
TRANSACTIONS = {"sales_summary", "sales_details"}

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.companies (
  company_id text PRIMARY KEY, name text NOT NULL,
  last_success_at timestamptz, source_database text NOT NULL
);
ALTER TABLE raw.companies ADD COLUMN IF NOT EXISTS coverage_start date;
ALTER TABLE raw.companies ADD COLUMN IF NOT EXISTS coverage_end date;
CREATE TABLE IF NOT EXISTS raw.records (
  company_id text NOT NULL, table_name text NOT NULL, source_id text NOT NULL,
  payload jsonb NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, table_name, source_id)
);
CREATE TABLE IF NOT EXISTS raw.checkpoints (
  company_id text NOT NULL, table_name text NOT NULL, watermark timestamp NOT NULL,
  PRIMARY KEY (company_id, table_name)
);
CREATE TABLE IF NOT EXISTS raw.load_runs (
  run_id uuid PRIMARY KEY, company_id text NOT NULL, mode text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
  status text NOT NULL, rows_loaded bigint, error_type text
);
"""


def json_default(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    raise TypeError(f"Unsupported source value type: {type(value).__name__}")


def selected_columns(table, available):
    required, optional = TABLES[table]
    missing = set(required.split()) - set(available)
    if missing:
        raise ValueError(f"{table}: missing required columns {sorted(missing)}")
    return required.split() + [c for c in optional.split() if c in available]


def date_filter(table, start_date, end_date):
    """Use the invoice business date for both headers and details; end is inclusive."""
    if start_date is None or table not in TRANSACTIONS:
        return "", ()
    end_exclusive = end_date + dt.timedelta(days=1)
    if table == "sales_summary":
        return " WHERE sales_date >= %s AND sales_date < %s", (start_date, end_exclusive)
    return (
        " WHERE EXISTS (SELECT 1 FROM sales_summary h WHERE "
        "h.invoice_no = sales_details.sales_code AND h.sales_date >= %s AND h.sales_date < %s)",
        (start_date, end_exclusive),
    )


def load_company(pg, company, mode, start_date=None, end_date=None):
    if (start_date is None) != (end_date is None):
        raise ValueError("Both start_date and end_date are required")
    if start_date and (start_date > end_date or mode != "full"):
        raise ValueError("Date-window loads require full mode and start_date <= end_date")
    company_id = company["company_id"]
    run_id = uuid.uuid4()
    with pg.transaction():
        # A session lock prevents overlapping scheduled runs for this company.
        locked = pg.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (company_id,)
        ).fetchone()[0]
        if not locked:
            raise RuntimeError(f"A load is already running for {company_id}")
        pg.execute(
            "INSERT INTO raw.load_runs(run_id,company_id,mode,status) VALUES (%s,%s,%s,'running')",
            (run_id, company_id, mode),
        )
    mysql = None
    rows_loaded = 0
    try:
        ssl = None
        if company.get("ssl_ca"):
            ssl = {"ca": company["ssl_ca"], "check_hostname": True}
        mysql = pymysql.connect(
            host=company["host"], port=company.get("port", 3306),
            user=company["user"], password=os.environ[company["password_env"]],
            database=company["database"], charset="utf8mb4", ssl=ssl,
            connect_timeout=15, read_timeout=300, write_timeout=60, autocommit=False,
        )
        with mysql.cursor() as cursor:
            cursor.execute("SET time_zone = %s", (company.get("timezone", "+00:00"),))
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            cursor.execute("SELECT CURRENT_TIMESTAMP(6)")
            cutoff = cursor.fetchone()[0]
            # Validate every table before changing raw data.
            columns = {}
            for table in TABLES:
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                columns[table] = selected_columns(table, [row[0] for row in cursor.fetchall()])
        with pg.transaction():
            previous = pg.execute(
                "SELECT coverage_start FROM raw.companies WHERE company_id=%s", (company_id,)
            ).fetchone()
            if mode == "incremental" and previous and previous[0] is not None:
                raise ValueError("A date-window company must use a full load with explicit dates")
            pg.execute(
                "INSERT INTO raw.companies(company_id,name,source_database,coverage_start,coverage_end) "
                "VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT(company_id) DO UPDATE SET name=excluded.name, "
                "source_database=excluded.source_database,coverage_start=excluded.coverage_start, "
                "coverage_end=excluded.coverage_end",
                (company_id, company["name"], company["database"], start_date, end_date),
            )
            for table, selected in columns.items():
                checkpoint = pg.execute(
                    "SELECT watermark FROM raw.checkpoints WHERE company_id=%s AND table_name=%s",
                    (company_id, table),
                ).fetchone()
                incremental = (
                    mode == "incremental" and table in TRANSACTIONS
                    and "modified_at" in selected and checkpoint is not None
                )
                query = "SELECT " + ",".join(f"`{c}`" for c in selected) + f" FROM `{table}`"
                date_clause, params = date_filter(table, start_date, end_date)
                query += date_clause
                if incremental:
                    # An inclusive overlap handles equal timestamps and ordinary late commits.
                    query += " WHERE modified_at >= %s OR modified_at IS NULL"
                    params = (checkpoint[0] - dt.timedelta(hours=24),)
                else:
                    pg.execute(
                        "DELETE FROM raw.records WHERE company_id=%s AND table_name=%s",
                        (company_id, table),
                    )
                with mysql.cursor(pymysql.cursors.SSDictCursor) as cursor:
                    cursor.execute(query, params)
                    while batch := cursor.fetchmany(1000):
                        records = [
                            (company_id, table, str(row["id"]),
                             Jsonb(row, dumps=lambda v: json.dumps(v, default=json_default)))
                            for row in batch
                        ]
                        with pg.cursor() as writer:
                            writer.executemany(
                                "INSERT INTO raw.records(company_id,table_name,source_id,payload) "
                                "VALUES (%s,%s,%s,%s) ON CONFLICT(company_id,table_name,source_id) "
                                "DO UPDATE SET payload=excluded.payload,loaded_at=now()", records,
                            )
                        rows_loaded += len(batch)
                pg.execute(
                    "INSERT INTO raw.checkpoints VALUES (%s,%s,%s) "
                    "ON CONFLICT(company_id,table_name) DO UPDATE SET watermark=excluded.watermark",
                    (company_id, table, cutoff),
                )
            pg.execute(
                "UPDATE raw.companies SET last_success_at=now() WHERE company_id=%s", (company_id,)
            )
            pg.execute(
                "UPDATE raw.load_runs SET status='success',finished_at=now(),rows_loaded=%s "
                "WHERE run_id=%s", (rows_loaded, run_id),
            )
        LOG.info("company=%s status=success rows=%s", company_id, rows_loaded)
    except Exception as exc:
        with pg.transaction():
            pg.execute(
                "UPDATE raw.load_runs SET status='failed',finished_at=now(),error_type=%s "
                "WHERE run_id=%s", (type(exc).__name__, run_id),
            )
        # Do not log exception messages: drivers can include connection or source data.
        LOG.error("company=%s status=failed error_type=%s", company_id, type(exc).__name__)
        raise
    finally:
        if mysql:
            mysql.close()
        with pg.transaction():
            pg.execute("SELECT pg_advisory_unlock(hashtext(%s))", (company_id,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/companies.example.json")
    parser.add_argument("--company", help="Load only this stable company_id")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--start-date", type=dt.date.fromisoformat)
    parser.add_argument("--end-date", type=dt.date.fromisoformat, help="Inclusive business date")
    args = parser.parse_args()
    if bool(args.start_date) != bool(args.end_date):
        parser.error("Supply both --start-date and --end-date")
    if args.start_date and (args.start_date > args.end_date or args.mode != "full"):
        parser.error("Date-window loads require full mode and start date <= end date")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    companies = load_companies(args.config)
    if args.company:
        companies = [c for c in companies if c["company_id"] == args.company]
        if not companies:
            parser.error("Unknown company_id")
    failed = False
    with psycopg.connect(autocommit=True) as pg:
        pg.execute(DDL)
        for company in companies:
            try:
                load_company(pg, company, args.mode, args.start_date, args.end_date)
            except Exception:
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
