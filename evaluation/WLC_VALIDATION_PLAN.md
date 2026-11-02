# WLC Validation Plan — Frozen Before Grading

## Purpose

The validation split is used only to select the WLC weights.
The frozen test split must not be run until the validation winner
has been selected and frozen.

## Query split

- Validation: 30 frozen queries.
- Test: 70 frozen queries.
- Pilot queries are excluded from both splits.

## WLC grid

Eleven weight combinations are evaluated:

| Semantic | Ingredient efficiency |
|---:|---:|
| 0.0 | 1.0 |
| 0.1 | 0.9 |
| 0.2 | 0.8 |
| 0.3 | 0.7 |
| 0.4 | 0.6 |
| 0.5 | 0.5 |
| 0.6 | 0.4 |
| 0.7 | 0.3 |
| 0.8 | 0.2 |
| 0.9 | 0.1 |
| 1.0 | 0.0 |

Retrieval is fixed at Top-50 semantic candidates plus at most
20 additional keyword candidates. The same candidate pool and
semantic normalization are reused for all WLC configurations of
a query.

## Final relevance validation

T_relevansi is applied to each candidate before Top-5 selection.
A candidate that does not pass T_relevansi is not eligible for
the displayed Top-5 under any WLC configuration.

## Blind candidate pooling

For every validation query:

1. Each WLC configuration produces its Top-5.
2. The union of all Top-5 candidates is taken.
3. Duplicate recipe IDs are removed.
4. System score, WLC configuration, and original rank are hidden.
5. The unique pooled candidates are randomized independently
   for grading pass 1 and pass 2.
6. Relevance grades follow the frozen 0/1/2 grading rubric.

This prevents the evaluator from knowing which configuration
retrieved a candidate.

## Reconciliation

Pass-1 and pass-2 disagreements are reviewed without exposing
WLC configuration, score, or original rank. The resolved grade
becomes the final relevance label for that query–recipe pair.

## Validation metrics

Each WLC configuration is evaluated using:

- Acceptable Success@5
- Strong Success@5
- Acceptable Precision@5
- Strong Precision@5
- pooled nDCG@5
- Mean Grade@5

For pooled nDCG@5, IDCG@5 is constructed from the five highest
grades available in the complete judged candidate pool for that
query. Therefore a configuration is penalized if it fails to
place highly graded pooled candidates in its own Top-5.

## Precommitted WLC selection rule

The winning WLC configuration is selected by the following
descending priority, fixed before blind grading results are seen:

1. Mean pooled nDCG@5
2. Strong Precision@5
3. Strong Success@5
4. Acceptable Precision@5
5. Acceptable Success@5
6. Mean Grade@5
7. Higher semantic weight, only as a deterministic final tie-break

After selection, the winning WLC weights are frozen.
Only then may the 70-query frozen test split be executed.
