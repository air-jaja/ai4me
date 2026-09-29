"""Prédiction de résiliation client B2B SaaS — production de certification CISIA.

Le code est découpé par **activité du cycle de vie**, non par type d'objet :

    donnees/           1. Gestion des données      — bronze → silver → gold
    features/          2. Contrôle des features    — construction et garde-fous
    modelisation/      3. Modélisation             — baseline et sélection
    evaluation/        4. Évaluation               — métriques, décision, impact
    packaging/         5. Packaging                — artefacts et fiche modèle
    industrialisation/ 6. Industrialisation        — lot mensuel et service
    monitoring/        7. Monitoring               — dérive et alertes

Ce découpage est volontairement aligné sur les phases du projet : une activité, un
dossier, un fichier de tests. Retrouver le code d'une étape ne demande aucune
connaissance de l'implémentation.
"""

__version__ = "1.0.0"
