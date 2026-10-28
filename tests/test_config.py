import datetime as dt
import decimal
import json

import pytest

from ingestion.config import load_companies
from ingestion.pipeline import json_default, selected_columns


def config_file(tmp_path, companies):
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(companies))
    return str(path)


def company(identity="alpha"):
    return {
        "company_id": identity, "name": "Alpha", "host": "localhost",
        "database": "alpha_db", "user": "reader", "password_env": "TEST_SOURCE_PASSWORD",
    }


def test_multiple_sources_keep_stable_company_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_SOURCE_PASSWORD", "secret")
    result = load_companies(config_file(tmp_path, [company(), company("beta")]))
    assert [c["company_id"] for c in result] == ["alpha", "beta"]


def test_duplicate_company_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_SOURCE_PASSWORD", "secret")
    with pytest.raises(ValueError, match="Duplicate"):
        load_companies(config_file(tmp_path, [company(), company()]))


def test_missing_secret_fails_before_connections(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_SOURCE_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="Missing password"):
        load_companies(config_file(tmp_path, [company()]))


def test_source_allowlist_excludes_sensitive_columns():
    assert selected_columns("users", ["id", "code", "name", "password", "email"]) == [
        "id", "code", "name",
    ]


def test_incompatible_schema_rejected():
    with pytest.raises(ValueError, match="missing required columns"):
        selected_columns("sales_details", ["id", "sales_code"])


def test_financial_precision_and_timestamps_preserved():
    assert json_default(decimal.Decimal("123456789.1234")) == "123456789.1234"
    assert json_default(dt.datetime(2026, 1, 1, 1, 2, 3, 456789)) == "2026-01-01T01:02:03.456789"
