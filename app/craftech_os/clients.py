"""Canonical clients from a Zoho Contacts.csv and from a file of alias decisions.

The files live outside the repo (~/repos/craftech-os-data/). Both loads run in one
transaction and are idempotent. Events and printed lines carry counts only, never names
or tax IDs; an error points at the line number.
"""

import csv
import re
from pathlib import Path

import psycopg

from craftech_os import events
from craftech_os.diff.compare import normalize

DEFAULT_TERMS_DAYS = 10
ALIAS_COLUMNS = ("fuente", "texto", "cliente", "decidio", "motivo")


class ClientsError(Exception):
    pass


def _rows(path: Path, columns: tuple[str, ...]) -> list[dict]:
    """The rows as {normalized column: stripped text}; fails if a column is missing."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = {normalize(name): name for name in reader.fieldnames or []}
        missing = [c for c in columns if c not in header]
        if missing:
            raise ClientsError(f"{path.name}: missing columns {', '.join(missing)}")
        return [{c: (row[header[c]] or "").strip() for c in columns} for row in reader]


def payment_terms_days(text: str) -> int:
    """Net 10 -> 10, Due on Receipt -> 0; anything else (blank, Custom) -> the default 10."""
    term = normalize(text)
    if term == "due on receipt":
        return 0
    found = re.fullmatch(r"net (\d+)", term)
    return int(found[1]) if found else DEFAULT_TERMS_DAYS


def _client(conn: psycopg.Connection, clients: dict[str, int], name: str) -> tuple[int, bool]:
    """The client with this name once normalized, created if missing: (id, created)."""
    key = normalize(name)
    if key in clients:
        return clients[key], False
    (client_id,) = conn.execute(
        "INSERT INTO client (name) VALUES (%s) RETURNING id", (name,)
    ).fetchone()
    clients[key] = client_id
    return client_id, True


def _clients_by_name(conn: psycopg.Connection) -> dict[str, int]:
    return {
        normalize(name): client_id
        for client_id, name in conn.execute("SELECT id, name FROM client")
    }


def load_zoho(conn: psycopg.Connection, path: Path) -> dict:
    """Upsert the razones sociales of a Zoho Contacts.csv, keyed by tax ID or razón social.

    A new razón social goes to the client named as its Display Name, created if missing.
    """
    columns = (
        "display name",
        "company name",
        "payment terms",
        "billing country",
        "cf.codigo tax id",
        "cf.tipo de tax id",
    )
    rows = _rows(path, columns)
    counts = {"read": len(rows), "created": 0, "updated": 0, "skipped": 0}
    with conn.transaction():
        clients = _clients_by_name(conn)
        known = [
            {"id": r[0], "tax_id": r[1], "fields": r[2:]}
            for r in conn.execute(
                "SELECT id, tax_id, legal_name, country, tax_id_type, payment_terms_days"
                " FROM client_legal_entity WHERE source_system = 'zoho'"
            )
        ]
        by_tax_id = {e["tax_id"]: e for e in known if e["tax_id"]}
        by_name = {normalize(e["fields"][0]): e for e in known}
        for row in rows:
            display, company = row["display name"], row["company name"]
            if not (display or company):
                counts["skipped"] += 1
                continue
            tax_id = row["cf.codigo tax id"] or None
            fields = (
                company or display,
                row["billing country"] or None,
                row["cf.tipo de tax id"] or None,
                payment_terms_days(row["payment terms"]),
            )
            entity = {"tax_id": tax_id, "fields": fields}
            match = by_tax_id.get(tax_id) or by_name.get(normalize(fields[0]))
            if match is None:
                client_id, _ = _client(conn, clients, display or company)
                (entity["id"],) = conn.execute(
                    "INSERT INTO client_legal_entity (legal_name, country, tax_id_type,"
                    " payment_terms_days, tax_id, client_id, source_system)"
                    " VALUES (%s, %s, %s, %s, %s, %s, 'zoho') RETURNING id",
                    (*fields, tax_id, client_id),
                ).fetchone()
                counts["created"] += 1
            else:
                entity["id"] = match["id"]
                if (match["tax_id"], match["fields"]) == (tax_id, fields):
                    counts["skipped"] += 1
                else:
                    conn.execute(
                        "UPDATE client_legal_entity SET legal_name = %s, country = %s,"
                        " tax_id_type = %s, payment_terms_days = %s, tax_id = %s,"
                        " updated_at = now() WHERE id = %s",
                        (*fields, tax_id, entity["id"]),
                    )
                    counts["updated"] += 1
            # A razón social repeated later in the file is the same one.
            if tax_id:
                by_tax_id[tax_id] = entity
            by_name[normalize(fields[0])] = entity
        events.record(conn, "clients_loaded", **counts)
    return counts


def load_aliases(conn: psycopg.Connection, path: Path) -> dict:
    """Insert each alias decision not already recorded, word for word.

    The client is found by its nombre de fantasía or one of its razones sociales, both
    normalized, and created by that name if there is none.
    """
    rows = _rows(path, ALIAS_COLUMNS)
    counts = {"read": len(rows), "created": 0, "updated": 0, "skipped": 0, "clients_created": 0}
    for line, row in enumerate(rows, start=2):
        missing = [c for c in ALIAS_COLUMNS if not row[c]]
        if missing:
            raise ClientsError(f"{path.name} line {line}: {', '.join(missing)} is blank")
    with conn.transaction():
        clients = _clients_by_name(conn)
        for client_id, legal_name in conn.execute(
            "SELECT client_id, legal_name FROM client_legal_entity"
        ):
            clients.setdefault(normalize(legal_name), client_id)
        recorded = set(
            conn.execute("SELECT source, text, client_id, author, reason FROM client_alias")
        )
        for row in rows:
            client_id, created = _client(conn, clients, row["cliente"])
            counts["clients_created"] += created
            decision = (
                row["fuente"],
                normalize(row["texto"]),
                client_id,
                row["decidio"],
                row["motivo"],
            )
            if decision in recorded:
                counts["skipped"] += 1
                continue
            conn.execute(
                "INSERT INTO client_alias (source, text, client_id, author, reason)"
                " VALUES (%s, %s, %s, %s, %s)",
                decision,
            )
            recorded.add(decision)
            counts["created"] += 1
        events.record(conn, "aliases_loaded", **counts)
    return counts
