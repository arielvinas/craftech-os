#!/bin/sh
# Runs once, when the PostgreSQL volume is empty: creates the application user
# (not a superuser), makes it owner of the main database and creates the test database.
set -eu
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set in infra/.env}"

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v pw="$APP_DB_PASSWORD" -v db="$POSTGRES_DB" -v testdb="${POSTGRES_DB}_test" <<'SQL'
CREATE ROLE craftech_app LOGIN PASSWORD :'pw';
ALTER DATABASE :"db" OWNER TO craftech_app;
ALTER SCHEMA public OWNER TO craftech_app;
CREATE DATABASE :"testdb" OWNER craftech_app;
\connect :testdb
ALTER SCHEMA public OWNER TO craftech_app;
SQL
