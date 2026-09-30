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


def test_le_tableau_affiche_ne_tronque_aucune_cellule():
    """A truncated table is a lost argument: the renderer must never elide content."""
    import pandas as pd

    from churn_saas.notebook import afficher_tableau

    texte_long = (
        "Intérêt légitime de l'éditeur pour la rétention de sa clientèle, "
        "sans consentement requis mais avec droit d'opposition à prévoir."
    )
    df = pd.DataFrame({"cadre": ["RGPD"], "traduction": [texte_long]})

    rendu = afficher_tableau(df, "Contrôle", retourner_html=True)
    assert texte_long.replace("'", "&#x27;") in rendu or texte_long in rendu
    assert "..." not in rendu
    assert "white-space: normal" in rendu
