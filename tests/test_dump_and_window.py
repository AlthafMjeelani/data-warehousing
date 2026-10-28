import datetime as dt
from io import StringIO

from ingestion.pipeline import date_filter
from scripts.restore_sales_dump import selected_statements


def test_dump_selection_excludes_triggers_views_replication_and_other_tables():
    dump = StringIO(
        "SET @@GLOBAL.GTID_PURGED='do not restore';\n"
        "CREATE TABLE `sales_summary` (\n`id` int\n) ENGINE=InnoDB;\n"
        "INSERT INTO `sales_summary` VALUES (1);\n"
        "CREATE TABLE `users_secrets` (`password` text);\n"
        "INSERT INTO `users_secrets` VALUES ('private');\n"
        "/*!50003 CREATE*/ TRIGGER ignored BEFORE INSERT ON sales_summary FOR EACH ROW SET @x=1;\n"
        "CREATE VIEW ignored AS SELECT * FROM sales_summary;\n"
    )
    result = list(selected_statements(dump, {"sales_summary"}))
    assert len(result) == 2
    assert result[0].startswith("CREATE TABLE `sales_summary`")
    assert result[1] == "INSERT INTO `sales_summary` VALUES (1);\n"


def test_header_and_line_windows_share_inclusive_business_date_bounds():
    start, end = dt.date(2026, 9, 28), dt.date(2026, 10, 27)
    header_sql, header_params = date_filter("sales_summary", start, end)
    line_sql, line_params = date_filter("sales_details", start, end)
    assert header_params == line_params == (start, dt.date(2026, 10, 28))
    assert "sales_date >= %s" in header_sql
    assert "h.invoice_no = sales_details.sales_code" in line_sql
    assert date_filter("customer", start, end) == ("", ())
