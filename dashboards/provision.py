"""Create a consolidated administrator dashboard via the Metabase REST API.

Run after browser setup with METABASE_API_KEY set. All charts retain currency and company.
This dashboard is for authorized cross-company administrators, not tenant isolation.
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request


def request(base, key, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + "/api" + path, data=data, method=method,
        headers={"X-API-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://metabase:3000")
    parser.add_argument("--company", help="Create a separate dashboard scoped to this company_id")
    args = parser.parse_args()
    if args.company and not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", args.company):
        parser.error("Invalid company_id")
    key = os.environ.get("METABASE_API_KEY")
    if not key:
        parser.error("Set METABASE_API_KEY after completing browser setup")
    def api(method, path, body=None):
        return request(args.url, key, method, path, body)
    database_name = "Sales Warehouse"
    existing = api("GET", "/database")["data"]
    database = next((db for db in existing if db["name"] == database_name), None)
    if database is None:
        database = api("POST", "/database", {
            "name": database_name, "engine": "postgres",
            "details": {
                "host": "warehouse", "port": 5432,
                "dbname": os.environ.get("PGDATABASE", "analytics"),
                "user": "analytics_reader", "password": os.environ["BI_PASSWORD"],
                "ssl": False,
            },
        })
    database_id = database["id"]
    # Reuse collection/dashboard/cards by exact name so reruns do not duplicate them.
    collection_name = (
        f"Warehouse - {args.company.upper()}" if args.company
        else "Warehouse - cross-company administrators"
    )
    collections = api("GET", "/collection")
    collection = next((c for c in collections if c["name"] == collection_name), None)
    if collection is None:
        collection = api("POST", "/collection", {"name": collection_name})
    collection_id = collection["id"]
    dashboard_name = (
        f"{args.company.upper()} Sales Overview" if args.company
        else "Sales overview by company and currency"
    )
    items = api("GET", f"/collection/{collection_id}/items")["data"]
    dashboard = next((i for i in items if i["model"] == "dashboard"
                      and i["name"] == dashboard_name), None)
    if dashboard is None:
        dashboard = api("POST", "/dashboard", {
            "name": dashboard_name, "collection_id": collection_id,
            "description": "Sales exclude tax. Currency amounts are never combined. "
                           "Current hierarchy; review metric definitions before business use.",
        })
    charts = [
        ("Monthly sales", """select company_id, company_name, currency_code,
            date_trunc('month',sales_date)::date as month,
            sum(net_sales_excluding_tax) as net_sales_excluding_tax
            from marts.mart_daily_sales group by 1,2,3,4 order by 4,1,3"""),
        ("Sales and returns", """select company_id, company_name, currency_code,
            sum(sales_excluding_tax) as sales_excluding_tax,
            sum(returns_excluding_tax) as returns_excluding_tax,
            sum(net_sales_excluding_tax) as net_sales_excluding_tax
            from marts.mart_daily_sales group by 1,2,3 order by 1,3"""),
        ("Product performance", """select company_id, currency_code, product_code, product_name,
            sum(net_sales_excluding_tax) as net_sales_excluding_tax
            from marts.mart_product_sales group by 1,2,3,4 order by 5 desc"""),
        ("Customer performance", """select company_id,currency_code,customer_code,customer_name,
            sum(net_sales_excluding_tax) as net_sales_excluding_tax
            from marts.mart_customer_sales group by 1,2,3,4 order by 5 desc"""),
        ("Route and region performance", """select company_id,currency_code,region_name,
            branch_name,route_name,sum(net_sales_excluding_tax) as net_sales_excluding_tax
            from marts.mart_route_sales group by 1,2,3,4,5 order by 6 desc"""),
        ("Refresh status", "select * from marts.mart_load_status order by company_id"),
    ]
    cards = []
    for index, (name, query) in enumerate(charts):
        if args.company:
            # Filter inside each source relation, before grouping/ranking, not after aggregation.
            query = re.sub(
                r"\bfrom (marts\.\w+)",
                lambda match: (
                    f"from (select * from {match.group(1)} "
                    f"where company_id = '{args.company}') company_scope"
                ),
                query,
                flags=re.IGNORECASE,
            )
        body = {
            "name": name, "collection_id": collection_id, "display": "table",
            "visualization_settings": {},
            "dataset_query": {
                "database": database_id, "type": "native",
                "native": {"query": query, "template-tags": {}},
            },
        }
        card = next((i for i in items if i["model"] == "card" and i["name"] == name), None)
        if card:
            card = api("PUT", f"/card/{card['id']}", body)
        else:
            card = api("POST", "/card", body)
        cards.append({
            "id": -(index + 1), "card_id": card["id"], "row": (index // 2) * 6,
            "col": (index % 2) * 12, "size_x": 12, "size_y": 6,
            "parameter_mappings": [], "visualization_settings": {},
        })
    api("PUT", f"/dashboard/{dashboard['id']}", {"dashcards": cards})
    print(f"Dashboard: http://localhost:3000/dashboard/{dashboard['id']}")
    # Trigger synchronous query execution so SQL or permissions errors fail provisioning.
    for card in cards:
        for attempt in range(3):
            try:
                result = api("POST", f"/card/{card['card_id']}/query", {"parameters": []})
                if result.get("status") != "completed":
                    raise RuntimeError(f"Card {card['card_id']} query failed")
                break
            except urllib.error.HTTPError as exc:
                if attempt == 2 or exc.code < 500:
                    raise
                time.sleep(2)


if __name__ == "__main__":
    main()
