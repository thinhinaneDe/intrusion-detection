# Projet — Détection d'intrusion réseau : supervisé vs non supervisé

## Contexte

Projet technique personnel destiné à un dépôt GitHub public, lu par un jury
universitaire (M1 Informatique). Le dépôt doit pouvoir être défendu à l'oral,
ligne par ligne.

Second projet d'une série. Le premier (pipeline PySpark sur GDELT) portait sur
le traitement de données à grande échelle. Celui-ci porte sur la modélisation
et l'évaluation — et sur une question que la plupart des projets de détection
d'intrusion escamotent.

## La question traitée

**Un modèle qui n'a jamais vu d'attaque peut-il en détecter une, et que perd-il
par rapport à un classifieur supervisé qui, lui, les a vues à l'entraînement ?**

Ce n'est pas un exercice de classification. C'est la question qu'un SOC se pose
face à une attaque inédite : le modèle supervisé, excellent sur les familles
connues, tient-il quand la famille est absente de son entraînement ?

## Règles de travail — prioritaires sur tout le reste

1. **Expliquer avant d'écrire.** Pour toute étape non triviale (choix
   d'architecture, métrique, seuil, stratégie de découpage), expliquer le
   raisonnement en 2-3 phrases, puis proposer le code.
2. **Ne pas écrire le projet à ma place.** Le boilerplate (arborescence,
   chargement de données, boucles d'entraînement, formatage) peut être délégué.
   Les décisions de modélisation et d'évaluation restent les miennes : proposer
   des options et leurs compromis plutôt qu'une solution unique.
3. **Aucun chiffre non mesuré.** Jamais de performance estimée, extrapolée ou
   recopiée d'un article. Si ce n'est pas sorti d'une exécution sur ces données,
   ça ne s'écrit pas.
4. **Interroger ma compréhension.** Si je copie du code sans le commenter,
   demander ce qu'il fait avant de continuer.
5. **Pas de dépendance superflue.** Toute bibliothèque au-delà de la stack
   ci-dessous doit être justifiée.
6. **Commits atomiques et fréquents**, un par étape fonctionnelle, messages en
   français accentué. Jamais de ligne d'attribution (`Co-Authored-By` ou
   équivalent) dans les messages de commit.
7. **Graine aléatoire fixée et documentée partout.** Un résultat non
   reproductible n'est pas un résultat.

## Le protocole expérimental — le cœur du projet

C'est ici que le projet se distingue d'un tutoriel de classification. Le
découpage des données n'est pas un `train_test_split` aléatoire.

**Trois jeux, construits explicitement :**

- **Entraînement non supervisé** : trafic normal uniquement. Le modèle ne voit
  aucune attaque.
- **Entraînement supervisé** : trafic normal + attaques, mais **une ou plusieurs
  familles d'attaques sont volontairement retirées**.
- **Test** : trafic normal + toutes les attaques, y compris les familles
  retenues hors de l'entraînement supervisé.

Les familles mises de côté doivent être choisies et justifiées explicitement,
pas tirées au hasard. Leur volume dans le jeu de test doit être annoncé.

**Deux régimes d'évaluation, rapportés séparément :**

- performance sur les familles d'attaques vues à l'entraînement ;
- performance sur les familles jamais vues.

Un tableau qui mélange les deux masque exactement ce que le projet cherche à
montrer.

## Métriques — et pourquoi pas l'accuracy

Les classes sont massivement déséquilibrées : certaines familles d'attaques
représentent une fraction de pourcent du trafic. Un modèle qui prédit « normal »
partout obtient une accuracy élevée et ne détecte rien.

À rapporter systématiquement :

- précision, rappel et F1 **par famille d'attaque**, pas seulement en agrégé ;
- AUC-PR (courbe précision-rappel), plus informative que l'AUC-ROC en régime
  déséquilibré — expliquer pourquoi dans le rapport ;
- la matrice de confusion complète, pas seulement ses résumés ;
- le taux de faux positifs rapporté à un volume réaliste : un SOC qui reçoit
  10 000 flux par heure avec 2 % de faux positifs reçoit 200 fausses alertes par
  heure. C'est ce chiffre-là qui décide si un modèle est déployable.

Le choix du seuil de décision doit être une décision argumentée et mesurée, pas
la valeur par défaut de la bibliothèque.

## Modèles

- **Non supervisé** : autoencodeur (erreur de reconstruction comme score
  d'anomalie) et Isolation Forest comme référence.
- **Supervisé** : gradient boosting (XGBoost ou LightGBM) comme plafond de
  performance sur les familles connues.

Pas de deep learning là où un modèle plus simple suffit. Si l'autoencodeur ne
bat pas l'Isolation Forest, c'est un résultat à rapporter tel quel, pas un
échec à masquer par du réglage d'hyperparamètres.

## Stack

- Python 3.12+, `venv` + `requirements.txt` avec versions figées.
- pandas, scikit-learn, PyTorch (autoencodeur), XGBoost ou LightGBM,
  matplotlib.
- Pas de framework d'expérimentation lourd. Un fichier de configuration et des
  scripts paramétrés en ligne de commande suffisent.

## Structure attendue

```
.
├── README.md
├── requirements.txt
├── Makefile
├── data/              # gitignoré — jamais de données versionnées
├── src/
│   ├── download.py    # récupération du dataset
│   ├── prepare.py     # nettoyage, encodage, construction des trois jeux
│   ├── models/
│   │   ├── autoencoder.py
│   │   ├── isolation_forest.py
│   │   └── supervised.py
│   └── evaluate.py    # métriques, seuils, matrices de confusion
├── notebooks/
│   └── resultats.ipynb
└── report/
    ├── mesures.md     # journal de mesures, une entrée par expérience
    └── synthese.md
```

## Journal de mesures

`report/mesures.md` suit la même règle que sur le projet précédent : **une
entrée par mesure, datée, avec la commande exacte qui l'a produite.** Rien
d'estimé, rien d'extrapolé. Les résultats qui contredisent une hypothèse de
départ y restent écrits — ce sont les plus intéressants.

## Contraintes de qualité

- Aucune donnée dans le dépôt : `data/` dans `.gitignore`, avec un script de
  téléchargement documenté.
- Le dépôt doit tourner sur une machine vierge en suivant uniquement le README.
- Toute valeur en dur (chemin, seuil, hyperparamètre, graine) remonte dans une
  configuration ou un argument de ligne de commande.
- Docstrings sur chaque fonction publique. Commentaires uniquement là où le
  *pourquoi* n'est pas évident.
- Aucune fuite de données entre entraînement et test : le scaler, l'encodeur et
  toute statistique d'ajustement se calculent **sur l'entraînement seul**. C'est
  l'erreur la plus courante de ce type de projet et elle fausse tous les
  résultats.

## README — sections obligatoires

1. Contexte et question traitée.
2. Données : source, volumétrie, familles d'attaques, comment les obtenir.
3. Protocole expérimental : les trois jeux, les familles exclues et pourquoi.
4. Résultats chiffrés : par famille, dans les deux régimes.
5. Analyse : pourquoi ces écarts, ce que le supervisé perd sur l'inédit.
6. Limites et pistes d'amélioration.
7. Reproduction : commandes exactes.

La section 6 n'est pas une formalité. Les limites connues de ces jeux de données
(labellisation contestée, trafic synthétique, obsolescence des familles
d'attaques) doivent y figurer nommément — un jury en sécurité les connaît.

## Hors périmètre

Ne pas proposer : interface web, API de scoring, conteneurisation, déploiement
cloud, traitement en flux temps réel. Ces éléments diluent le propos.
