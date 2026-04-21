# Ablation report

Comparison of the 4 conditions (C0/C1/C2/C3) at `temperature=0` against the manual classification. Scope: 133 fields across 25 tables.

## Global degradation curve

| Condition | Description | n | correct | accuracy | Δ vs previous |
|-----------|-------------|---|---------|----------|---------------|
| **C0** | original code (with PII annotations) | 133 | 122 | **91.73%** |  |
| **C1** | no `.. pii*` annotations | 133 | 119 | **89.47%** | -2.26% |
| **C2** | no docstrings or comments | 133 | 118 | **88.72%** | -0.75% |
| **C3** | C2 + anonymized column names | 133 | 118 | **88.72%** | +0.00% |

See figure: `ablation_curve.png`

## Accuracy by stratum and condition

| Stratum | C0 | C1 | C2 | C3 |
|---------|------|------|------|------|
| identity | 96.15% (25/26) | 88.46% (23/26) | 92.31% (24/26) | 84.62% (22/26) |
| academic | 95.24% (20/21) | 95.24% (20/21) | 95.24% (20/21) | 95.24% (20/21) |
| content | 96.55% (28/29) | 93.10% (27/29) | 96.55% (28/29) | 96.55% (28/29) |
| verification | 83.87% (26/31) | 87.10% (27/31) | 80.65% (25/31) | 87.10% (27/31) |
| operational | 88.46% (23/26) | 84.62% (22/26) | 80.77% (21/26) | 80.77% (21/26) |

## Metrics by sensitivity level × condition

Counts per condition according to the canonical definition in `scripts/sensitivity_levels.py`. Levels: 0 = enterprise, 1 = non-sensitive personal, 2 = sensitive personal (Law 21.719). FP = over-classification (predicted level > manual level); FN = under-classification (predicted level < manual level); same-level = incorrect category, same level.

| Condition | correct | FP (over) | FN (under) | same-level | no-level |
|-----------|---------|-----------|------------|------------|----------|
| **C0** | 122 | 1 | 5 | 5 | 0 |
| **C1** | 119 | 5 | 4 | 5 | 0 |
| **C2** | 118 | 5 | 4 | 6 | 0 |
| **C3** | 118 | 4 | 4 | 7 | 0 |

## Recall per category × condition (one-vs-rest)

Recall = TP / support (how often the classifier gets the category right when the golden says it is that category). Sorted by support desc. See heatmap in `ablation_per_category.png`.

> `cat_FP` values are per-category one-vs-rest counts (fields predicted as this category but with a different golden). They are not the sensitivity false positives — see the previous section and `scripts/sensitivity_levels.py`.

| category | support | C0 | C1 | C2 | C3 |
|----------|---------|------|------|------|------|
| `system.operations` | 86 | 98.84% (cat_FP=5) | 94.19% (cat_FP=4) | 94.19% (cat_FP=4) | 95.35% (cat_FP=4) |
| `user.unique_id` | 16 | 93.75% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=1) | 100.00% (cat_FP=1) |
| `user.authorization` | 8 | 75.00% (cat_FP=1) | 62.50% (cat_FP=1) | 75.00% (cat_FP=1) | 50.00% (cat_FP=1) |
| `user.content.private` | 7 | 85.71% (cat_FP=1) | 85.71% (cat_FP=1) | 71.43% (cat_FP=2) | 71.43% (cat_FP=2) |
| `user.name` | 3 | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) |
| `user.account.settings` | 2 | 0.00% (cat_FP=0) | 0.00% (cat_FP=0) | 0.00% (cat_FP=0) | 50.00% (cat_FP=2) |
| `user.account.username` | 2 | 50.00% (cat_FP=0) | 50.00% (cat_FP=0) | 50.00% (cat_FP=0) | 50.00% (cat_FP=0) |
| `user.biometric` | 2 | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) |
| `user.workplace` | 2 | 0.00% (cat_FP=0) | 0.00% (cat_FP=0) | 0.00% (cat_FP=0) | 0.00% (cat_FP=0) |
| `user.behavior` | 1 | 100.00% (cat_FP=0) | 100.00% (cat_FP=1) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) |
| `user.contact.email` | 1 | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) |
| `user.contact.url` | 1 | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) | 100.00% (cat_FP=0) |
| `user.privacy_preferences` | 1 | 100.00% (cat_FP=2) | 100.00% (cat_FP=4) | 100.00% (cat_FP=4) | 100.00% (cat_FP=2) |
| `user.unique_id.pseudonymous` | 1 | 0.00% (cat_FP=0) | 100.00% (cat_FP=0) | 0.00% (cat_FP=0) | 0.00% (cat_FP=0) |

### Predicted categories that do not exist in the golden

These categories were never assigned by the manual labeler, yet the classifier used them at least once. They are spurious assignments (each occurrence adds to the category's `cat_FP`; their impact on the sensitivity metric depends on their level relative to the golden — see the level-metrics section).

| category | C0 (cat_FP) | C1 (cat_FP) | C2 (cat_FP) | C3 (cat_FP) |
|----------|------|------|------|------|
| `user.behavior.purchase_history` | 0 | 0 | 1 | 0 |
| `user.contact.address` | 1 | 1 | 1 | 1 |
| `user.contact.organization` | 1 | 1 | 1 | 1 |
| `user.payment` | 0 | 1 | 0 | 1 |

## Empirical noise floor (LLM stochasticity)

Tables `CourseAccessRoleHistory, StagedContentFile` have no `.. pii*` annotations, so their C0 and C1 code is **identical**. Any difference between the C0 and C1 predictions on these tables is pure model variance (even at temperature=0 there is residual non-determinism in the agent SDK tool calls).

- Fields compared: **12**
- `category` disagreements: 0 (0.0%)
- `data_subject` disagreements: 0 (0.0%)
- Noise floor (any disagreement): **0.0%** (0/12)

**Conclusion**: over the 12 fields where the input is identical between C0 and C1 (tables without PII annotations), predictions agreed 100% — floor = **0.0%**. This does **not** say that predictions are identical across conditions (they do differ, and that difference shows up as accuracy variation in the global table); it says that **given the same input, the model responds the same way**. Therefore the accuracy differences observed between C0/C1/C2/C3 **reflect the treatment effect** (removal of annotations, docstrings or names) and not model non-determinism.

## Per-field trace (when each prediction breaks)

For each field, ✓ = correct classification in that condition, ✗ = incorrect. `first_break` = first condition where the prediction breaks (transition ✓ - ✗).

### Fields that break at C0 - C1 (PII annotations effect)

| table | field | golden | trace (C0/C1/C2/C3) |
|-------|-------|--------|---------------------|
| LTIPIISignature | lti_tools_hash | SYSTEM/system.operations | ✓ ✗ ✓ ✓ |
| CourseEnrollmentAttribute | value | SYSTEM/system.operations | ✓ ✗ ✗ ✗ |
| CourseEnrollment | mode | USUARIO/user.authorization | ✓ ✗ ✓ ✗ |
| CourseTeamMembership | last_activity_at | SYSTEM/system.operations | ✓ ✗ ✓ ✓ |
| ApiAccessRequest | contacted | SYSTEM/system.operations | ✓ ✗ ✗ ✗ |

### Fields that break at C1 - C2 (docstring effect)

| table | field | golden | trace |
|-------|-------|--------|-------|
| IDVerificationAttempt | expiration_date | SYSTEM/system.operations | ✓ ✓ ✗ ✓ |
| PhotoVerification | receipt_id | USUARIO/user.unique_id.pseudonymous | ✗ ✓ ✗ ✗ |
| PhotoVerification | error_code | SYSTEM/system.operations | ✓ ✓ ✗ ✗ |
| StagedContentFile | data_file | USUARIO/user.content.private | ✓ ✓ ✗ ✗ |

### Fields that break at C2 - C3 (column name effect)

| table | field | golden | trace |
|-------|-------|--------|-------|
| CourseEnrollment | is_active | USUARIO/user.authorization | ✓ ✓ ✓ ✗ |

### Fields the classifier NEVER gets right

Possible causes: systematic classifier bias on these cases, or divergent criteria between manual and prompt.

| table | field | golden |
|-------|-------|--------|
| CourseAccessRoleHistory | org | USUARIO/user.authorization |
| ProgramCourseEnrollment | status | USUARIO/user.authorization |
| Bookmark | course_key | USUARIO/user.content.private |
| PhotoVerification | error_msg | SYSTEM/system.operations |
| VerificationAttempt | hide_status_from_user | USUARIO/user.account.settings |
| Catalog | viewers | USUARIO/user.account.username |
| ApiAccessRequest | company_name | USUARIO/user.workplace |
| ApiAccessRequest | company_address | USUARIO/user.workplace |

## Design limitations

- **Cumulative, not factorial, ablation**: the 4 conditions progressively remove signals in a fixed order (annotations - docstrings - names). The cell 'anonymized names with intact docstrings' (C0 + anon) is not measured.
- **Each gap is marginal and ordering-conditional**: the C2-C3 gap is read as 'effect of column name conditional on no docstrings', not as an independent contribution.
- **Residual lexical leakage in C3**: `unique_together`, `help_text`, `db_column`, `related_name`, `verbose_name`, method names remain preserved. C3 measures the loss of the name-token, not of all lexical signal.
- **Single-labeler golden**: manual labels come from a single person. A more robust golden would require inter-annotator agreement.
- **Noise floor at T=0**: even running at `temperature=0` there is residual non-determinism (agent SDK tool-call ordering). See the noise floor section.
