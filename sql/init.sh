#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v meta_password="$METABASE_DB_PASSWORD" -v bi_password="$BI_PASSWORD" <<'SQL'
CREATE ROLE metabase_app LOGIN PASSWORD :'meta_password';
CREATE DATABASE metabase OWNER metabase_app;
CREATE ROLE analytics_reader LOGIN PASSWORD :'bi_password';
CREATE SCHEMA raw;
CREATE SCHEMA staging;
CREATE SCHEMA core;
CREATE SCHEMA marts;
GRANT USAGE ON SCHEMA marts TO analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO analytics_reader;
SQL
