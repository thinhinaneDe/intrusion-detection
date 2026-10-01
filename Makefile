# Enchaîne les commandes de la section 7 du README, dans le même ordre.
# Toutes les valeurs qui influencent un résultat sont dans config.toml et
# config_sans_ttl.toml ; ce fichier ne fait qu'appeler les scripts.
#
#   make venv        environnement virtuel et dépendances figées
#   make check-data  présence et intégrité des six CSV bruts (téléchargement manuel, README §2)
#   make all         toute la chaîne, de la préparation aux tables (durées par étape : README §7)
#
# Les étapes intermédiaires peuvent être lancées seules, dans l'ordre :
# prepare, models-ttl, prepare-sans-ttl, models-sans-ttl, intervals, tables.

PYTHON  ?= python3.12
VENV    := venv
PY      := $(VENV)/bin/python
AVEC    := config.toml
SANS    := config_sans_ttl.toml

.PHONY: all venv check-data prepare models-ttl prepare-sans-ttl models-sans-ttl intervals tables

all: check-data prepare models-ttl prepare-sans-ttl models-sans-ttl intervals tables

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

check-data:
	$(PY) src/download.py --config $(AVEC)

# 1. Préparation : découpage, déduplication, jeux unsup, A, B, C et test ; contrôles d'intégrité.
prepare: check-data
	$(PY) src/prepare.py --config $(AVEC)
	$(PY) src/verify_prepare.py --config $(AVEC)

# 2. Modèles, version AVEC les colonnes TTL. La recherche d'hyperparamètres du supervisé
#    (sur C) écrit results/supervised_search.json, réutilisé par la version sans TTL.
models-ttl:
	$(PY) src/models/isolation_forest.py --config $(AVEC)
	$(PY) src/models/autoencoder.py --config $(AVEC)
	$(PY) src/models/supervised.py --config $(AVEC)

# 3. Version SANS les colonnes TTL (résultat principal). Nécessite models-ttl.
prepare-sans-ttl:
	$(PY) src/prepare.py --config $(SANS)
	$(PY) src/verify_prepare.py --config $(SANS)

models-sans-ttl:
	$(PY) src/models/isolation_forest.py --config $(SANS)
	$(PY) src/models/supervised.py --config $(SANS) --skip-tuning
	$(PY) src/models/autoencoder.py --config $(SANS)

# 4. Intervalles par blocs de temps (les deux versions) et tables du README.
intervals:
	for c in $(AVEC) $(SANS); do \
	  $(PY) src/paired_bootstrap.py --config $$c && \
	  $(PY) src/block_ci.py --config $$c || exit 1; \
	done
	$(PY) src/compare_ablation.py

tables:
	$(PY) src/report_tables.py
