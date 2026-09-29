"""Garantie d'unicité du code : ce que le notebook affiche est ce qui est testé."""

import inspect

from churn_saas.donnees.silver import nettoyer_decimal_texte
from churn_saas.notebook import afficher_source


def test_la_source_affichee_est_celle_du_module():
    """`afficher_source` lit le code dans le module : il ne peut pas diverger.

    C'est l'invariant qui autorise un notebook auto-porteur sans duplication de code.
    """
    affiche = afficher_source(nettoyer_decimal_texte)
    assert affiche == inspect.getsource(nettoyer_decimal_texte)
    assert "def nettoyer_decimal_texte" in affiche
