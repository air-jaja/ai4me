# API de scoring

**Rôle** : le lot mensuel décide (la liste) ; l'API éclaire. Elle renvoie le risque d'un compte à la demande, avec ses
trois motifs, **sans jamais décider** (E-102). Contrat complet : `docs/openapi.json`, ou `http://localhost:8000/docs`.

## Démarrer

```powershell
# .env : CHURN_API_KEY=une-valeur-secrète   (plusieurs clés séparées par des virgules pour en changer sans coupure)
uv run python tools/modele_servi.py          # le modèle servi existe dans models/ et est promu champion
docker compose up -d api                      # sans CHURN_API_KEY, /score répond 503
Invoke-RestMethod http://localhost:8000/ready # {"statut": "pret", "modele": "churn_saas_servi 1.1", ...}
```

## Appeler

```powershell
$compte = @{ client_id = "CLI-004593"; plan = "Pro"; anciennete_mois = 14; sieges_souscrits = 4;
             derniere_connexion_jours = 30; nb_integrations = 1; valeur_vie_client_eur = 1690 } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/score -Headers @{ "X-API-Key" = $env:CHURN_API_KEY } `
                  -ContentType "application/json" -Body $compte
```

Seule `valeur_vie_client_eur` est obligatoire ; un champ absent est imputé comme à l'entraînement. Les noms des champs
sont les colonnes de l'export du CRM ; leurs libellés, descriptions et exemples viennent du dictionnaire
(`industrialisation/dictionnaire.py`), le même que la liste opérationnelle.

## Réponse et erreurs

| Champ | Libellé |
|---|---|
| `risque_pct`, `tranche_risque`, `probabilite` | Risque de départ |
| `gain_attendu_contact_eur` | Gain attendu d'un contact (€) |
| `motif` | Pourquoi ce compte ? |
| `modele` | Modèle en service |

| Code | Cause |
|---|---|
| 401 | Clé absente ou invalide (`X-API-Key`) |
| 422 | `valeur_vie_client_eur` manquante, ou champ de mauvais type |
| 503 | Modèle non chargé (`/ready` dit pourquoi), ou aucune clé configurée |

## Garanties (testées)

Mêmes scores que le lot sur les 50 comptes de l'échantillon (10⁻⁹) ; modèle chargé par alias, empreinte vérifiée ;
latence du **modèle** sous 50 ms. **À décider** : l'appel complet prend environ 80 ms ici, préparation du compte
comprise ; un budget de bout en bout reste à fixer. La clé est un secret partagé : en production, HTTPS obligatoire.
