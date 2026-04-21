# Validation report — C2 (T=0)

- **Predictions**: `openedx_predictions_c2_t0.json`
- **Golden**: `openedx_manual_classification.json` (manual classification)
- **Fields compared**: 133

## Degradation curve snapshot

Global accuracy (exact match) of every condition run against the same manual golden. **C2** highlighted.

| Condition | Accuracy |
|-----------|----------|
| **C0** | 91.73% |
| **C1** | 89.47% |
| **C2** | 88.72% ← this report |
| **C3** | 88.72% |

See `ablation_report.md` for the full curve with deltas and noise floor.

## Global accuracy

| Metric | Value |
|--------|-------|
| Exact match (subject + category) | **88.72%** |
| Category only | 88.72% |
| data_subject only | 93.23% |

## Accuracy by stratum (exact match)

| Stratum | n | correct | accuracy |
|---------|---|---------|----------|
| identity | 26 | 24 | 92.31% |
| academic | 21 | 20 | 95.24% |
| content | 29 | 28 | 96.55% |
| verification | 31 | 25 | 80.65% |
| operational | 26 | 21 | 80.77% |

## Metrics by sensitivity level

Levels and error definitions: see docstring of `scripts/sensitivity_levels.py` (canonical source). Levels: 0 = enterprise, 1 = non-sensitive personal, 2 = sensitive personal (Law 21.719).

| Metric | n | % |
|--------|---|---|
| Correct (exact category) | 118 | 88.72% |
| False positives — over-classification (predicted level > manual level) | 5 | 3.76% |
| False negatives — under-classification (predicted level < manual level) | 4 | 3.01% |
| Same-sensitivity error (different categories, same level) | 6 | 4.51% |
| No assigned level (mapping needs extension) | 0 | 0.00% |

| True level | support | correct | FP (over) | FN (under) | same-level |
|------------|---------|---------|-----------|------------|------------|
| 0 (enterprise) | 86 | 81 | 5 | 0 | 0 |
| 1 (non-sensitive personal) | 45 | 35 | 0 | 4 | 6 |
| 2 (sensitive) | 2 | 2 | 0 | 0 | 0 |

## Per-category metrics (one-vs-rest)

For each Fides category observed (in golden or predicted): support (n in golden), TP / cat_FP / cat_FN over the 133 fields, precision, recall, F1. Sorted by support desc.

> `cat_FP` / `cat_FN` are **per-category one-vs-rest counts** (`cat_FP` = fields predicted as this category with a different golden; `cat_FN` = fields whose golden = this category but were predicted as another). They feed per-category precision/recall/F1. **They are not the sensitivity false positives/negatives** from the previous section — see `scripts/sensitivity_levels.py`.

| category | support | TP | cat_FP | cat_FN | precision | recall | F1 |
|----------|---------|----|--------|--------|-----------|--------|-----|
| `system.operations` | 86 | 81 | 4 | 5 | 95.29% | 94.19% | 94.74% |
| `user.unique_id` | 16 | 16 | 1 | 0 | 94.12% | 100.00% | 96.97% |
| `user.authorization` | 8 | 6 | 1 | 2 | 85.71% | 75.00% | 80.00% |
| `user.content.private` | 7 | 5 | 2 | 2 | 71.43% | 71.43% | 71.43% |
| `user.name` | 3 | 3 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.account.settings` | 2 | 0 | 0 | 2 | N/A | 0.00% | N/A |
| `user.account.username` | 2 | 1 | 0 | 1 | 100.00% | 50.00% | 66.67% |
| `user.biometric` | 2 | 2 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.workplace` | 2 | 0 | 0 | 2 | N/A | 0.00% | N/A |
| `user.behavior` | 1 | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.contact.email` | 1 | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.contact.url` | 1 | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.privacy_preferences` | 1 | 1 | 4 | 0 | 20.00% | 100.00% | 33.33% |
| `user.unique_id.pseudonymous` | 1 | 0 | 0 | 1 | N/A | 0.00% | N/A |
| `user.behavior.purchase_history` | 0 | 0 | 1 | 0 | 0.00% | N/A | N/A |
| `user.contact.address` | 0 | 0 | 1 | 0 | 0.00% | N/A | N/A |
| `user.contact.organization` | 0 | 0 | 1 | 0 | 0.00% | N/A | N/A |

## Confusion matrix

See figure: `validation_confusion_matrix_c2.png` (row-normalized).

## Main error patterns

The most frequent error pattern is `user.authorization` - `system.operations` with 2 occurrences. Second pattern: `user.content.private` - `system.operations` (2 cases).

## Top 10 confusion pairs

| Actual (golden) | Predicted | n |
|-----------------|-----------|---|
| `user.authorization` | `system.operations` | 2 |
| `user.content.private` | `system.operations` | 2 |
| `system.operations` | `user.privacy_preferences` | 2 |
| `user.account.settings` | `user.privacy_preferences` | 2 |
| `system.operations` | `user.content.private` | 2 |
| `system.operations` | `user.behavior.purchase_history` | 1 |
| `user.unique_id.pseudonymous` | `user.unique_id` | 1 |
| `user.account.username` | `user.authorization` | 1 |
| `user.workplace` | `user.contact.organization` | 1 |
| `user.workplace` | `user.contact.address` | 1 |

## Error examples per category

For each category we show up to 5 fields **predicted as this category with a different golden** (contributing to `cat_FP`) and up to 5 fields **with golden = this category, predicted as another** (contributing to `cat_FN`). Do not confuse with the sensitivity false positives/negatives — see the corresponding section and `scripts/sensitivity_levels.py`.

### `system.operations`

**Predicted as this category, different golden (4 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseAccessRoleHistory | org | `user.authorization` | `system.operations` |
| ProgramCourseEnrollment | status | `user.authorization` | `system.operations` |
| Bookmark | course_key | `user.content.private` | `system.operations` |
| StagedContentFile | data_file | `user.content.private` | `system.operations` |

**Golden = this category, predicted as another (5 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollmentAttribute | value | `system.operations` | `user.behavior.purchase_history` |
| IDVerificationAttempt | expiration_date | `system.operations` | `user.privacy_preferences` |
| PhotoVerification | error_msg | `system.operations` | `user.content.private` |
| PhotoVerification | error_code | `system.operations` | `user.content.private` |
| ApiAccessRequest | contacted | `system.operations` | `user.privacy_preferences` |

### `user.unique_id`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| PhotoVerification | receipt_id | `user.unique_id.pseudonymous` | `user.unique_id` |

### `user.authorization`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Catalog | viewers | `user.account.username` | `user.authorization` |

**Golden = this category, predicted as another (2 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseAccessRoleHistory | org | `user.authorization` | `system.operations` |
| ProgramCourseEnrollment | status | `user.authorization` | `system.operations` |

### `user.content.private`

**Predicted as this category, different golden (2 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| PhotoVerification | error_msg | `system.operations` | `user.content.private` |
| PhotoVerification | error_code | `system.operations` | `user.content.private` |

**Golden = this category, predicted as another (2 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Bookmark | course_key | `user.content.private` | `system.operations` |
| StagedContentFile | data_file | `user.content.private` | `system.operations` |

### `user.account.settings`

**Golden = this category, predicted as another (2 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| PhotoVerification | display | `user.account.settings` | `user.privacy_preferences` |
| VerificationAttempt | hide_status_from_user | `user.account.settings` | `user.privacy_preferences` |

### `user.account.username`

**Golden = this category, predicted as another (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Catalog | viewers | `user.account.username` | `user.authorization` |

### `user.workplace`

**Golden = this category, predicted as another (2 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| ApiAccessRequest | company_name | `user.workplace` | `user.contact.organization` |
| ApiAccessRequest | company_address | `user.workplace` | `user.contact.address` |

### `user.privacy_preferences`

**Predicted as this category, different golden (4 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| IDVerificationAttempt | expiration_date | `system.operations` | `user.privacy_preferences` |
| PhotoVerification | display | `user.account.settings` | `user.privacy_preferences` |
| VerificationAttempt | hide_status_from_user | `user.account.settings` | `user.privacy_preferences` |
| ApiAccessRequest | contacted | `system.operations` | `user.privacy_preferences` |

### `user.unique_id.pseudonymous`

**Golden = this category, predicted as another (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| PhotoVerification | receipt_id | `user.unique_id.pseudonymous` | `user.unique_id` |

### `user.behavior.purchase_history`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollmentAttribute | value | `system.operations` | `user.behavior.purchase_history` |

### `user.contact.address`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| ApiAccessRequest | company_address | `user.workplace` | `user.contact.address` |

### `user.contact.organization`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| ApiAccessRequest | company_name | `user.workplace` | `user.contact.organization` |

## Errors by stratum (summary)

### identity (2 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollmentAttribute | value | SYSTEM/system.operations | USUARIO/user.behavior.purchase_history |
| CourseAccessRoleHistory | org | USUARIO/user.authorization | SYSTEM/system.operations |

### academic (1 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| ProgramCourseEnrollment | status | USUARIO/user.authorization | SYSTEM/system.operations |

### content (1 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Bookmark | course_key | USUARIO/user.content.private | SYSTEM/system.operations |

### verification (6 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| IDVerificationAttempt | expiration_date | SYSTEM/system.operations | USUARIO/user.privacy_preferences |
| PhotoVerification | receipt_id | USUARIO/user.unique_id.pseudonymous | USUARIO/user.unique_id |
| PhotoVerification | display | USUARIO/user.account.settings | USUARIO/user.privacy_preferences |
| PhotoVerification | error_msg | SYSTEM/system.operations | USUARIO/user.content.private |
| PhotoVerification | error_code | SYSTEM/system.operations | USUARIO/user.content.private |
| VerificationAttempt | hide_status_from_user | USUARIO/user.account.settings | USUARIO/user.privacy_preferences |

### operational (5 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Catalog | viewers | USUARIO/user.account.username | USUARIO/user.authorization |
| ApiAccessRequest | company_name | USUARIO/user.workplace | USUARIO/user.contact.organization |
| ApiAccessRequest | company_address | USUARIO/user.workplace | USUARIO/user.contact.address |
| ApiAccessRequest | contacted | SYSTEM/system.operations | USUARIO/user.privacy_preferences |
| StagedContentFile | data_file | USUARIO/user.content.private | SYSTEM/system.operations |
