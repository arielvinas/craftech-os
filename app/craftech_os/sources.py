import json
import re
from pathlib import Path

import psycopg
import yaml

from craftech_os import yaml_unique
from craftech_os.diff.compare import column_index
from craftech_os.interpret import consolidado, fundings, interpreter

CLASSES = ("CARGA", "DERIVADA", "HISTORICA", "IGNORAR", "A_CONFIRMAR", "SIN_CLASIFICAR")
SOURCES_FILE = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"
DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class SourcesError(Exception):
    pass


def _name(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourcesError(f"{what} must be a non-empty string, got {value!r}")
    return value


def _class(value, what: str) -> str:
    if value not in CLASSES:
        raise SourcesError(f"{what}: unknown class {value!r}; allowed: {', '.join(CLASSES)}")
    return value


def _schema(value, what: str, name: str) -> dict:
    """A tab schema: header text, key column, block openers and the month grid columns.

    Pagos also names its funding blocks and the row that totals them; the FUNDINGS tracker and
    Consolidado map roles to header texts, and Consolidado maps each bank to its legal entity,
    "historical" or "adjustment".
    """
    if not isinstance(value, dict) or not {"header", "key"} <= set(value):
        raise SourcesError(f"{what}: a schema needs 'header' and 'key'")
    unknown = set(value) - {
        "header",
        "key",
        "blocks",
        "grid",
        "funding_blocks",
        "funding_total",
        "columns",
        "banks",
    }
    if unknown:
        raise SourcesError(f"{what}: unknown schema keys {sorted(unknown)}")
    _name(value["header"], f"{what} header")
    try:
        column_index(value["key"] if isinstance(value["key"], str) else "")
        if "grid" in value:
            first, sep, last = str(value["grid"]).partition(":")
            if not sep or column_index(first) > column_index(last):
                raise ValueError
    except ValueError:
        raise SourcesError(f"{what}: key must be a column (A) and grid a range (D:AM)") from None
    blocks = value.get("blocks", [])
    if not isinstance(blocks, list):
        raise SourcesError(f"{what}: blocks must be a list of texts")
    for block in blocks:
        _name(block, f"{what} block")
    if not set(value.get("funding_blocks", [])) <= set(blocks):
        raise SourcesError(f"{what}: funding_blocks must be among the blocks")
    if "funding_total" in value:
        _name(value["funding_total"], f"{what} funding_total")
    if "columns" in value:
        columns = value["columns"]
        if not isinstance(columns, dict):
            raise SourcesError(f"{what}: columns must map roles to header texts")
        for role, text in columns.items():
            _name(text, f"{what} column {role!r}")
        required = consolidado.COLUMNS if name == "Consolidado" else fundings.REQUIRED
        missing = sorted(set(required) - set(columns))
        if missing:
            raise SourcesError(f"{what}: columns needs {missing}")
    if name == "Consolidado" or "banks" in value:
        banks = value.get("banks")
        if not isinstance(banks, dict) or not banks:
            raise SourcesError(f"{what}: banks must map each bank to its legal entity")
        for bank, kind in banks.items():
            _name(bank, f"{what} bank")
            _name(kind, f"{what} legal entity of {bank!r}")
    return value


def parse(text: str) -> list[dict]:
    """Validate sources.yaml.

    Returns [{title, drive_id, default_class, tabs: [(name, class)], schemas: {name: schema}}].
    """
    try:
        data = yaml_unique.load(text)
    except yaml.YAMLError as e:
        raise SourcesError(f"invalid YAML: {e}") from e
    except ValueError as e:
        raise SourcesError(str(e)) from e
    if (
        not isinstance(data, dict)
        or set(data) != {"sources"}
        or not isinstance(data["sources"], list)
    ):
        raise SourcesError("sources.yaml must have a single top-level key 'sources' with a list")
    result, titles, drive_ids = [], set(), set()
    for i, entry in enumerate(data["sources"]):
        if not isinstance(entry, dict):
            raise SourcesError(f"sources[{i}] must be a mapping")
        unknown = set(entry) - {"title", "drive_id", "tabs", "all_tabs", "schemas"}
        if unknown:
            raise SourcesError(f"sources[{i}]: unknown keys {sorted(unknown)}")
        title = _name(entry.get("title"), f"sources[{i}].title")
        if title in titles:
            raise SourcesError(f"duplicated source title {title!r}")
        titles.add(title)
        drive_id = entry.get("drive_id")
        if drive_id is not None:
            if not isinstance(drive_id, str) or not DRIVE_ID.match(drive_id):
                raise SourcesError(f"{title!r}: drive_id must be a Google Drive file id")
            if drive_id in drive_ids:
                raise SourcesError(f"{title!r}: duplicated drive_id {drive_id!r}")
            drive_ids.add(drive_id)
        if ("tabs" in entry) == ("all_tabs" in entry):
            raise SourcesError(f"{title!r}: exactly one of 'tabs' or 'all_tabs' is required")
        if "all_tabs" in entry:
            if "schemas" in entry:
                raise SourcesError(f"{title!r}: schemas need tabs listed by name, not all_tabs")
            result.append(
                {
                    "title": title,
                    "drive_id": drive_id,
                    "default_class": _class(entry["all_tabs"], title),
                    "tabs": [],
                    "schemas": {},
                }
            )
            continue
        groups = entry["tabs"]
        if not isinstance(groups, dict) or not groups:
            raise SourcesError(f"{title!r}: 'tabs' must map classes to lists of tab names")
        tabs, seen = [], set()
        for cls, names in groups.items():
            _class(cls, title)
            if not isinstance(names, list) or not names:
                raise SourcesError(f"{title!r}: {cls} must be a non-empty list of tab names")
            for name in names:
                _name(name, f"{title!r} {cls} tab")
                if name in seen:
                    raise SourcesError(f"{title!r}: duplicated tab {name!r}")
                seen.add(name)
                tabs.append((name, cls))
        schemas = entry.get("schemas", {})
        if not isinstance(schemas, dict):
            raise SourcesError(f"{title!r}: 'schemas' must map tab names to schemas")
        for name, schema in schemas.items():
            if name not in seen:
                raise SourcesError(f"{title!r}: schema for {name!r}, a tab not listed in 'tabs'")
            _schema(schema, f"{title!r} schema of {name!r}", name)
        for name, cls in tabs:
            schema = schemas.get(name, {})
            if (
                cls == "CARGA"
                and interpreter(title, name)
                and not {"grid", "columns"} & set(schema)
            ):
                raise SourcesError(
                    f"{title!r}: {name!r} is interpreted"
                    " and needs a schema with 'grid' or 'columns'"
                )
        result.append(
            {
                "title": title,
                "drive_id": drive_id,
                "default_class": None,
                "tabs": tabs,
                "schemas": schemas,
            }
        )
    return result


def load(conn: psycopg.Connection, sources: list[dict]) -> None:
    """Upsert sources and tabs; tabs no longer listed become inactive, never deleted.

    SIN_CLASIFICAR tabs come from Google, not from the list, and stay as they are.

    A source missing from the list keeps its row but all its tabs become inactive.
    An all_tabs source gives its class to every tab it has.
    """
    with conn.transaction():
        # The list owns every drive_id: clearing them first lets a renamed source keep its id.
        conn.execute("UPDATE source SET drive_id = NULL WHERE drive_id IS NOT NULL")
        for s in sources:
            (source_id,) = conn.execute(
                """
                INSERT INTO source (title, drive_id, default_class) VALUES (%s, %s, %s)
                ON CONFLICT (title) DO UPDATE
                SET drive_id = EXCLUDED.drive_id, default_class = EXCLUDED.default_class
                RETURNING id
                """,
                (s["title"], s["drive_id"], s["default_class"]),
            ).fetchone()
            for name, cls in s["tabs"]:
                schema = s["schemas"].get(name)
                conn.execute(
                    """
                    INSERT INTO source_tab (source_id, name, class, schema)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (source_id, name)
                    DO UPDATE SET class = EXCLUDED.class, schema = EXCLUDED.schema, active = true
                    """,
                    (source_id, name, cls, json.dumps(schema) if schema else None),
                )
            if s["default_class"] is None:
                conn.execute(
                    "UPDATE source_tab SET active = false WHERE source_id = %s AND active"
                    " AND class <> 'SIN_CLASIFICAR' AND NOT (name = ANY(%s))",
                    (source_id, [name for name, _ in s["tabs"]]),
                )
            else:
                conn.execute(
                    "UPDATE source_tab SET class = %s WHERE source_id = %s AND class <> %s",
                    (s["default_class"], source_id, s["default_class"]),
                )
        conn.execute(
            "UPDATE source_tab SET active = false WHERE active AND source_id IN"
            " (SELECT id FROM source WHERE NOT (title = ANY(%s)))",
            ([s["title"] for s in sources],),
        )


def summary(conn: psycopg.Connection) -> list[tuple[str, str | None, dict[str, int]]]:
    """Each source with its count of active tabs per class, ordered by title."""
    rows = conn.execute(
        """
        SELECT s.title, s.default_class, t.class, count(t.id)
        FROM source s
        LEFT JOIN source_tab t ON t.source_id = s.id AND t.active
        GROUP BY s.title, s.default_class, t.class
        ORDER BY s.title, array_position(%s, t.class)
        """,
        (list(CLASSES),),
    ).fetchall()
    result: dict[str, tuple[str | None, dict[str, int]]] = {}
    for title, default_class, cls, count in rows:
        counts = result.setdefault(title, (default_class, {}))[1]
        if cls is not None:
            counts[cls] = count
    return [(title, dc, counts) for title, (dc, counts) in result.items()]


TITLE_LINE = re.compile(r"^(\s*)- (title: .*)$")


def with_drive_ids(text: str, drive_ids: dict[str, str]) -> str:
    """Return sources.yaml with a drive_id line under each given title, comments kept."""
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        out.append(line)
        match = TITLE_LINE.match(line.rstrip("\n"))
        if not match:
            continue
        title = yaml.safe_load(match.group(2))["title"]
        if title in drive_ids:
            drive_id = drive_ids[title]
            if not DRIVE_ID.match(drive_id):
                raise SourcesError(f"{title!r}: Google returned an invalid file id")
            out.append(f'{match.group(1)}  drive_id: "{drive_id}"\n')
    result = "".join(out)
    written = {s["title"]: s["drive_id"] for s in parse(result)}
    missing = sorted(t for t, i in drive_ids.items() if written.get(t) != i)
    if missing:
        raise SourcesError(f"could not write drive_id for {missing}")
    return result
