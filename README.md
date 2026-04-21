# Lebrely, Validación sobre Open edX

*"Clasificación automática de datos con LLMs bajo Ley 21.719: caso Open edX"*.

Se puede encontrar el abstract asociado en [`abstract.md`](abstract.md).

## Sobre este repositorio

Lebrely es el clasificador automático de datos de [Privai](https://privai.cl). Este repositorio documenta un protocolo reproducible para validar su desempeño sobre un dominio público (Open edX, LMS open-source usado por instituciones educativas estatales chilenas) y contiene los datos y resultados del experimento reportado en el abstract.

## Qué hay

| Carpeta | Contenido |
|---------|-----------|
| [`scripts/`](scripts/) | Scripts del experimento (Python). Ver detalle abajo. |
| [`data/`](data/) | Inventario de modelos Django de Open edX, muestra estratificada, y los modelos extraídos (input del clasificador). |
| [`classification/`](classification/) | Golden dataset (clasificación manual ciega) + predicciones del clasificador a `temperature=0` en las 4 condiciones (C0, C1, C2, C3). |
| [`reports/`](reports/) | Reporte de ablación, reportes de validación por condición, matrices de confusión y figuras. |

## Qué NO hay

**El clasificador Lebrely (`app/` en el repo privado de Privai) y el prompt de dominio (`openedx_prompt.OPENEDX_PROMPT`) no están incluidos.** Son productos comerciales de Privai. Los scripts que orquestan la clasificación (`usage_analysis_agent.py`, `ablation.py`) contienen imports privados que no resuelven fuera del entorno de Privai — `from app. ...` (el clasificador) y `from openedx_prompt import OPENEDX_PROMPT` (el prompt). Se publican con los nombres visibles para transparencia metodológica, pudiendo observarse la lógica de orquestación y las transformaciones de ablación, pero no re-ejecutar la clasificación.

Los scripts de análisis (`compare_and_evaluate.py`, `ablation_report.py`, `stratify_and_sample.py`, `extract_models.py`) SÍ corren sin Lebrely y permiten reproducir todas las tablas y figuras del abstract a partir de las predicciones ya almacenadas.

## Setup

Requiere Python 3.10+. Instalar dependencias:

```
pip install -r requirements.txt
```

`extract_models.py` adicionalmente requiere un checkout local de Open edX (`edx-platform`) y la variable de entorno `OPENEDX_REPO` apuntando a él:

```
export OPENEDX_REPO=/ruta/a/edx-platform
```

Los otros tres scripts de análisis no requieren `OPENEDX_REPO`: leen los artefactos ya almacenados en `data/` y `classification/`, y regeneran los reportes y figuras bajo `reports/`.

## Verificación del Clasificador (resumen)

1. **Inventario** (`scripts/extract_models.py`): parsea todos los `models.py` de Open edX con tree-sitter y extrae 272 modelos Django, `data/openedx_inventory.csv` y `data/openedx_models.json`.
2. **Estratificación y muestra** (`scripts/stratify_and_sample.py`): produce `data/openedx_sample.csv`.

   - **2a. Asignación de estrato.** Cada modelo Django se asigna a 1 de 5 estratos vía un mapping explícito `django_app > estrato` (22 apps nombradas). Apps que no aparecen en el mapping caen en el estrato `operational` por defecto. Estratos y apps:
     - **identity**: `student`, `user_api`, `third_party_auth`, `external_user_ids`, `user_tours`.
     - **academic**: `courseware`, `certificates`, `credit`, `grades`, `program_enrollments`, `course_modes`, `entitlements`, `course_goals`.
     - **content**: `bulk_email`, `django_comment_common`, `discussions`, `notifications`, `bookmarks`, `teams`, `survey`.
     - **verification**: `verify_student`, `agreements`.
     - **operational**: todo lo demás (site_configuration, oauth_dispatch, schedules, commerce, etc.).
   - **2b. Cuota por estrato.** 5 tablas × aprox 4 campos = **aprox 20 campos por estrato, aprox 100 campos totales sobre 25 tablas**. Cuotas fijas, no proporcionales: así ningún estrato domina (demasiado) la comparación por tamaño. En la práctica, la clasificación manual y la automática se evaluaron sobre **todos los campos** de las 25 tablas muestreadas, no sólo los 4 seleccionados al azar. Esas 25 tablas suman en total **133 campos**, que es el scope final del golden y del report de ablación.
   - **2c. Filtro de elegibilidad.** Para esta demo se consideran tablas con al menos 4 campos (las más chicas no aportan la cuota completa).
   - **2d. Muestreo aleatorio.** `random.Random(seed=42)`. Por cada estrato: `rng.sample(elegibles, 5)` para las tablas, luego `rng.sample(fields, 4)` por tabla. El seed fijo hace la muestra reproducible.
3. **Clasificación manual ciega** (`classification/openedx_manual_classification.json`): 133 campos etiquetados contra taxonomía Fides.

4. **Clasificación automática en 4 condiciones de ablación** (`scripts/usage_analysis_agent.py` + `scripts/ablation.py`, con Lebrely): `classification/openedx_predictions_c{0,1,2,3}_t0.json`. Las transformaciones:
   - **C0** — código original.
   - **C1** — regex-strip de anotaciones `.. pii*` en docstrings.
   - **C2** — eliminación completa de docstrings y comentarios (AST walk).
   - **C3** — C2 + renombre de columnas a `col_1, col_2, ...` (preserva tipos, FKs).
5. **Comparación golden vs predicciones** (`scripts/compare_and_evaluate.py`): `reports/validation_report_c{0,1,2,3}.md` + matrices de confusión.
6. **Reporte de ablación** (`scripts/ablation_report.py`): `reports/ablation_report.md` + curva de degradación + heatmap por categoría.

## Resultados principales (temperature=0)

| Condición | Accuracy | Δ vs anterior |
|-----------|----------|---------------|
| **C0** (con anotaciones PII) | 91.73% | — |
| **C1** (sin `.. pii*` — baseline honesta) | **89.47%** | −2.26 pp |
| **C2** (sin docstrings ni comentarios) | 88.72% | −0.75 pp |
| **C3** (C2 + nombres anonimizados) | 88.72% | 0.00 pp |

Detalles completos en [`reports/ablation_report.md`](reports/ablation_report.md).

## Licencia

Ver [`LICENSE`](LICENSE). Scripts bajo MIT, datos/reportes bajo CC-BY-4.0. `data/openedx_models.json` incluye código extraído de Open edX (AGPL-3.0 upstream), citado por completitud metodológica.

---

# Lebrely, Validation on Open edX

*"Automated data classification with LLMs under Law 21.719: Open edX case"*.

The associated abstract can be found at [`abstract.md`](abstract.md).

## About this repository

Lebrely is [Privai](https://privai.cl)'s automated data classifier. This repository documents a reproducible protocol to validate its performance on a public domain (Open edX, an open-source LMS used by Chilean state-run educational institutions) and contains the data and results of the experiment reported in the abstract.

## What is here

| Folder | Contents |
|--------|----------|
| [`scripts/`](scripts/) | Experiment scripts (Python). See detail below. |
| [`data/`](data/) | Inventory of Open edX Django models, stratified sample, and extracted models (classifier input). |
| [`classification/`](classification/) | Golden dataset (blind manual classification) + classifier predictions at `temperature=0` across the 4 conditions (C0, C1, C2, C3). |
| [`reports/`](reports/) | Ablation report, per-condition validation reports, confusion matrices and figures. |

## What is NOT here

**The Lebrely classifier (`app/` in the private Privai repo) and the domain prompt (`openedx_prompt.OPENEDX_PROMPT`) are not included.** Both are Privai commercial products. The scripts that orchestrate the classification (`usage_analysis_agent.py`, `ablation.py`) contain private imports that do not resolve outside the Privai environment — `from app. ...` (the classifier) and `from openedx_prompt import OPENEDX_PROMPT` (the prompt). They are published with names visible for methodological transparency — the orchestration logic and the ablation transformations can be inspected, but the classification cannot be re-executed.

The analysis scripts (`compare_and_evaluate.py`, `ablation_report.py`, `stratify_and_sample.py`, `extract_models.py`) DO run without Lebrely and can reproduce all tables and figures in the abstract from the stored predictions.

## Setup

Requires Python 3.10+. Install dependencies:

```
pip install -r requirements.txt
```

`extract_models.py` additionally requires a local checkout of Open edX (`edx-platform`) and the environment variable `OPENEDX_REPO` pointing to it:

```
export OPENEDX_REPO=/path/to/edx-platform
```

The other three analysis scripts do not require `OPENEDX_REPO`: they read the artefacts already stored under `data/` and `classification/`, and regenerate the reports and figures under `reports/`.

## Classifier verification (summary)

1. **Inventory** (`scripts/extract_models.py`): parses every `models.py` under Open edX with tree-sitter and extracts 272 Django models, `data/openedx_inventory.csv` and `data/openedx_models.json`.
2. **Stratification and sampling** (`scripts/stratify_and_sample.py`): produces `data/openedx_sample.csv`.

   - **2a. Stratum assignment.** Each Django model is assigned to one of 5 strata via an explicit `django_app > stratum` mapping (22 named apps). Apps not present in the mapping fall into the default `operational` stratum. Strata and apps:
     - **identity**: `student`, `user_api`, `third_party_auth`, `external_user_ids`, `user_tours`.
     - **academic**: `courseware`, `certificates`, `credit`, `grades`, `program_enrollments`, `course_modes`, `entitlements`, `course_goals`.
     - **content**: `bulk_email`, `django_comment_common`, `discussions`, `notifications`, `bookmarks`, `teams`, `survey`.
     - **verification**: `verify_student`, `agreements`.
     - **operational**: everything else (site_configuration, oauth_dispatch, schedules, commerce, etc.).
   - **2b. Per-stratum quota.** 5 tables × ~4 fields = **~20 fields per stratum, ~100 fields total across 25 tables**. Fixed, non-proportional quotas: that way no single stratum dominates the comparison by size. In practice, both the manual and the automatic classification were evaluated on **every field** of the 25 sampled tables, not only the 4 randomly selected per table. Those 25 tables add up to **133 fields** in total, which is the final scope of the golden dataset and of the ablation report.
   - **2c. Eligibility filter.** For this demo we consider tables with at least 4 fields (smaller ones cannot satisfy the full quota).
   - **2d. Random sampling.** `random.Random(seed=42)`. For each stratum: `rng.sample(eligible, 5)` for tables, then `rng.sample(fields, 4)` per table. The fixed seed makes the sample reproducible.
3. **Blind manual classification** (`classification/openedx_manual_classification.json`): 133 fields labeled against the Fides taxonomy.

4. **Automatic classification in 4 ablation conditions** (`scripts/usage_analysis_agent.py` + `scripts/ablation.py`, with Lebrely): `classification/openedx_predictions_c{0,1,2,3}_t0.json`. The transformations:
   - **C0** — original code.
   - **C1** — regex-strip of `.. pii*` annotations in docstrings.
   - **C2** — full removal of docstrings and comments (AST walk).
   - **C3** — C2 + column renaming to `col_1, col_2, ...` (preserving types, FKs).
5. **Golden vs. predictions comparison** (`scripts/compare_and_evaluate.py`): `reports/validation_report_c{0,1,2,3}.md` + confusion matrices.
6. **Ablation report** (`scripts/ablation_report.py`): `reports/ablation_report.md` + degradation curve + per-category heatmap.

## Main results (temperature=0)

| Condition | Accuracy | Δ vs previous |
|-----------|----------|---------------|
| **C0** (with PII annotations) | 91.73% | — |
| **C1** (no `.. pii*` — honest baseline) | **89.47%** | −2.26 pp |
| **C2** (no docstrings or comments) | 88.72% | −0.75 pp |
| **C3** (C2 + anonymized names) | 88.72% | 0.00 pp |

Full details in [`reports/ablation_report.md`](reports/ablation_report.md).

## License

See [`LICENSE`](LICENSE). Scripts under MIT, data/reports under CC-BY-4.0. `data/openedx_models.json` includes code extracted from Open edX (AGPL-3.0 upstream), cited for methodological completeness.
