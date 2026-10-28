import json
import os
import re
from pathlib import Path


def load_companies(path: str) -> list[dict]:
    companies = json.loads(Path(path).read_text())
    if not isinstance(companies, list) or not companies:
        raise ValueError("Company configuration must be a nonempty JSON array")
    seen = set()
    for company in companies:
        for field in ("company_id", "name", "host", "database", "user", "password_env"):
            if not isinstance(company.get(field), str) or not company[field].strip():
                raise ValueError(f"Company requires nonempty {field}")
        identity = company["company_id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", identity):
            raise ValueError(f"Invalid company_id: {identity}")
        if identity in seen:
            raise ValueError(f"Duplicate company_id: {identity}")
        seen.add(identity)
        if not os.environ.get(company["password_env"]):
            raise ValueError(f"Missing password environment variable: {company['password_env']}")
        port = company.get("port", 3306)
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"Invalid port for {identity}")
    return companies
