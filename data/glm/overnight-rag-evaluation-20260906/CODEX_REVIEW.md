# Codex Review

Review date: 2026-09-06. This batch is retained as an **offline candidate pool**,
not as a production regression suite or factual evidence source.

## Structural result

- The batch contains 3,143 JSONL records: 1,866 evaluation candidates, 436 aliases,
  137 coverage records, 332 quality findings, 252 FTS samples, and 120 triage records.
- The repository validator checks JSON syntax, ids, cross-file references, real source
  files and line ranges. Its line counting deliberately matches `chunker.py`'s
  `text.split("\\n")` contract. Four quality findings are intentionally directory-level;
  their `1-1` ranges are sentinels and must not be used as citations.
- The 31 missing `observed_top_paths` are retained as historical evidence of stale local
  index entries. They are not errors in the batch itself.
- The original prose summary overstated the quality aggregate. The JSONL-derived totals are
  168 `duplicate` findings and severity counts of 119 medium, 105 low, and 108 info; the
  adjacent reports now reflect these corrected values.

## Admissibility

- All 1,381 records labelled `模板生成：题面与该小节内容适配需人工复核` require semantic review.
  Path and line validity does not prove that the cited section answers the question.
- At least 44 template questions are visibly dependent on local document wording (for
  example, "这篇在系列中的位置"). They are unsuitable as standalone user questions.
- No batch item is automatically eligible for production evaluation, alias expansion,
  knowledge cards, source metadata, or deployment. A small manually reviewed subset
  should be promoted only after it passes the production Retrieval v2 path.

## Retrieval interpretation

- The reported `source-symbol` 20/20 FTS misses do not prove that exact symbol retrieval
  is broken. The sample submits long natural-language questions directly to local FTS;
  production performs query planning and also uses Vectorize, RRF, and reranking.
- Direct local FTS queries for `objc_msgSend`, `class_addMethod`, and `attachCategories`
  returned authoritative documentation or source candidates. `attachCategories` returned
  an objc4 source candidate at rank 3.
- The real local issue was 32 deleted `summer2026` files (1,521 chunks) remaining in the
  index. Codex removed them with `uv run ioskb sync --source summer2026 --no-embed` and
  verified that `freshness --source summer2026 --skip-upstreams --check` is clean.
- Production has not been republished after this local cleanup. Its recorded 55,635-vector
  snapshot predates removal; a future Cloudflare release must use the stable-ID deployment
  procedure and production Retrieval v2 evaluation, not this local FTS sample alone.
