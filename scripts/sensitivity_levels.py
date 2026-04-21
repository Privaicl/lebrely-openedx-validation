"""Sensitivity levels (canonical definition).

Simplification based on Law 21.719 (Chile), used by the evaluation
pipeline and by the validation reports. Single source of truth: this
module. Any report or document that discusses "levels" or false
positives/negatives in the sense of data sensitivity must refer to this
file.

Levels:
    0  — Enterprise data (lowest sensitivity).
    1  — Personal data not listed as sensitive by the law.
    2  — Sensitive personal data under Law 21.719 (highest sensitivity).

Error terminology (used in the validation reports):
    - Correct:                 predicted category = manual category.
    - False positive (FP):     predicted sensitivity level > manual sensitivity level (over-classification).
    - False negative (FN):     predicted sensitivity level < manual sensitivity level (under-classification).
    - Same-sensitivity error:  different categories, same sensitivity level.

NOTE: the reports also show `cat_FP` / `cat_FN` columns. Those refer to
per-category one-vs-rest counts used to compute precision/recall/F1.
They are not the sensitivity FP/FN defined above — they are a different
metric artifact and are labeled separately to avoid confusion.
"""

from __future__ import annotations

UNKNOWN = -1

# Level 0 — enterprise data. Anything starting with "system." falls here
# via `level_of`.
LEVEL_0_PREFIX = "system"

# Level 2 — sensitive personal data under Law 21.719, Art. 2 lit. g:
# ethnic or racial origin, political / union / trade-association
# affiliation, religious / philosophical convictions, health data, human
# biological profile (biometric, genetic), sex life, sexual orientation.
# In addition, data concerning children and adolescents is included.
LEVEL_2: frozenset[str] = frozenset({
    # Biometric
    "user.biometric",
    "user.biometric.fingerprint",
    "user.biometric.health",
    "user.biometric.retinal",
    "user.biometric.voice",
    "user.authorization.biometric",
    # Health and medical / genetic data
    "user.health_and_medical",
    "user.health_and_medical.genetic",
    "user.health_and_medical.insurance_beneficiary_id",
    "user.health_and_medical.record_id",
    # Criminal / investigative data
    "user.criminal_history",
    # Convictions, opinions and affiliation, gender
    "user.demographic.gender",
    "user.demographic.political_opinion",
    "user.demographic.race_ethnicity",
    "user.demographic.religious_belief",
    "user.demographic.sexual_orientation",
    # Children and adolescents
    "user.childrens",
})


def level_of(category: str) -> int:
    """Return the sensitivity level (0/1/2) for a Fides category, or
    UNKNOWN (-1) if it cannot be determined."""
    if not category:
        return UNKNOWN
    if category == LEVEL_0_PREFIX or category.startswith(LEVEL_0_PREFIX + "."):
        return 0
    if category in LEVEL_2:
        return 2
    if category == "user" or category.startswith("user."):
        return 1
    return UNKNOWN
