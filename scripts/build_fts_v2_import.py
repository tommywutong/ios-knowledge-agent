"""Build bounded, atomic D1 SQL batches from the FTS v2 NDJSON export."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_MAX_BYTES = 230 * 1024 * 1024
SCHEMA = """DROP TABLE IF EXISTS ios_ask_fts_v2_next;
DROP TABLE IF EXISTS ios_ask_fts_v2_neighbors_next;
CREATE VIRTUAL TABLE ios_ask_fts_v2_next USING fts5(
  chunk_id UNINDEXED, file_key UNINDEXED, chunk_ordinal UNINDEXED,
  content_hash UNINDEXED, tier UNINDEXED, selection_score UNINDEXED,
  source UNINDEXED, source_type UNINDEXED, path UNINDEXED,
  title_path UNINDEXED, lines UNINDEXED, text UNINDEXED,
  ios_version UNINDEXED, swift_version UNINDEXED, platform UNINDEXED,
  topic UNINDEXED, section UNINDEXED, language UNINDEXED,
  authority UNINDEXED, confidence UNINDEXED, source_origin UNINDEXED,
  title_tokens, body_tokens
);
CREATE TABLE ios_ask_fts_v2_neighbors_next(
  fts_rowid INTEGER PRIMARY KEY, file_key TEXT NOT NULL, chunk_ordinal INTEGER NOT NULL
);
"""
FINALIZE = """DROP TABLE IF EXISTS ios_ask_fts_v2_neighbors;
DROP TABLE IF EXISTS ios_ask_fts_v2;
ALTER TABLE ios_ask_fts_v2_next RENAME TO ios_ask_fts_v2;
ALTER TABLE ios_ask_fts_v2_neighbors_next RENAME TO ios_ask_fts_v2_neighbors;
CREATE INDEX idx_ios_ask_fts_v2_neighbors_file
  ON ios_ask_fts_v2_neighbors(file_key, chunk_ordinal);
"""


def sql(value):
    safe = (
        str(value if value is not None else "")
        .replace("\x00", "")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
        .replace("'", "''")
    )
    return "'" + safe + "'"


def tokens(value):
    value = value.lower()
    output = set(re.findall(r"[a-z_@][a-z0-9_+.#@:-]{1,}", value))
    for run in re.findall(r"[\u3400-\u9fff]{2,}", value):
        output.update(run[index : index + 2] for index in range(len(run) - 1))
    return " ".join(sorted(output))


def statement(record, rowid):
    metadata = record["metadata"]
    title_value = "\n".join(
        str(metadata.get(key, "")) for key in ("path", "title_path", "topic", "section")
    )
    body_value = str(metadata.get("text", ""))
    values = [
        record["id"], record["file_key"], record["chunk_ordinal"], record["content_hash"],
        record["tier"], record.get("selection_score", 0), metadata.get("source"),
        metadata.get("type"), metadata.get("path"), metadata.get("title_path"),
        metadata.get("lines"), body_value, metadata.get("ios_version"),
        metadata.get("swift_version"), metadata.get("platform"), metadata.get("topic"),
        metadata.get("section"), metadata.get("language"), metadata.get("authority"),
        metadata.get("confidence"), metadata.get("source_origin"), tokens(title_value),
        tokens(body_value),
    ]
    columns = (
        "chunk_id, file_key, chunk_ordinal, content_hash, tier, selection_score, source, "
        "source_type, path, title_path, lines, text, ios_version, swift_version, platform, "
        "topic, section, language, authority, confidence, source_origin, title_tokens, body_tokens"
    )
    fts_insert = (
        f"INSERT INTO ios_ask_fts_v2_next(rowid, {columns}) VALUES ({rowid}, "
        + ", ".join(sql(v) for v in values)
        + ");\n"
    )
    neighbor_insert = (
        "INSERT INTO ios_ask_fts_v2_neighbors_next(fts_rowid, file_key, chunk_ordinal) "
        f"VALUES ({rowid}, {sql(record['file_key'])}, {int(record['chunk_ordinal'])});\n"
    )
    return fts_insert + neighbor_insert


def build(input_path: Path, output_dir: Path, *, batch_size=750, max_bytes=DEFAULT_MAX_BYTES):
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.sql"):
        stale.unlink()
    minimum_bytes = len(SCHEMA.encode("utf-8")) + len(FINALIZE.encode("utf-8"))
    if max_bytes < minimum_bytes:
        raise ValueError(f"FTS v2 SQL byte limit is smaller than its schema: {max_bytes}")
    batch, part, count, input_count, dropped_for_size, total_bytes = [], 0, 0, 0, 0, 0
    planned_bytes = minimum_bytes
    by_tier, by_source = {}, {}

    def write_batch(lines):
        nonlocal part, total_bytes
        content = (SCHEMA if part == 0 else "") + "".join(lines)
        encoded = content.encode("utf-8")
        total_bytes += len(encoded)
        if total_bytes + len(FINALIZE.encode("utf-8")) > max_bytes:
            raise ValueError(f"FTS v2 SQL exceeds byte limit: {total_bytes} > {max_bytes}")
        (output_dir / f"{part:03d}.sql").write_bytes(encoded)
        part += 1

    with input_path.open(encoding="utf-8") as input_file:
        for line in input_file:
            record = json.loads(line)
            input_count += 1
            sql_statement = statement(record, count + 1)
            statement_bytes = len(sql_statement.encode("utf-8"))
            if planned_bytes + statement_bytes > max_bytes:
                if int(record.get("tier", 1)) == 0:
                    raise ValueError("FTS v2 SQL byte limit cannot preserve all Tier 0 rows")
                dropped_for_size += 1
                continue
            planned_bytes += statement_bytes
            batch.append(sql_statement)
            count += 1
            tier = str(record.get("tier", "unknown"))
            source = str(record.get("metadata", {}).get("source", "unknown"))
            by_tier[tier] = by_tier.get(tier, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1
            if len(batch) >= batch_size:
                write_batch(batch)
                batch = []
    if batch:
        write_batch(batch)
    finalize_bytes = FINALIZE.encode("utf-8")
    total_bytes += len(finalize_bytes)
    (output_dir / "999-finalize.sql").write_bytes(finalize_bytes)
    manifest = {
        "schema_version": 2,
        "input": str(input_path),
        "input_rows": input_count,
        "rows": count,
        "dropped_for_size": dropped_for_size,
        "batches": part,
        "sql_bytes": total_bytes,
        "max_bytes": max_bytes,
        "by_tier": dict(sorted(by_tier.items())),
        "by_source": dict(sorted(by_source.items())),
        "final_table": "ios_ask_fts_v2",
        "neighbor_table": "ios_ask_fts_v2_neighbors",
        "legacy_table_preserved": "ios_ask_fts",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batch-size", type=int, default=750)
    parser.add_argument("--max-mb", type=int, default=230)
    args = parser.parse_args()
    manifest = build(
        args.input, args.output, batch_size=args.batch_size, max_bytes=args.max_mb * 1024 * 1024
    )
    print(
        f"Wrote {manifest['batches']} SQL batches for {manifest['rows']} records "
        f"({manifest['sql_bytes'] / 1048576:.1f} MiB, "
        f"dropped {manifest['dropped_for_size']} for size) to {args.output}"
    )


if __name__ == "__main__":
    main()
