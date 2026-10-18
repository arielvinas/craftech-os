from pathlib import Path

import psycopg
import yaml

CLASSES = ("CARGA", "DERIVADA", "HISTORICA", "IGNORAR", "A_CONFIRMAR", "SIN_CLASIFICAR")
SOURCES_FILE = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"


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


def parse(text: str) -> list[dict]:
    """Validate sources.yaml. Returns [{title, default_class, tabs: [(name, class)]}]."""
    data = yaml.safe_load(text)
    if (
        not isinstance(data, dict)
        or set(data) != {"sources"}
        or not isinstance(data["sources"], list)
    ):
        raise SourcesError("sources.yaml must have a single top-level key 'sources' with a list")
    result, titles = [], set()
    for i, entry in enumerate(data["sources"]):
        if not isinstance(entry, dict):
            raise SourcesError(f"sources[{i}] must be a mapping")
        unknown = set(entry) - {"title", "tabs", "all_tabs"}
        if unknown:
            raise SourcesError(f"sources[{i}]: unknown keys {sorted(unknown)}")
        title = _name(entry.get("title"), f"sources[{i}].title")
        if title in titles:
            raise SourcesError(f"duplicated source title {title!r}")
        titles.add(title)
        if ("tabs" in entry) == ("all_tabs" in entry):
            raise SourcesError(f"{title!r}: exactly one of 'tabs' or 'all_tabs' is required")
        if "all_tabs" in entry:
            result.append(
                {"title": title, "default_class": _class(entry["all_tabs"], title), "tabs": []}
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
        result.append({"title": title, "default_class": None, "tabs": tabs})
    return result


def load(conn: psycopg.Connection, sources: list[dict]) -> None:
    """Upsert sources and tabs; tabs no longer listed become inactive, never deleted."""
    with conn.transaction():
        for s in sources:
            (source_id,) = conn.execute(
                """
                INSERT INTO source (title, default_class) VALUES (%s, %s)
                ON CONFLICT (title) DO UPDATE SET default_class = EXCLUDED.default_class
                RETURNING id
                """,
                (s["title"], s["default_class"]),
            ).fetchone()
            for name, cls in s["tabs"]:
                conn.execute(
                    """
                    INSERT INTO source_tab (source_id, name, class) VALUES (%s, %s, %s)
                    ON CONFLICT (source_id, name)
                    DO UPDATE SET class = EXCLUDED.class, active = true
                    """,
                    (source_id, name, cls),
                )
            if s["default_class"] is None:
                conn.execute(
                    "UPDATE source_tab SET active = false"
                    " WHERE source_id = %s AND active AND NOT (name = ANY(%s))",
                    (source_id, [name for name, _ in s["tabs"]]),
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
