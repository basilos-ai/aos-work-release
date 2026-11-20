---
name: "local-sql-analysis"
description: "Design, validate, and optionally execute read-only SQL against local user-provided data. Use when the user needs SQL exploration or analysis without a remote warehouse account."
---

# Responsibilities

Produce dialect-aware, reproducible SQL for local files or local databases and distinguish generated, parsed, and actually executed evidence. Prefer read-only analysis and preserve source files.

# Execution

1. Inventory the local inputs, schemas, file formats, sizes, encodings, date conventions, null markers, and target SQL dialect. Do not infer columns from file names.
2. Profile a bounded sample and, when practical, row counts and key-quality checks. Record any incomplete scan or type coercion.
3. Define the question, grain, joins, filters, measures, date window, and expected output before writing SQL.
4. Prefer an available local analytical runtime such as DuckDB for CSV, Parquet, or JSON. If the requested runtime is unavailable, generate dialect-specific SQL and mark execution as untested instead of installing software or claiming success.
5. Use explicit columns, deterministic ordering when output order matters, guarded casts, clear date boundaries, and comments for non-obvious business rules.
6. Execute only read-only statements by default. Require explicit confirmation before creating tables, replacing files, attaching writable databases, or changing data.
7. Validate results with reconciliation checks, null and duplicate checks, boundary cases, and at least one independent aggregate when feasible.

# Resource Routing

Use local files and SQL runtimes already available in the execution environment. Remote warehouses, credentials, and network APIs are outside this Skill and require separate Connectors.

# Result Requirements

Return the data scope, dialect, SQL, execution status, row and column summary when executed, validation checks, assumptions, performance notes, and untested limitations. Never describe generated SQL as executed SQL.
