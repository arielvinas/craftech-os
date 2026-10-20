"""Run the Pagos and Pagos ARG interpreters of one code tree over the latest snapshots; dump facts
as JSON. The dump holds real customer data: it is written only outside the repository."""
import json, os, sys
from pathlib import Path
import psycopg
from craftech_os.interpret import pagos
repo = Path(__file__).resolve().parents[3]
dest = Path(sys.argv[1]).resolve()
if dest.is_relative_to(repo):
    sys.exit(f"refusing to write customer data inside the repository: {dest}")
interpreters = {"Pagos": pagos.interpret, "Pagos ARG": pagos.interpret_arg}
conn = psycopg.connect(os.environ["DATABASE_URL"])
out = {}
for name, schema, title, doc in conn.execute("""
    SELECT t.name, t.schema, s.title, n.content FROM source_tab t JOIN source s ON s.id=t.source_id
    JOIN LATERAL (SELECT content FROM snapshot WHERE source_tab_id=t.id ORDER BY read_at DESC, id DESC LIMIT 1) n ON true
    WHERE t.name IN ('Pagos', 'Pagos ARG') AND t.class='CARGA'"""):
    facts, issues = interpreters[name](doc, schema, title)
    out[f"{title} / {name}"] = {
        "facts": {k: [{c: str(v) for c, v in f.items()} for f in vs] for k, vs in facts.items()},
        "issues": [[t, k, d] for t, k, d in issues],
    }
json.dump(out, open(dest, "w"), default=str, sort_keys=True)
