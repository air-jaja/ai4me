"""Single-source guarantee: what the notebook displays is what the tests cover."""

import inspect

from churn_saas.donnees.silver import nettoyer_decimal_texte
from churn_saas.notebook import afficher_source


def test_la_source_affichee_est_celle_du_module():
    """`afficher_source` reads the code from the module, so it cannot drift.

    This is the invariant that allows a self-contained notebook with no duplicated code.
    """
    affiche = afficher_source(nettoyer_decimal_texte)
    assert affiche == inspect.getsource(nettoyer_decimal_texte)
    assert "def nettoyer_decimal_texte" in affiche
