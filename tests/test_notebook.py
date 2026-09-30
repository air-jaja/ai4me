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


def test_le_rendu_ne_depend_pas_d_ipython(monkeypatch):
    """The markup must be produced even without IPython installed.

    Caught on a fresh clone installed with the `dev` group only: the function ignored
    `retourner_html` on the fallback path and returned None. The defect was invisible in a
    notebook environment, where IPython is always present - exactly the kind of gap a test
    run in the development environment alone never sees.
    """
    import builtins

    import pandas as pd

    from churn_saas.notebook import afficher_tableau

    vrai_import = builtins.__import__

    def sans_ipython(nom, *args, **kwargs):
        if nom.startswith("IPython"):
            raise ImportError("IPython indisponible")
        return vrai_import(nom, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sans_ipython)

    rendu = afficher_tableau(pd.DataFrame({"a": ["x" * 200]}), "Contrôle", retourner_html=True)
    assert rendu is not None
    assert "white-space: normal" in rendu
