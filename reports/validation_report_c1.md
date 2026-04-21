# Validation report — C1 (T=0)

- **Predictions**: `openedx_predictions_c1_t0.json`
- **Golden**: `openedx_manual_classification.json` (manual classification)
- **Fields compared**: 133

## Degradation curve snapshot

Global accuracy (exact match) of every condition run against the same manual golden. **C1** highlighted.

| Condition | Accuracy |
|-----------|----------|
| **C0** | 91.73% |
| **C1** | 89.47% ← this report |
| **C2** | 88.72% |
| **C3** | 88.72% |

See `ablation_report.md` for the full curve with deltas and noise floor.

## Global accuracy

| Metric | Value |
|--------|-------|
| Exact match (subject + category) | **89.47%** |
| Category only | 89.47% |
| data_subject only | 93.23% |

## Accuracy by stratum (exact match)

| Stratum | n | correct | accuracy |
|---------|---|---------|----------|
| identity | 26 | 23 | 88.46% |
| academic | 21 | 20 | 95.24% |
| content | 29 | 27 | 93.10% |
| verification | 31 | 27 | 87.10% |
| operational | 26 | 22 | 84.62% |

## Metrics by sensitivity level

Levels and error definitions: see docstring of `scripts/sensitivity_levels.py` (canonical source). Levels: 0 = enterprise, 1 = non-sensitive personal, 2 = sensitive personal (Law 21.719).

| Metric | n | % |
|--------|---|---|
| Correct (exact category) | 119 | 89.47% |
| False positives — over-classification (predicted level > manual level) | 5 | 3.76% |
| False negatives — under-classification (predicted level < manual level) | 4 | 3.01% |
| Same-sensitivity error (different categories, same level) | 5 | 3.76% |
| No assigned level (mapping needs extension) | 0 | 0.00% |

| True level | support | correct | FP (over) | FN (under) | same-level |
|------------|---------|---------|-----------|------------|------------|
| 0 (enterprise) | 86 | 81 | 5 | 0 | 0 |
| 1 (non-sensitive personal) | 45 | 36 | 0 | 4 | 5 |
| 2 (sensitive) | 2 | 2 | 0 | 0 | 0 |

## Per-category metrics (one-vs-rest)

For each Fides category observed (in golden or predicted): support (n in golden), TP / cat_FP / cat_FN over the 133 fields, precision, recall, F1. Sorted by support desc.

> `cat_FP` / `cat_FN` are **per-category one-vs-rest counts** (`cat_FP` = fields predicted as this category with a different golden; `cat_FN` = fields whose golden = this category but were predicted as another). They feed per-category precision/recall/F1. **They are not the sensitivity false positives/negatives** from the previous section — see `scripts/sensitivity_levels.py`.

| category | support | TP | cat_FP | cat_FN | precision | recall | F1 |
|----------|---------|----|--------|--------|-----------|--------|-----|
| `system.operations` | 86 | 81 | 4 | 5 | 95.29% | 94.19% | 94.74% |
| `user.unique_id` | 16 | 16 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.authorization` | 8 | 5 | 1 | 3 | 83.33% | 62.50% | 71.43% |
| `user.content.private` | 7 | 6 | 1 | 1 | 85.71% | 85.71% | 85.71% |
| `user.name` | 3 | 3 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.account.settings` | 2 | 0 | 0 | 2 | N/A | 0.00% | N/A |
| `user.account.username` | 2 | 1 | 0 | 1 | 100.00% | 50.00% | 66.67% |
| `user.biometric` | 2 | 2 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.workplace` | 2 | 0 | 0 | 2 | N/A | 0.00% | N/A |
| `user.behavior` | 1 | 1 | 1 | 0 | 50.00% | 100.00% | 66.67% |
| `user.contact.email` | 1 | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.contact.url` | 1 | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.privacy_preferences` | 1 | 1 | 4 | 0 | 20.00% | 100.00% | 33.33% |
| `user.unique_id.pseudonymous` | 1 | 1 | 0 | 0 | 100.00% | 100.00% | 100.00% |
| `user.contact.address` | 0 | 0 | 1 | 0 | 0.00% | N/A | N/A |
| `user.contact.organization` | 0 | 0 | 1 | 0 | 0.00% | N/A | N/A |
| `user.payment` | 0 | 0 | 1 | 0 | 0.00% | N/A | N/A |

## Confusion matrix

See figure: `validation_confusion_matrix_c1.png` (row-normalized).

## Main error patterns

The most frequent error pattern is `user.authorization` - `system.operations` with 3 occurrences. Second pattern: `system.operations` - `user.privacy_preferences` (2 cases).

## Top 10 confusion pairs

| Actual (golden) | Predicted | n |
|-----------------|-----------|---|
| `user.authorization` | `system.operations` | 3 |
| `system.operations` | `user.privacy_preferences` | 2 |
| `user.account.settings` | `user.privacy_preferences` | 2 |
| `system.operations` | `user.payment` | 1 |
| `system.operations` | `user.behavior` | 1 |
| `user.content.private` | `system.operations` | 1 |
| `system.operations` | `user.content.private` | 1 |
| `user.account.username` | `user.authorization` | 1 |
| `user.workplace` | `user.contact.organization` | 1 |
| `user.workplace` | `user.contact.address` | 1 |

## Error examples per category

For each category we show up to 5 fields **predicted as this category with a different golden** (contributing to `cat_FP`) and up to 5 fields **with golden = this category, predicted as another** (contributing to `cat_FN`). Do not confuse with the sensitivity false positives/negatives — see the corresponding section and `scripts/sensitivity_levels.py`.

### `system.operations`

**Predicted as this category, different golden (4 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollment | mode | `user.authorization` | `system.operations` |
| CourseAccessRoleHistory | org | `user.authorization` | `system.operations` |
| ProgramCourseEnrollment | status | `user.authorization` | `system.operations` |
| Bookmark | course_key | `user.content.private` | `system.operations` |

**Golden = this category, predicted as another (5 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| LTIPIISignature | lti_tools_hash | `system.operations` | `user.privacy_preferences` |
| CourseEnrollmentAttribute | value | `system.operations` | `user.payment` |
| CourseTeamMembership | last_activity_at | `system.operations` | `user.behavior` |
| PhotoVerification | error_msg | `system.operations` | `user.content.private` |
| ApiAccessRequest | contacted | `system.operations` | `user.privacy_preferences` |

### `user.authorization`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Catalog | viewers | `user.account.username` | `user.authorization` |

**Golden = this category, predicted as another (3 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollment | mode | `user.authorization` | `system.operations` |
| CourseAccessRoleHistory | org | `user.authorization` | `system.operations` |
| ProgramCourseEnrollment | status | `user.authorization` | `system.operations` |

### `user.content.private`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| PhotoVerification | error_msg | `system.operations` | `user.content.private` |

**Golden = this category, predicted as another (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Bookmark | course_key | `user.content.private` | `system.operations` |

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

### `user.behavior`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseTeamMembership | last_activity_at | `system.operations` | `user.behavior` |

### `user.privacy_preferences`

**Predicted as this category, different golden (4 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| LTIPIISignature | lti_tools_hash | `system.operations` | `user.privacy_preferences` |
| PhotoVerification | display | `user.account.settings` | `user.privacy_preferences` |
| VerificationAttempt | hide_status_from_user | `user.account.settings` | `user.privacy_preferences` |
| ApiAccessRequest | contacted | `system.operations` | `user.privacy_preferences` |

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

### `user.payment`

**Predicted as this category, different golden (1 shown):**

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollmentAttribute | value | `system.operations` | `user.payment` |

## Errors by stratum (summary)

### identity (3 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseEnrollmentAttribute | value | SYSTEM/system.operations | USUARIO/user.payment |
| CourseEnrollment | mode | USUARIO/user.authorization | SYSTEM/system.operations |
| CourseAccessRoleHistory | org | USUARIO/user.authorization | SYSTEM/system.operations |

### academic (1 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| ProgramCourseEnrollment | status | USUARIO/user.authorization | SYSTEM/system.operations |

### content (2 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| CourseTeamMembership | last_activity_at | SYSTEM/system.operations | USUARIO/user.behavior |
| Bookmark | course_key | USUARIO/user.content.private | SYSTEM/system.operations |

### verification (4 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| LTIPIISignature | lti_tools_hash | SYSTEM/system.operations | USUARIO/user.privacy_preferences |
| PhotoVerification | display | USUARIO/user.account.settings | USUARIO/user.privacy_preferences |
| PhotoVerification | error_msg | SYSTEM/system.operations | USUARIO/user.content.private |
| VerificationAttempt | hide_status_from_user | USUARIO/user.account.settings | USUARIO/user.privacy_preferences |

### operational (4 errors)

| table | field | golden | predicted |
|-------|-------|--------|-----------|
| Catalog | viewers | USUARIO/user.account.username | USUARIO/user.authorization |
| ApiAccessRequest | company_name | USUARIO/user.workplace | USUARIO/user.contact.organization |
| ApiAccessRequest | company_address | USUARIO/user.workplace | USUARIO/user.contact.address |
| ApiAccessRequest | contacted | SYSTEM/system.operations | USUARIO/user.privacy_preferences |
