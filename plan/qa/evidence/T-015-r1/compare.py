"""Run the Pagos interpreter of one code tree over the latest snapshots; dump facts as JSON."""
import json, os, sys, hashlib
import psycopg
from craftech_os.interpret import pagos
conn = psycopg.connect(os.environ["DATABASE_URL"])
out = {}
for tab_id, schema, title, doc in conn.execute("""
    SELECT t.id, t.schema, s.title, n.content FROM source_tab t JOIN source s ON s.id=t.source_id
    JOIN LATERAL (SELECT content FROM snapshot WHERE source_tab_id=t.id ORDER BY read_at DESC, id DESC LIMIT 1) n ON true
    WHERE t.name='Pagos' AND t.class='CARGA'"""):
    facts, issues = pagos.interpret(doc, schema, title)
    out[title] = {
        "facts": {k: [{c: str(v) for c, v in f.items()} for f in vs] for k, vs in facts.items()},
        "issues": [[t, k, d] for t, k, d in issues],
    }
json.dump(out, open(sys.argv[1], "w"), default=str, sort_keys=True)
