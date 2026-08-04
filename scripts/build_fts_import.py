"""Build bounded SQL batches for the website D1 full-text index.

The input is the Vectorize export. Vectors are deliberately discarded here;
only server-side metadata, evidence excerpts, and search tokens are kept.
"""
import argparse
import json
import re
from pathlib import Path

SCHEMA = """DROP TABLE IF EXISTS ios_ask_fts_next;
CREATE VIRTUAL TABLE ios_ask_fts_next USING fts5(
  vector_id UNINDEXED, source UNINDEXED, source_type UNINDEXED,
  path UNINDEXED, title_path UNINDEXED, lines UNINDEXED, text UNINDEXED,
  ios_version UNINDEXED, swift_version UNINDEXED, platform UNINDEXED,
  topic UNINDEXED, section UNINDEXED, language UNINDEXED,
  authority UNINDEXED, confidence UNINDEXED, source_origin UNINDEXED, tokens
);
"""

FINALIZE = """DROP TABLE IF EXISTS ios_ask_fts;
ALTER TABLE ios_ask_fts_next RENAME TO ios_ask_fts;
"""


def sql(value):
    return "'" + str(value or "").replace("\x00", "").replace("'", "''") + "'"


def tokens(value):
    value = value.lower()
    out = set(re.findall(r"[a-z_@][a-z0-9_+.#@-]{1,}", value))
    for run in re.findall(r"[\u3400-\u9fff]{2,}", value):
        out.update(run[index : index + 2] for index in range(len(run) - 1))
    return " ".join(sorted(out))


def statement(record):
    metadata = record["metadata"]
    values = [
        record["id"], metadata.get("source"), metadata.get("type"),
        metadata.get("path"), metadata.get("title_path"), metadata.get("lines"),
        metadata.get("text"), metadata.get("ios_version"), metadata.get("swift_version"),
        metadata.get("platform"), metadata.get("topic"), metadata.get("section"),
        metadata.get("language"), metadata.get("authority"), metadata.get("confidence"),
        metadata.get("source_origin"),
        tokens("\n".join(str(metadata.get(key, "")) for key in ("path", "title_path", "text"))),
    ]
    columns = "vector_id, source, source_type, path, title_path, lines, text, ios_version, swift_version, platform, topic, section, language, authority, confidence, source_origin, tokens"
    return f"INSERT INTO ios_ask_fts_next({columns}) VALUES (" + ", ".join(sql(value) for value in values) + ");\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for stale in args.output.glob("*.sql"):
        stale.unlink()
    batch, part, count = [], 0, 0
    for line in args.input.open(encoding="utf-8"):
        batch.append(statement(json.loads(line)))
        count += 1
        if len(batch) >= args.batch_size:
            suffix = f"{part:03d}.sql"
            prefix = SCHEMA if part == 0 else ""
            (args.output / suffix).write_text(prefix + "".join(batch), encoding="utf-8")
            part += 1
            batch = []
    if batch:
        suffix = f"{part:03d}.sql"
        prefix = SCHEMA if part == 0 else ""
        (args.output / suffix).write_text(prefix + "".join(batch), encoding="utf-8")
        part += 1
    (args.output / "999-finalize.sql").write_text(FINALIZE, encoding="utf-8")
    print(f"Wrote {part} SQL batches for {count} Vectorize records to {args.output}")


if __name__ == "__main__":
    main()
