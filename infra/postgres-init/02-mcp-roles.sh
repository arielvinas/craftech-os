#!/bin/sh
# Creates (or updates the password of) the two roles of the MCP server, in the
# whole cluster: mcp_reader (read-only transactions, 10 s per query) and
# mcp_writer. Their privileges are granted by migration 0006. Runs by itself on
# an empty volume; on an existing one, run it once by hand (see README.md).
# Safe to run again.
set -eu
: "${MCP_READER_PASSWORD:?MCP_READER_PASSWORD must be set in infra/.env}"
: "${MCP_WRITER_PASSWORD:?MCP_WRITER_PASSWORD must be set in infra/.env}"

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v reader_pw="$MCP_READER_PASSWORD" -v writer_pw="$MCP_WRITER_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE mcp_reader LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_reader') \gexec
SELECT 'CREATE ROLE mcp_writer LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_writer') \gexec
ALTER ROLE mcp_reader LOGIN PASSWORD :'reader_pw';
ALTER ROLE mcp_writer LOGIN PASSWORD :'writer_pw';
ALTER ROLE mcp_reader SET default_transaction_read_only = on;
ALTER ROLE mcp_reader SET statement_timeout = '10s';
SQL
