"""Activité 1 — Gestion des données.

Trois niveaux de raffinage, convention usuelle en ingénierie de données :

    BRONZE  données brutes, telles que reçues, jamais modifiées
    SILVER  données nettoyées et normalisées, fidèles au métier, lisibles par un humain
    GOLD    données prêtes pour l'apprentissage : variables construites, colonnes
            interdites retirées, cible séparée

La frontière silver → gold porte la décision la plus lourde du projet : c'est en passant
au gold que les variables en fuite sont écartées (notebook § 7).
"""

from .gold import construire_gold, separer_cible
from .ingestion import charger_bronze, inventaire
from .silver import construire_silver

__all__ = [
    "charger_bronze",
    "inventaire",
    "construire_silver",
    "construire_gold",
    "separer_cible",
]
