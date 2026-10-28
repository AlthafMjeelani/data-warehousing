"""Real MySQL + PostgreSQL tests. Run only against the supplied synthetic demo sources."""

import os
import subprocess
from pathlib import Path

import psycopg
import pymysql
import pytest

from ingestion.config import load_companies
from ingestion.pipeline import DDL, load_company

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1", reason="Requires isolated demo databases"
)
ROOT = Path(__file__).resolve().parents[1]


def transform():
    subprocess.run(
        ["dbt", "build", "--project-dir", str(ROOT / "warehouse"),
         "--profiles-dir", str(ROOT / "warehouse")], check=True,
    )


def test_company_isolation_updates_cancellation_deletion_and_failure():
    companies = load_companies(os.environ.get(
        "TEST_COMPANIES_CONFIG", str(ROOT / "config/companies.example.json")
    ))
    a = companies[0]
    assert a["database"] == "company_a"
    with psycopg.connect(autocommit=True) as pg:
        pg.execute(DDL)
        for c in companies:
            load_company(pg, c, "full")
        transform()
        initial = pg.execute(
            "select company_id,currency_code,sum(net_sales_excluding_tax) "
            "from marts.mart_daily_sales group by 1,2 order by 1"
        ).fetchall()
        assert [(r[0], r[1], float(r[2])) for r in initial] == [
            ("company_a", "AED", 330), ("company_b", "SAR", 330)
        ]
        with psycopg.connect(
            user="analytics_reader", password=os.environ["BI_PASSWORD"], autocommit=True
        ) as reader:
            assert reader.execute("select count(*) from marts.mart_daily_sales").fetchone()[0] == 4
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute("select * from raw.records")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute("delete from raw.records where false")
            assert reader.execute(
                "select has_table_privilege(current_user, 'marts.mart_daily_sales', 'DELETE')"
            ).fetchone()[0] is False
            assert reader.execute("select count(*) from marts.mart_daily_sales").fetchone()[0] == 4
        load_company(pg, a, "incremental")
        transform()
        assert pg.execute("select count(*) from core.fact_sales_line").fetchone()[0] == 8
        with pymysql.connect(
            host=a["host"], port=a.get("port", 3306),
            user="root", password=os.environ.get("MYSQL_ROOT_PASSWORD", ""),
            database="company_a", autocommit=True,
        ) as mysql:
            with mysql.cursor() as cursor:
                try:
                    cursor.execute("UPDATE sales_details SET total_taxable_amount=120 WHERE id=1")
                    cursor.execute("UPDATE sales_summary SET void=1 WHERE id=2")
                    load_company(pg, a, "incremental")
                    transform()
                    assert float(pg.execute(
                        "select sum(net_sales_excluding_tax) from marts.mart_daily_sales "
                        "where company_id='company_a'"
                    ).fetchone()[0]) == 170
                    assert float(pg.execute(
                        "select sum(net_sales_excluding_tax) from marts.mart_daily_sales "
                        "where company_id='company_b'"
                    ).fetchone()[0]) == 330
                    before = pg.execute(
                        "select count(*) from raw.records where company_id='company_a'"
                    ).fetchone()[0]
                    broken = dict(a, database="missing_demo_database")
                    with pytest.raises(pymysql.MySQLError):
                        load_company(pg, broken, "full")
                    assert pg.execute(
                        "select count(*) from raw.records where company_id='company_a'"
                    ).fetchone()[0] == before
                    # Fail after sales tables have already been written, proving transaction rollback.
                    pg.execute("""
                        CREATE FUNCTION raw.reject_demo_product() RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                          IF NEW.company_id='company_a' AND NEW.table_name='product' THEN
                            RAISE EXCEPTION 'controlled integration failure';
                          END IF;
                          RETURN NEW;
                        END $$;
                        CREATE TRIGGER reject_demo_product BEFORE INSERT ON raw.records
                        FOR EACH ROW EXECUTE FUNCTION raw.reject_demo_product();
                    """)
                    try:
                        cursor.execute(
                            "UPDATE sales_details SET total_taxable_amount=140 WHERE id=1"
                        )
                        with pytest.raises(psycopg.errors.RaiseException):
                            load_company(pg, a, "full")
                        preserved = pg.execute(
                            "select payload->>'total_taxable_amount' from raw.records "
                            "where company_id='company_a' and table_name='sales_details' "
                            "and source_id='1'"
                        ).fetchone()[0]
                        assert float(preserved) == 120
                    finally:
                        pg.execute("DROP TRIGGER reject_demo_product ON raw.records")
                        pg.execute("DROP FUNCTION raw.reject_demo_product()")
                        cursor.execute(
                            "UPDATE sales_details SET total_taxable_amount=120 WHERE id=1"
                        )
                    # Hard deletions are reconciled by full loads.
                    cursor.execute("DELETE FROM sales_details WHERE id=2")
                    load_company(pg, a, "full")
                    transform()
                    assert float(pg.execute(
                        "select sum(net_sales_excluding_tax) from marts.mart_daily_sales "
                        "where company_id='company_a'"
                    ).fetchone()[0]) == 120
                finally:
                    cursor.execute(
                        "INSERT INTO sales_details(id,detail_code,sales_code,product_code,"
                        "product_name,sales_type,net_amount,total_taxable_amount,tax_amount,"
                        "multipack_quantity,multiplier,cost_price,discount_amount,base_multipack_code) "
                        "VALUES (2,'L2','INV001','P2','Apple Juice','sales',52.5,50,2.5,5,1,6,0,'EA') "
                        "ON DUPLICATE KEY UPDATE total_taxable_amount=50"
                    )
                    cursor.execute("UPDATE sales_details SET total_taxable_amount=100 WHERE id=1")
                    cursor.execute("UPDATE sales_summary SET void=0 WHERE id=2")
                    load_company(pg, a, "full")
                    transform()


def test_date_window_load_is_bounded_repeatable_and_blocks_incremental():
    companies = load_companies(os.environ.get(
        "TEST_COMPANIES_CONFIG", str(ROOT / "config/companies.example.json")
    ))
    a = companies[0]
    assert a["database"] == "company_a"
    with pymysql.connect(
        host=a["host"], port=a.get("port", 3306), user=a["user"],
        password=os.environ[a["password_env"]], database=a["database"],
    ) as mysql:
        with mysql.cursor() as cursor:
            cursor.execute("SELECT CURRENT_DATE - INTERVAL 1 DAY, CURRENT_DATE")
            start, end = cursor.fetchone()
    with psycopg.connect(autocommit=True) as pg:
        pg.execute(DDL)
        try:
            for _ in range(2):
                load_company(pg, a, "full", start, end)
                transform()
                assert pg.execute(
                    "select count(*) from raw.records "
                    "where company_id='company_a' and table_name='sales_summary'"
                ).fetchone()[0] == 2
                assert pg.execute(
                    "select count(*) from core.fact_sales_line where company_id='company_a'"
                ).fetchone()[0] == 2
                assert pg.execute(
                    "select coverage_start,coverage_end from raw.companies "
                    "where company_id='company_a'"
                ).fetchone() == (start, end)
            with pytest.raises(ValueError, match="explicit dates"):
                load_company(pg, a, "incremental")
        finally:
            load_company(pg, a, "full")
            transform()
