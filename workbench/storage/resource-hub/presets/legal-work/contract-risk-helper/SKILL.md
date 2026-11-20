---
name: contract-risk-helper
description: "Scan supplied Chinese or English contract text for common clause risks, classify severity, and suggest negotiation points. Use for preliminary offline risk spotting before qualified legal review."
---

# Contract Risk Helper

Perform read-only local pattern matching on contract text. The result is preliminary issue spotting, not legal advice, and must not replace review by a qualified lawyer familiar with the full facts and current jurisdiction.

## Workflow

1. Accept contract text supplied in the task; do not transmit or persist it.
2. Run `handler.py` or use its pattern categories to identify common issues.
3. Group findings by severity and clause category, citing the matched passage.
4. Explain why each clause may matter and propose a bounded negotiation or drafting question.
5. State false-positive risks, missing context, governing-law uncertainty, and the need for professional review.

## Supported Categories

- Liability: unlimited liability or broad indemnification.
- Termination: automatic renewal, missing convenience termination, or excessive notice.
- Dispute resolution: one-sided or unsuitable venue.
- Payment: extended terms or missing late-payment treatment.
- Intellectual property: broad work-product or background-rights transfer.
- Confidentiality: perpetual duties or overly broad definitions.
- Delivery: unclear scope, service levels, or acceptance criteria.

Read `references/common-risks.md` when detailed patterns or negotiation notes are needed.

## Boundaries and Results

Do not make final enforceability conclusions, invent missing clauses, execute commands beyond the bundled scanner, or modify the source contract. Return the findings, severity, evidence passage, suggested question, uncertainty, and legal-review reminder.

