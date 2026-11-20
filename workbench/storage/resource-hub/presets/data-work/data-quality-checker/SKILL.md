---
name: "data-quality-checker"
description: "Provide the data quality checker workflow. Use when this capability is requested."
---

# Data Quality Checker

Validate CSV/JSON/JSONL data for quality issues. Pure Python, zero dependencies.

## Quick Start

```bash
# Full quality check
python3 scripts/check_data_quality.py data.csv

# JSON/JSONL support
python3 scripts/check_data_quality.py data.json
python3 scripts/check_data_quality.py data.jsonl

# Markdown report
python3 scripts/check_data_quality.py data.csv --format markdown

# JSON report (for CI/CD)
python3 scripts/check_data_quality.py data.csv --format json

# Only specific checks
python3 scripts/check_data_quality.py data.csv --checks missing,duplicates,types

# Only warnings and critical
python3 scripts/check_data_quality.py data.csv --severity warning

# Save report
python3 scripts/check_data_quality.py data.csv --format markdown --output report.md
```

## Schema Validation

```bash
# Generate schema from existing data
python3 scripts/check_data_quality.py data.csv --generate-schema schema.json

# Validate against schema
python3 scripts/check_data_quality.py data.csv --schema schema.json
```

## Checks Performed

| Check | Description | Severity |
|-------|-------------|----------|
| `missing` | Missing/null/empty values per column | info → critical |
| `duplicates` | Duplicate rows and potential ID conflicts | warning |
| `types` | Mixed data types within columns | info → warning |
| `outliers` | Statistical outliers via IQR method | info → warning |
| `formats` | Email/phone/URL/date format violations | warning |
| `whitespace` | Leading/trailing whitespace | info |
| `empty` | Entirely empty columns | warning |
| `drift` | Extra/missing keys across rows (schema drift) | warning |

## Quality Score

0-100 score based on weighted severity:
- **90-100**: Clean data, minor issues
- **70-89**: Usable but needs attention
- **50-69**: Significant issues
- **0-49**: Critical problems

## Exit Codes

- `0` — No warnings or critical issues
- `1` — Warnings found
- `2` — Critical issues found

Use in CI: `python3 scripts/check_data_quality.py data.csv || echo "Quality check failed"`

## Schema Format

JSON schema with validation rules:

```json
{
  "required": ["id", "email", "name"],
  "properties": {
    "id": {"type": "integer", "minimum": 1},
    "email": {"type": "string", "pattern": "^[^@]+@[^@]+\\.[^@]+$"},
    "age": {"type": "number", "minimum": 0, "maximum": 150},
    "status": {"type": "string", "enum": ["active", "inactive", "pending"]}
  }
}
```
