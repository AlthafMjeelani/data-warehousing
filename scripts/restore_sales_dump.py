"""Restore only the warehouse source tables from a trusted mysqldump into a NEW database.

Streams SQL to the existing isolated kaku-source container. Does not alter the dump or
restore views, triggers, routines, replication metadata, or unrelated application tables.
"""

import argparse
import hashlib
import re
import subprocess
from pathlib import Path

from ingestion.pipeline import TABLES


def selected_statements(lines, tables):
    """Extract mysqldump CREATE TABLE and INSERT statements, including wrapped statements."""
    statement = []
    for line in lines:
        if not statement:
            match = re.match(r"^(?:CREATE TABLE|INSERT INTO) `([^`]+)`", line)
            if not match or match[1] not in tables:
                continue
        statement.append(line)
        if line.rstrip().endswith(";"):
            yield "".join(statement)
            statement = []
    if statement:
        raise ValueError("Selected SQL statement is incomplete at end of dump")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--database", default="tenant_kaku_sales")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", args.database):
        parser.error("Invalid target database name")
    if not args.dump.is_file():
        parser.error("Dump file does not exist")
    # Intentionally fails if this target already exists; never silently replaces existing data.
    subprocess.run([
        "docker", "compose", "exec", "-T", "kaku-source", "sh", "-c",
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root -e '
        f"'CREATE DATABASE `{args.database}`'",
    ], check=True)
    command = [
        "docker", "compose", "exec", "-T", "kaku-source", "sh", "-c",
        f'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --max-allowed-packet=256M '
        f'-u root {args.database}',
    ]
    created = set()
    statements = 0
    process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True)
    try:
        process.stdin.write(
            "SET NAMES utf8mb4; SET FOREIGN_KEY_CHECKS=0; SET UNIQUE_CHECKS=0; "
            "SET time_zone='+00:00'; SET sql_mode='NO_AUTO_VALUE_ON_ZERO';\n"
        )
        with args.dump.open(encoding="utf-8") as source:
            for sql in selected_statements(source, TABLES):
                if sql.startswith("CREATE TABLE"):
                    table = re.match(r"CREATE TABLE `([^`]+)`", sql)[1]
                    created.add(table)
                    print(f"Restoring {table}", flush=True)
                process.stdin.write(sql)
                statements += 1
        process.stdin.write("SET FOREIGN_KEY_CHECKS=1; SET UNIQUE_CHECKS=1;\n")
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("Restore failed; inspect MySQL error above")
        missing = set(TABLES) - created
        if missing:
            raise ValueError(f"Dump is missing required tables: {sorted(missing)}")
        with args.dump.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        print(f"Restored {len(created)} tables, {statements} statements into {args.database}")
        print(f"Source SHA256: {digest}")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
