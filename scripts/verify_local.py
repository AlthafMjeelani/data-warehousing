"""Run the integration suite with isolated native databases when Docker is unavailable.

Requires installed PostgreSQL and MySQL server/client binaries. Never uses existing databases.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(port, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Database exited during startup; inspect output above")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError("Database did not start within 120 seconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", required=True)
    parser.add_argument("--mysql-bin", required=True)
    args = parser.parse_args()
    env = dict(os.environ)
    env["PATH"] = args.postgres_bin + os.pathsep + args.mysql_bin + os.pathsep + env["PATH"]
    for binary in ("initdb", "postgres", "psql", "mysqld", "mysql", "dbt"):
        if not shutil.which(binary, path=env["PATH"]):
            parser.error(f"Missing executable: {binary}")
    # Native database sockets and MySQL paths need a short temporary prefix on macOS.
    with tempfile.TemporaryDirectory(prefix="dw-") as temporary:
        temp = Path(temporary)
        pg_data = temp / "pg"
        mysql_data = temp / "mysql"
        mysql_data.mkdir()
        pg_port, mysql_port = free_port(), free_port()
        env.update({
            "PGHOST": "127.0.0.1", "PGPORT": str(pg_port), "PGUSER": "warehouse",
            "PGDATABASE": "analytics", "PGPASSWORD": "",
            "POSTGRES_USER": "warehouse", "POSTGRES_DB": "analytics",
            "METABASE_DB_PASSWORD": "isolated_test", "BI_PASSWORD": "isolated_test",
            "SOURCE_A_PASSWORD": "demo_reader", "SOURCE_B_PASSWORD": "demo_reader",
            "MYSQL_ROOT_PASSWORD": "", "RUN_INTEGRATION": "1",
            "DBT_PROFILES_DIR": str(ROOT / "warehouse"),
            "TEST_COMPANIES_CONFIG": str(temp / "companies.json"),
        })
        config = json.loads((ROOT / "config/companies.example.json").read_text())
        for company in config:
            company.update(host="127.0.0.1", port=mysql_port)
        (temp / "companies.json").write_text(json.dumps(config))
        subprocess.run(
            [str(Path(args.postgres_bin) / "initdb"), "-D", str(pg_data), "-U", "warehouse",
             "--auth=trust", "--no-locale", "--encoding=UTF8"], env=env, check=True,
        )
        subprocess.run(
            [str(Path(args.mysql_bin) / "mysqld"), "--no-defaults", "--initialize-insecure",
             f"--datadir={mysql_data}"], env=env, check=True,
        )
        processes = []
        try:
            pg = subprocess.Popen(
                [str(Path(args.postgres_bin) / "postgres"), "-D", str(pg_data),
                 "-p", str(pg_port), "-h", "127.0.0.1", "-k", str(temp)], env=env,
            )
            processes.append(pg)
            mysql = subprocess.Popen(
                [str(Path(args.mysql_bin) / "mysqld"), "--no-defaults",
                 f"--datadir={mysql_data}", f"--port={mysql_port}", "--bind-address=127.0.0.1",
                 f"--socket={temp / 'mysql.sock'}", f"--pid-file={temp / 'mysql.pid'}",
                 "--mysqlx=0"], env=env,
            )
            processes.append(mysql)
            wait_for(pg_port, pg)
            wait_for(mysql_port, mysql)
            subprocess.run(
                ["psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
                 "CREATE DATABASE analytics"], env=env, check=True,
            )
            subprocess.run(["sh", str(ROOT / "sql/init.sh")], env=env, check=True)
            subprocess.run(
                ["mysql", "--protocol=TCP", "-h", "127.0.0.1", "-P", str(mysql_port),
                 "-u", "root"], input=(ROOT / "demo/source.sql").read_bytes(), env=env, check=True,
            )
            subprocess.run(
                ["python", "-m", "pytest", "-q", "tests/test_integration.py"],
                cwd=ROOT, env=env, check=True,
            )
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


if __name__ == "__main__":
    main()
