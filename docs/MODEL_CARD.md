---
# For reference on model card metadata, see the spec: https://github.com/huggingface/hub-docs/blob/main/modelcard.md?plain=1
# Doc / guide: https://huggingface.co/docs/hub/model-cards
license: mit
language: fr
library_name: sklearn
tags:
- tabular-classification
- churn
- b2b-saas
- calibrated-logistic-regression
metrics:
- average_precision
- roc_auc
---

# Model Card for churn_saas_servi 1.1

<!-- Provide a quick summary of what the model is/does. -->

Monthly churn risk score for B2B SaaS accounts, turned into a prioritised contact list for account managers by expected net value.

## Model Details

### Model Description

<!-- Provide a longer summary of what this model is. -->

A sklearn.linear_model.LogisticRegression (C=1.0, class_weight=balanced, penalty=l2) inside a scikit-learn pipeline (median imputation, scaling, one-hot encoding), with sigmoid calibration fitted on out-of-fold predictions - 1 calibrated copy. Chosen over RandomForestClassifier and XGBClassifier by a paired comparison on 25 folds fixed before any computation.

- **Developed by:** Rakotovoalavo Petera Haja (CISIA certification project)
- **Funded by [optional]:** Not applicable (certification project)
- **Shared by [optional]:** Rakotovoalavo Petera Haja
- **Model type:** Binary classification (churn within the next period), calibrated probabilities
- **Language(s) (NLP):** Not applicable (tabular data; labels and documentation in French)
- **License:** MIT
- **Finetuned from model [optional]:** None (trained from scratch)

### Model Sources [optional]

<!-- Provide the basic links for the model. -->

- **Repository:** https://github.com/air-jaja/ai4me
- **Paper [optional]:** Not applicable
- **Demo [optional]:** Not applicable

## Uses

<!-- Address questions around how the model is intended to be used, including the foreseeable users of the model and those affected by the model. -->

### Direct Use

<!-- This section is for the model use without fine-tuning or plugging into a larger ecosystem/app. -->

Scoring the monthly portfolio and ranking accounts by expected net value (probability x lifetime value x retention efficacy - contact cost), within the team's capacity (140 accounts per month). Each account comes with its three main reasons in plain words.

### Downstream Use [optional]

<!-- This section is for the model use when fine-tuned for a task, or when plugged into a larger ecosystem/app -->

Monthly CSV list imported into the CRM; on-demand score through the API (no decision field).

### Out-of-Scope Use

<!-- This section addresses misuse, malicious use, and uses that the model will not work well for. -->

Automatic decisions without an account manager; causal reading of the reasons (a contribution explains a score, not why a customer leaves); other markets, products or data sources; pricing or contract decisions.

## Bias, Risks, and Limitations

<!-- This section is meant to convey both technical and sociotechnical limitations. -->

Synthetic data. Fairness checked by sector, country and company size: one conclusive segment below the criterion (pays = Suisse), documented and monitored rather than corrected on the test set. Retention efficacy (0.25) is a hypothesis, the most fragile of the project; usage variables are strongly correlated, so their individual importance is understated.

### Recommendations

<!-- This section is meant to convey recommendations with respect to the bias, risk, and technical limitations. -->

Keep a human in the loop; keep the 10 % random control group to measure the real efficacy; watch the flagged segment on the next monthly batches.

## How to Get Started with the Model

Use the code below to get started with the model.

from churn_saas.packaging import charger_champion
from churn_saas.industrialisation.scoring import preparer
from churn_saas.donnees import typer_pour_modele

model, card = charger_champion()          # file hash checked against the registry
X = typer_pour_modele(preparer(raw_accounts, catalogue=catalogue))
risk = model.predict_proba(X)[:, 1]
# Monthly list: uv run python tools/liste_operationnelle.py

## Training Details

### Training Data

<!-- This should link to a Dataset Card, perhaps with a short stub of information on what the training data is all about as well as documentation related to data pre-processing or additional filtering. -->

5000 accounts after cleaning (gold, 19 columns, data manifest v1.0); frozen 80/20 stratified split; f5556d76df1470d5... is the fingerprint of the exact training rows (resultats/registre_modeles.json).

### Training Procedure

<!-- This relates heavily to the Technical Specifications. Content here should link to that section when it is relevant to the training procedure. -->

#### Preprocessing [optional]

Shared chain bronze -> silver -> gold; variables after the decision date removed; 18 features retained in phase 5.


#### Training Hyperparameters

- **Training regime:** fp64, scikit-learn; deterministic (fixed seed), refit in about one second. <!--fp32, fp16 mixed precision, bf16 mixed precision, bf16 non-mixed precision, fp16 non-mixed precision, fp8 mixed precision -->

#### Speeds, Sizes, Times [optional]

<!-- This section provides information about throughput, start/end time, checkpoint size if relevant, etc. -->

One account 12.0 ms, a batch of 5,000 accounts 0.054 s (x4.9 faster than the evaluated five-copy champion).

## Evaluation

<!-- This section describes the evaluation protocols and provides the results. -->

### Testing Data, Factors & Metrics

#### Testing Data

<!-- This should link to a Dataset Card if possible. -->

1,000 accounts held out and read for evaluation once (phase 7), then once more for reporting only (phase 9); no decision followed either read.

#### Factors

<!-- These are the things the evaluation is disaggregating by, e.g., subpopulations or domains. -->

Sector, country and company size (recall at the protocol point, 4/5 rule).

#### Metrics

<!-- These are the evaluation metrics being used, ideally with a description of why. -->

PR-AUC (primary: 28 % churners), ROC-AUC, calibration error, precision at the operating points, monthly recurring revenue covered.

### Results

| Metric | Test (95 % interval) |
|---|---|
| PR-AUC | 0.761 [0.712; 0.806] |
| ROC-AUC | 0.881 [0.858; 0.904] |
| Calibration error | 0.036 [0.028; 0.061] |
| Business point (28 accounts) | precision 0.64 |
| Protocol point (top 10 %) | precision 0.88, recall 0.31 |
| Revenue at risk covered (28 accounts) | 57% |

#### Summary

Cross-validation PR-AUC 0.793 lies within the test interval. Versus the frozen baseline, RandomForestClassifier (0.774) and XGBClassifier (0.780) do not beat LogisticRegression. The served one-copy model is equivalent to the evaluated champion (paired gap -0.0001, rank correlation 0.9999). 2833 of 4000 accounts pass their own threshold: capacity, not profitability, is the constraint; the treated list is stable (mean Jaccard 0.87).

## Model Examination [optional]

<!-- Relevant interpretability work for the model goes here -->

Exact linear contributions per account (base + contributions = score before calibration). On the test set, the most important features by permutation are derniere_connexion_jours, anciennete_mois, nb_integrations, tickets_support_90j.

## Environmental Impact

<!-- Total emissions (in grams of CO2eq) and additional considerations, such as electricity usage, go here. Edit the suggested text below accordingly -->

Carbon emissions can be estimated using the [Machine Learning Impact calculator](https://mlco2.github.io/impact#compute) presented in [Lacoste et al. (2019)](https://arxiv.org/abs/1910.09700).

- **Hardware Type:** Laptop CPU (Intel Core i5-6300U, 4 cores)
- **Hours used:** Training under one second; whole tuning 64 s
- **Cloud Provider:** None (local)
- **Compute Region:** None (local)
- **Carbon Emitted:** Thousandths of a watt-hour per training, measured for the tuned models in phase 8 (resultats/ressources_modeles.json, docs/06.SOBRIETE_calcul.md); carbon negligible.

## Technical Specifications [optional]

### Model Architecture and Objective

Calibrated logistic regression on 18 tabular features; objective: log-loss.

### Compute Infrastructure

Local workstation: training, MLflow tracking, monthly batch. Docker stack: the API is demonstrated in it; its MLflow server and the batch deployment are deferred (D-06, D-10, D-11).

#### Hardware

Any CPU; under 10 MB of memory to score.

#### Software

Python 3.11, scikit-learn, pandas; versions locked in uv.lock.

## Citation [optional]

<!-- If there is a paper or blog post introducing the model, the APA and Bibtex information for that should go in this section. -->

**BibTeX:**

Not applicable

**APA:**

Not applicable

## Glossary [optional]

<!-- If relevant, include terms and calculations in this section that can help readers understand the model or model card. -->

PR-AUC: area under the precision-recall curve. Expected net value: probability x value x efficacy - cost. Control group: accounts randomly not contacted.

## More Information [optional]

Monitoring and retraining plan (phase 11, rules M1-M10 validated before any computation). Monthly, against a reference profile versioned with the model (resultats/profil_reference.json): drift alert when one key variable (derniere_connexion_jours, anciennete_mois, nb_integrations, tickets_support_90j) has a PSI above 0.25, 3 variables above 0.1, or the score above 0.1; missing values above 2 x their training share; flagged accounts moving by more than 30% from the previous month. Quarterly: at-risk revenue coverage of at least 50%, recall on the Switzerland segment (phase 9 fairness criterion), retention against the control group, PR-AUC drop above 15%. An alert warns and is qualified by a person; it never blocks scoring. Retraining every 3 months, earlier on an alert qualified as real drift, on a 12-month window excluding contacted accounts (control group and non-contacted accounts kept); a new champion comes with a new reference profile. Demonstrated on simulated batches (data/simulation/, notebooks/11_suivi.ipynb): mechanics only, no performance claim. Decisions and rejected options: docs/00.README_choix_methodologiques.md, docs/05.REGISTRE_elements_ecartes.md.

## Model Card Authors [optional]

Rakotovoalavo Petera Haja

## Model Card Contact

Through the repository issues
