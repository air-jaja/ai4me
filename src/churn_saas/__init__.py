"""B2B SaaS churn prediction - CISIA certification deliverable.

Code is organised by **lifecycle activity** rather than by object type:

    donnees/           1. Data management       - bronze -> silver -> gold
    features/          2. Feature control       - construction and guardrails
    modelisation/      3. Modelling             - baseline and selection
    evaluation/        4. Evaluation            - metrics, decision rule, impact
    packaging/         5. Packaging             - artefacts and model card
    industrialisation/ 6. Industrialisation     - monthly batch and service
    monitoring/        7. Monitoring            - drift and alerting

One activity, one package, one test file. Locating the code behind a project step
requires no knowledge of the implementation.

Language convention: comments and docstrings are written in English. Rendered content
(markdown, figure titles, table labels, printed messages) stays in French, since the
deliverable is read by a French-speaking jury.
"""

__version__ = "1.0.0"
