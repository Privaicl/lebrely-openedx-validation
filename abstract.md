# Clasificación automática de datos con LLMs bajo Ley 21.719: caso Open edX

**Fecha:** 2026-04-18

**Categoría:** Estudios de campo de tecnología de privacidad, Funcionalidad y diseño innovadores de privacidad, Principios fundamentales de privacidad usable.

## Contexto

La mayoría de las organizaciones no sabe qué datos tiene ni dónde. Esto es preocupante considerando que mantener inventario actualizado de datos personales es fundamental para cumplir con la Ley 21.719. El problema es operacional: los sistemas reales tienen miles de campos, nomenclatura inconsistente y documentación incompleta. La escala hace que un inventario manual sea inviable para gran parte de las organizaciones chilenas. Surge la pregunta de si métodos basados en LLM pueden automatizar la tarea manteniendo buena calidad sobre sistemas reales.

En este trabajo se presenta un protocolo de validación reproducible aplicado al Clasificador de datos de Privai, Lebrely (en producción). Para demostración, se construyó un golden dataset abierto sobre Open edX (open source, utilizado en plataformas educativas chilenas, estatales) y se midió el desempeño bajo una ablación que simula reducción progresiva del input documental. En un caso B2B previo en salud privada, Lebrely alcanzó 85.96% sobre 2.173 campos; este trabajo evalúa generalización a un dominio distinto.

## Metodología

Muestreo estratificado reproducible sobre apps Django de Open edX: 25 tablas, 133 campos. Primero, clasificación manual contra la taxonomía Fides, sin acceso a las predicciones automáticas. Luego, clasificaciones automáticas (temperatura=0) en cuatro condiciones:

- **C0** — código original.
- **C1** — sin anotaciones PII.
- **C2** — sin docstrings ni comentarios.
- **C3** — nombres de columna no informativos.

## Resultados

91.73% de exact match en C0 y 89.47% en C1, comparable al caso B2B previo sobre un dataset distinto. Al remover docstrings (C2) el método mantiene 88.72%, con caída total de sólo 3.01 pp desde C0. C3 iguala a C2 (88.72%): posiblemente el análisis de uso del agente y las señales estructurales preservadas (tipos, FKs) bastan cuando los nombres no son informativos. Este es un test de robustez ante input directo reducido, no ante documentación degradada en todo el sistema.

Operacionalmente, los 133 campos se clasifican en 24 min 30 seg vs. ~3h manuales, una reducción de ~7× que se amplifica a miles de campos.

## Hallazgos

Los campos biométricos clasificados, críticos bajo Ley 21.719, alcanzan 100% precisión y recall en las cuatro condiciones. La confusión dominante ocurre entre categorías adyacentes de Fides (por ejemplo, `user.workplace` con `user.contact.organization`/`address`), no entre distantes. El patrón sugiere que la brecha restante refleja en parte ambigüedad de la taxonomía, no sólo error del modelo.

## Alcance

La ablación transforma sólo el código pasado al clasificador; el repositorio donde el agente hace análisis de uso queda intacto. Los gaps miden desempeño en modo productivo ante reducción de input directo. La validación sobre documentación degradada en todo el sistema requiere experimentación adicional. El golden se realizó con etiquetador único, al igual que la clasificación automática.

## Disponibilidad de datos

Golden dataset, scripts, predicciones y análisis en repositorio abierto. El funcionamiento general del clasificador es público. El detalle de la implementación es producto comercial separado.

## Implicancias

Los resultados obtenidos del clasificador, en los escenarios estudiados, son prometedores. Lebrely clasifica correctamente datos personales en un dominio distinto al caso B2B previo, con accuracy consistente y robustez ante degradación del input. Esto sugiere que la automatización del inventario de datos es técnicamente viable para organizaciones que enfrentan el desafío operacional descrito. Queda pendiente, como trabajo futuro, explorar mayor variabilidad de dominio, calidad de código y realidades organizativas para evaluar la generalización de la herramienta.

---

# Automated data classification with LLMs under Law 21.719: Open edX case

**Date:** 2026-04-18

**Category:** Field studies of privacy technology, Innovative privacy functionality and design, Foundational principles of usable privacy.

## Context

Most organizations do not know what data they hold or where. This is concerning given that keeping an up-to-date inventory of personal data is foundational to compliance with Law 21.719. The problem is operational: real systems have thousands of fields, inconsistent naming and incomplete documentation. The scale makes a manual inventory unfeasible for most Chilean organizations. The question arises whether LLM-based methods can automate the task while preserving good quality on real systems.

This work presents a reproducible validation protocol applied to Privai's data classifier, Lebrely (in production). For demonstration, an open golden dataset was built over Open edX (open source, used on Chilean, state-run educational platforms) and performance was measured under an ablation that simulates progressive reduction of the documentary input. In a previous B2B case in private healthcare, Lebrely reached 85.96% over 2,173 fields; this work evaluates generalization to a different domain.

## Methodology

Reproducible stratified sampling over Open edX Django apps: 25 tables, 133 fields. First, manual classification against the Fides taxonomy, with no access to the automatic predictions. Then, automatic classifications (temperature=0) under four conditions:

- **C0** — original code.
- **C1** — no PII annotations.
- **C2** — no docstrings or comments.
- **C3** — non-informative column names.

## Results

91.73% exact match in C0 and 89.47% in C1, comparable to the previous B2B case over a different dataset. Removing docstrings (C2) the method maintains 88.72%, with a total drop of only 3.01 pp from C0. C3 matches C2 (88.72%): plausibly the agent's usage analysis and the preserved structural signals (types, FKs) suffice when names are not informative. This is a robustness test against reduced direct input, not against documentation degraded across the whole system.

Operationally, the 133 fields are classified in 24 min 30 sec vs. ~3 h manually, a ~7× reduction that scales up as the field count grows.

## Findings

Classified biometric fields, critical under Law 21.719, reach 100% precision and recall across the four conditions. The dominant confusion occurs between adjacent Fides categories (e.g., `user.workplace` with `user.contact.organization`/`address`), not between distant ones. The pattern suggests that the remaining gap partly reflects taxonomy ambiguity, not only model error.

## Scope

The ablation transforms only the code passed to the classifier; the repository where the agent performs usage analysis is left intact. The gaps measure production-mode performance under reduced direct input. Validation against documentation degraded across the whole system requires additional experimentation. The golden was produced by a single labeler, as was the automatic classification.

## Data availability

Golden dataset, scripts, predictions and analysis in an open repository. The general operation of the classifier is public. The implementation detail is a separate commercial product.

## Implications

The results obtained from the classifier, in the scenarios studied, are promising. Lebrely correctly classifies personal data in a domain different from the previous B2B case, with consistent accuracy and robustness against input degradation. This suggests that data-inventory automation is technically viable for organizations facing the operational challenge described. Future work remains to explore greater variability of domain, code quality and organizational realities in order to evaluate the tool's generalization.
