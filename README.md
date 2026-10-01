# Détection d'intrusion réseau : supervisé contre non supervisé

Un modèle qui n'a jamais vu d'attaque peut-il en détecter une, et que perd-il par rapport à un
classifieur supervisé qui, lui, les a vues à l'entraînement ? Projet technique personnel (M1
Informatique), sur le jeu UNSW-NB15. Second d'une série : le premier (pipeline PySpark sur GDELT)
portait sur le traitement à grande échelle ; celui-ci porte sur la modélisation et l'évaluation.

Toutes les mesures citées ici sont tirées d'exécutions consignées dans
[`report/mesures.md`](report/mesures.md) (une entrée par mesure, avec la commande exacte). Aucune
performance n'est estimée ni recopiée d'un article.

## 1. Contexte et question traitée

Face à une attaque inédite, un SOC se demande si son modèle, excellent sur les familles connues,
tient quand la famille est absente de son entraînement. Ce n'est pas un exercice de
classification : un modèle qui prédit « normal » partout obtient une accuracy élevée et ne détecte
rien, car les attaques ne représentent que 1,4 % du trafic de test.

Le protocole oppose trois modèles qui n'ont jamais vu d'attaque (Isolation Forest, deux
autoencodeurs) à un gradient boosting supervisé (XGBoost), dans trois conditions qui isolent
l'effet d'une famille absente à l'entraînement.

**Réponse en bref** (intervalles à 95 % par blocs de temps, voir §3.6 ; « rappel lu au même taux » :
§4.1) :

1. **Sans les colonnes TTL** (résultat principal), les modèles non supervisés ne détectent presque
   rien : AUC-PR de 0,118 [0,058 ; 0,180] (Isolation Forest), 0,091 [0,041 ; 0,196] et 0,061
   [0,029 ; 0,120] (autoencodeurs), pour une prévalence de 1,395 % ; rappel lu à 0,1 % de faux
   positifs : 0,0 %, 0,3 % [0,0 ; 3,8] et 1,3 % [0,5 ; 2,0].
2. **Avec le TTL**, l'Isolation Forest détecte 42,9 % [31,7 ; 53,8] des attaques à 1 % de faux
   positifs. C'est un raccourci du banc d'essai, non une détection de comportement : sans lui, 2,9 %
   [1,7 ; 4,3].
3. **Le supervisé reste très bon sans TTL** : AUC-PR 0,948 [0,905 ; 0,968] (condition A), rappel de
   75,8 % [69,6 ; 82,2] à 0,1 % de faux positifs.
4. **Retirer une famille de l'entraînement coûte cher, et de façon spécifique.** Écart de rappel
   entre le témoin à volume égal (B) et le traitement (C), à 0,01 % de faux positifs : Reconnaissance
   +75,9 points [+69,3 ; +82,0], Exploits +28,3 [+20,8 ; +33,4]. Sur les sept autres familles, A, B et
   C sont indiscernables.
5. **Limite qui borne toutes ces conclusions** : le protocole mesure ce qu'un raccourci identifié
   (le TTL) offrait ; il ne prouve pas qu'il n'en reste aucun (§6).

## 2. Données

**Source et licence.** UNSW-NB15 (Moustafa & Slay), créé au Cyber Range Lab de l'Australian Centre
for Cyber Security avec l'outil IXIA PerfectStorm : un mélange d'activité normale réelle et
d'attaques **synthétiques**, simulé sur deux jours (22-1-2015 et 17-2-2015 d'après le `ReadMe.pdf`
du jeu). Page du projet : <https://research.unsw.edu.au/projects/unsw-nb15-dataset>. Le jeu est
libre pour la **recherche académique uniquement** (usage commercial interdit). Le `ReadMe.pdf`
fourni avec les fichiers exige de citer :

1. Moustafa, N. et Slay, J., « UNSW-NB15: a comprehensive data set for network intrusion detection
   systems (UNSW-NB15 network data set) », Military Communications and Information Systems
   Conference (MilCIS), IEEE, 2015 ;
2. Moustafa, N. et Slay, J., « The evaluation of Network Anomaly Detection Systems: Statistical
   analysis of the UNSW-NB15 data set and the comparison with the KDD99 data set », Information
   Security Journal: A Global Perspective, 2016, pp. 1-14.

La page du projet en liste au total cinq ; les deux ci-dessus sont celles du `ReadMe.pdf`.

**Volumétrie.** Quatre CSV sans en-tête, 49 colonnes (noms dans `NUSW-NB15_features.csv`) : 2 540 047
lignes, soit 3 de plus que les 2 540 044 annoncés, car la dernière ligne de chacun des fichiers 1, 2
et 3 est répétée en première ligne du suivant. Après retrait de ces trois doublons : 2 218 761
flux normaux et 321 283 attaques.

**Familles d'attaque** (libellés normalisés, voir plus bas) :

| Famille | Enregistrements | Famille | Enregistrements |
|---|---|---|---|
| Generic | 215 481 | Reconnaissance | 13 987 |
| Exploits | 44 525 | Analysis | 2 677 |
| Fuzzers | 24 246 | Backdoors | 2 329 |
| DoS | 16 353 | Shellcode | 1 511 |
| Worms | 174 | | |

**Défauts du jeu mesurés, et traitements.**

- **Libellés** : 14 variantes brutes de `attack_cat` pour 9 familles (espaces parasites ;
  `Backdoor` et `Backdoors` sont un même libellé écrit de deux façons, une par lot d'étiquetage, un
  par jour). Normalisés et fusionnés.
- **Doublons exacts** : 480 630 lignes en surplus sur 49 colonnes, retirées **après** le découpage
  temporel, côté par côté (416 624 à l'entraînement, 64 006 au test). 89,2 % des attaques Generic du
  jour d'entraînement étaient des copies exactes (207 959 → 22 545) : le volume apparent de Generic
  était presque entièrement de la redondance.
- **Contradictions d'étiquetage, conservées** : sur les 41 colonnes de comportement, 2 590
  combinaisons de valeurs identiques portent des étiquettes différentes (42 322 lignes), dont 463
  combinaisons (1 913 lignes) opposent flux normal et attaque ; avant l'alignement des blancs, 449 des 453
  combinaisons opposaient normal et Fuzzers.
  Un modèle ne peut pas les classer toutes correctement ; sur le test, le plafond théorique est de
  54 erreurs binaires (0,0053 point d'accuracy), mais au plus 7,9 % des attaques ont une famille
  irréductiblement ambiguë.
- **Format propre à un jour** : trois colonnes (`ct_flw_http_mthd`, `is_ftp_login`, `ct_ftp_cmd`)
  sont vides au jour 2 et valent 0 au jour 1 ; les blancs sont remplacés par 0, sinon un modèle
  apprendrait le jour d'entraînement.
- **Date** : les données du second jour tombent le 18-02-2015 en UTC, le `ReadMe.pdf` dit le 17-02.
  Écart non élucidé.

**Obtenir les données.** Le téléchargement est **manuel** : la page du projet ci-dessus renvoie
vers un partage SharePoint qui exige un navigateur, sans URL de fichier stable qu'un script
pourrait appeler. Récupérer depuis ce partage les six fichiers CSV `UNSW-NB15_1.csv` à
`UNSW-NB15_4.csv`, `NUSW-NB15_features.csv` et `UNSW-NB15_LIST_EVENTS.csv` (586 Mo), et les placer
sans les renommer dans `data/raw/` ; le `ReadMe.pdf` du partage (licence, citations, dates) est
utile à lire mais pas requis. Puis :

```bash
venv/bin/python src/download.py    # ou : make check-data
```

Ce script ne télécharge rien : il vérifie la présence des six fichiers et leur empreinte SHA-256
(`[download.sha256]` de `config.toml`), celle des fichiers qui ont produit toutes les mesures, et
indique la page officielle et les noms attendus si un fichier manque ou diffère. Le dossier `data/`
est ignoré par git : aucune donnée n'est versionnée. Les jeux déjà partitionnés
`UNSW_NB15_training-set.csv` et `UNSW_NB15_testing-set.csv` ne sont pas utilisés.

## 3. Protocole expérimental

### 3.1 Découpage temporel, pas aléatoire

Le jour 2 (18-02-2015, UTC) sert à l'entraînement, le jour 1 (22 et 23-01-2015) au test. Le jour 1
ne compte que 22 215 attaques avant déduplication, trop peu pour entraîner. Un tirage aléatoire
mélangerait les copies d'un même flux entre entraînement et test. **Le sens du temps est inversé** :
on entraîne sur le 18 février pour tester sur les 22 et 23 janvier (§6).

Après déduplication par côté : entraînement 1 036 218 lignes (950 853 normaux, 85 365 attaques),
test 1 023 196 lignes (1 008 918 normaux, 14 278 attaques, prévalence 1,395 %).

### 3.2 Les jeux d'entraînement et les familles exclues

- **Non supervisé** (`unsup`) : les 950 853 normaux du jour 2, aucune attaque.
- **A, témoin complet** : normaux et attaques des 9 familles (85 365 attaques).
- **B, témoin à volume égal** : les mêmes normaux, 50 191 attaques tirées au hasard proportionnellement
  aux familles de A (graine 42).
- **C, traitement** : Exploits et Reconnaissance retirés, 50 191 attaques.

A − B mesure l'effet du volume seul ; **B − C mesure l'effet d'une famille inédite à volume
constant** : c'est l'écart qui répond à la question. Sans B, on confondrait « famille absente » et
« 41 % d'attaques en moins ».

**Pourquoi Exploits et Reconnaissance** : ce sont les deux familles où la mesure au test est la plus
précise, et elles sont conceptuellement distinctes (exploitation d'une vulnérabilité contre balayage
exploratoire) : si un modèle en détecte une et pas l'autre, c'est interprétable. Ensemble elles pèsent
5 782 des 14 278 attaques du test (40,5 %) : Exploits 4 042, Reconnaissance 1 740. Écartées :
Worms (24 lignes de test, non concluant) et Generic (le retirer aurait privé l'entraînement de 26 %
de ses attaques pour une raison étrangère à l'expérience).

### 3.3 Variables et absence de fuite

Sont exclus des variables : `srcip`, `dstip`, `sport`, `dsport`, `Stime`, `Ltime` (un modèle qui
apprend qu'une IP est malveillante a mémorisé la machine du banc d'essai) ; il reste **41 variables**.
La **version sans TTL** retire en plus `sttl`, `dttl` et `ct_state_ttl` : **38 variables**.

Le préprocesseur (encodage one-hot des variables nominales avec regroupement des modalités rares,
`log1p` sur les colonnes dont l'asymétrie mesurée dépasse 2, puis standardisation) est **ajusté sur
l'entraînement seul, séparément pour chaque jeu** : un préprocesseur commun aurait emporté dans C les
statistiques des familles retirées, et dans `unsup` celles des attaques. La sélection `log1p` retient
32 colonnes (29 sans TTL), les mêmes dans les quatre jeux.

### 3.4 Modèles

- **Isolation Forest** : valeurs par défaut de la bibliothèque (100 arbres, 256 échantillons par
  arbre), graine 42, non réglé.
- **Autoencodeur** (PyTorch, perceptron symétrique, ReLU, perte MSE sans écrêtage, Adam 10⁻³, 30
  epochs, lot 1 024) en **deux architectures déclarées d'avance et rapportées sur le même pied** :
  « moyen » [128, 64, 16] (33 224 paramètres) et « petit » [32, 16, 8] (5 024). Le score est l'erreur
  de reconstruction.
- **Gradient boosting supervisé** (XGBoost) : profondeur 6, 100 arbres, choisis **une seule fois sur
  les données de C** (donc sans jamais voir les familles retirées) parmi la grille {6, 10} × {100, 300}
  par validation croisée en blocs de temps, critère AUC-PR moyenne sur les blocs tenus à l'écart
  (0,9565 contre 0,9531 pour la configuration la plus complexe), puis **figés pour A, B et C**.

### 3.5 Seuil de décision : un budget de faux positifs, calibré hors échantillon

Le seuil n'est jamais la valeur par défaut d'une bibliothèque. Pour un **budget** de faux positifs
(part des flux normaux qui déclenchent une alerte) — **1 %, 0,1 % (référence) et 0,01 %** — le seuil
est le quantile correspondant des scores de flux normaux **que le modèle n'a pas vus** : les normaux
du jour 2, triés dans le temps, sont coupés en 5 blocs contigus, chaque bloc étant noté par un modèle
entraîné sans lui, avec un préprocesseur réajusté. Les attaques ne servent jamais à fixer le seuil.

Le débit mesuré est d'environ 80 000 flux normaux par heure : 0,1 % ≈ 80 fausses alertes par
heure, 1 % ≈ 800. Deux lectures sont rapportées :

- **au seuil calibré** : ce qu'un déploiement obtiendrait, avec le taux de faux positifs *observé* au
  test (qui diffère du taux visé) ;
- **au même taux lu sur le test** : le seuil est pris sur les normaux du test pour égaler le budget.
  Il utilise les étiquettes du test, donc **n'est pas déployable** ; il sert à comparer des modèles
  indépendamment de la qualité de leur calibration.

### 3.6 Métriques et intervalles de confiance

L'AUC-PR (précision moyenne) est plus informative que l'AUC-ROC quand les classes sont très
déséquilibrées : elle ne récompense pas le nombre de vrais négatifs, qui domine ici (98,6 % du test).
Sont rapportés : AUC-PR, rappel par famille, taux de faux positifs observé, matrice de confusion
complète, précision et F1 globaux au budget de référence. **La précision et le F1 par famille ne
sont pas définis** : les faux positifs sont des flux normaux, non attribuables à une famille.

**Les intervalles sont calculés par rééchantillonnage de blocs de temps de 10 minutes** (1 000
réplications, graine 42, 95 %), et, pour les écarts entre conditions ou modèles, apparié (mêmes
blocs). La raison est mesurée : les attaques du test arrivent en rafales (Reconnaissance et Exploits
tombent chacun dans 12 blocs de 10 minutes sur 76), donc l'indépendance des lignes supposée par un
intervalle de Wilson est fausse et donne des intervalles 3 à 5 fois trop étroits. **Aucun
intervalle de Wilson ne figure dans ce document.** Les quantités sans intervalle par blocs sont
rapportées sans intervalle.

**Décisions déclarées avant les résultats.** Les architectures, la grille de réglage et son critère,
la liste des colonnes de l'ablation TTL et la méthode des intervalles ont été committées avant toute
exécution qui les concerne (voir l'historique git et les entrées M19, M23, M25, M27 du journal).

## 4. Résultats chiffrés

Deux versions sont rapportées : **sans TTL** (§4.1, résultat principal) et **avec TTL** (§4.2, mesure
du raccourci que le banc d'essai offre). Pour les modèles non supervisés, toutes les attaques sont
« jamais vues » ; pour le supervisé, deux régimes sont séparés : les familles vues par les trois
conditions (les sept autres) et les familles jamais vues par C (Exploits, Reconnaissance).

### 4.1 Sans TTL (résultat principal)

**Tableau 1.** AUC-PR au test [intervalle par blocs], prévalence 1,395 %

| Modèle | Sans TTL (principal) | Avec TTL (raccourci) |
|---|---|---|
| Isolation Forest | 0.118 [0.058 ; 0.180] | 0.308 [0.170 ; 0.442] |
| Autoencodeur moyen | 0.091 [0.041 ; 0.196] | 0.121 [0.053 ; 0.297] |
| Autoencodeur petit | 0.061 [0.029 ; 0.120] | 0.114 [0.052 ; 0.247] |
| Supervisé A | 0.948 [0.905 ; 0.968] | 0.976 [0.957 ; 0.988] |
| Supervisé B | 0.950 [0.909 ; 0.970] | 0.970 [0.947 ; 0.985] |
| Supervisé C | 0.944 [0.896 ; 0.964] | 0.974 [0.953 ; 0.987] |

Le taux de faux positifs visé n'est pas le taux obtenu :

**Tableau 2.** Sans TTL, budget de faux positifs 1 % (en %, [intervalle par blocs])

| Modèle | Taux de faux positifs observé | Rappel au seuil calibré | Rappel lu au même taux (non déployable) |
|---|---|---|---|
| Isolation Forest | 0.4117 [0.3547 ; 0.4978] | 0.4 [0.2 ; 0.7] | 2.9 [1.7 ; 4.3] |
| Autoencodeur moyen | 5.4359 [2.8347 ; 9.0913] | 46.5 [35.3 ; 57.9] | 5.1 [2.0 ; 18.9] |
| Autoencodeur petit | 3.1411 [1.2793 ; 5.7964] | 15.4 [12.3 ; 19.3] | 5.0 [2.6 ; 14.3] |
| Supervisé A | 0.3248 [0.2146 ; 0.4520] | 92.2 [89.8 ; 94.3] | 100.0 [99.9 ; 100.0] |
| Supervisé B | 0.3232 [0.2123 ; 0.4632] | 91.7 [89.0 ; 94.0] | 99.9 [99.9 ; 100.0] |
| Supervisé C | 0.2277 [0.1384 ; 0.3314] | 90.2 [87.0 ; 92.8] | 99.8 [99.7 ; 100.0] |

**Tableau 3.** Sans TTL, budget de faux positifs 0.1 % (en %, [intervalle par blocs])

| Modèle | Taux de faux positifs observé | Rappel au seuil calibré | Rappel lu au même taux (non déployable) |
|---|---|---|---|
| Isolation Forest | 0.1321 [0.1181 ; 0.1484] | 0.0 [0.0 ; 0.1] | 0.0 [0.0 ; 0.0] |
| Autoencodeur moyen | 1.6290 [0.4055 ; 3.5657] | 9.1 [7.5 ; 11.0] | 0.3 [0.0 ; 3.8] |
| Autoencodeur petit | 0.7108 [0.2073 ; 1.5099] | 3.6 [2.7 ; 4.7] | 1.3 [0.5 ; 2.0] |
| Supervisé A | 0.0824 [0.0678 ; 0.0985] | 74.0 [66.9 ; 80.4] | 75.8 [69.6 ; 82.2] |
| Supervisé B | 0.0651 [0.0527 ; 0.0791] | 72.3 [65.0 ; 79.2] | 75.6 [69.1 ; 81.8] |
| Supervisé C | 0.0578 [0.0453 ; 0.0726] | 61.5 [52.7 ; 70.0] | 73.7 [66.2 ; 81.3] |

**Tableau 4.** Sans TTL, budget de faux positifs 0.01 % (en %, [intervalle par blocs])

| Modèle | Taux de faux positifs observé | Rappel au seuil calibré | Rappel lu au même taux (non déployable) |
|---|---|---|---|
| Isolation Forest | 0.0714 [0.0631 ; 0.0795] | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] |
| Autoencodeur moyen | 0.2172 [0.0267 ; 0.5196] | 0.9 [0.6 ; 1.2] | 0.0 [0.0 ; 0.3] |
| Autoencodeur petit | 0.0001 [0.0000 ; 0.0003] | 0.0 [0.0 ; 0.0] | 0.3 [0.1 ; 1.3] |
| Supervisé A | 0.0048 [0.0035 ; 0.0062] | 44.7 [34.4 ; 55.0] | 56.4 [47.1 ; 65.1] |
| Supervisé B | 0.0023 [0.0010 ; 0.0040] | 45.3 [35.3 ; 55.2] | 60.4 [51.8 ; 68.9] |
| Supervisé C | 0.0076 [0.0055 ; 0.0100] | 39.9 [28.4 ; 51.5] | 41.8 [31.2 ; 53.4] |

Matrice de confusion complète, précision et F1 au budget de référence (tableau 5) :

**Tableau 5.** Sans TTL, budget de référence 0,1 % : matrice de confusion complète au seuil calibré, précision, F1 (la précision et le F1 par famille ne sont pas définis : les faux positifs sont des flux normaux)

| Modèle | VP | FP | FN | VN | Précision (%) | F1 (%) | Fausses alertes/h (moyenne ; pire heure) |
|---|---|---|---|---|---|---|---|
| Isolation Forest | 4 | 1333 | 14274 | 1007585 | 0.3 | 0.1 | 105.8 ; 199 |
| Autoencodeur moyen | 1301 | 16435 | 12977 | 992483 | 7.3 | 8.1 | 1304.7 ; 12573 |
| Autoencodeur petit | 518 | 7171 | 13760 | 1001747 | 6.7 | 4.7 | 569.3 ; 5176 |
| Supervisé A | 10561 | 831 | 3717 | 1008087 | 92.7 | 82.3 | 66.0 ; 132 |
| Supervisé B | 10330 | 657 | 3948 | 1008261 | 94.0 | 81.8 | 52.2 ; 134 |
| Supervisé C | 8786 | 583 | 5492 | 1008335 | 93.8 | 74.3 | 46.3 ; 110 |

**Par famille, rappel lu au même taux** (les intervalles par blocs des petites familles couvrent
presque tout l'intervalle possible : Analysis, Worms, Backdoors et Shellcode ne sont pas
interprétables individuellement) :

**Tableau 6.** Sans TTL, rappel par famille lu au même taux 0.1 % (en %, [intervalle par blocs])

| Famille (n test) | Isolation Forest | Autoencodeur moyen | Autoencodeur petit | Supervisé A | Supervisé B | Supervisé C |
|---|---|---|---|---|---|---|
| Analysis (301) | 0.0 [0.0 ; 0.0] | 0.3 [0.0 ; 1.7] | 0.0 [0.0 ; 0.0] | 80.7 [0.0 ; 100.0] | 81.1 [1.8 ; 100.0] | 81.1 [1.8 ; 100.0] |
| Backdoors (299) | 0.0 [0.0 ; 0.0] | 0.3 [0.0 ; 6.7] | 0.0 [0.0 ; 0.0] | 96.7 [76.7 ; 99.5] | 96.7 [73.2 ; 99.7] | 97.0 [77.6 ; 99.6] |
| DoS (825) | 0.0 [0.0 ; 0.0] | 0.6 [0.0 ; 8.0] | 3.3 [1.3 ; 6.4] | 89.0 [79.9 ; 94.6] | 89.9 [81.9 ; 94.9] | 88.8 [80.0 ; 94.6] |
| Exploits (4042) | 0.0 [0.0 ; 0.1] | 0.4 [0.0 ; 8.5] | 2.6 [1.1 ; 3.9] | 91.9 [88.5 ; 95.4] | 91.9 [88.6 ; 95.2] | 88.0 [83.6 ; 91.7] |
| Fuzzers (3991) | 0.0 [0.0 ; 0.1] | 0.2 [0.0 ; 1.0] | 0.1 [0.0 ; 0.3] | 29.8 [20.0 ; 42.3] | 28.5 [18.6 ; 41.3] | 40.2 [28.8 ; 55.7] |
| Generic (2833) | 0.0 [0.0 ; 0.0] | 0.1 [0.0 ; 3.8] | 1.6 [0.5 ; 3.9] | 98.1 [96.2 ; 99.1] | 98.4 [96.8 ; 99.1] | 98.8 [97.0 ; 99.5] |
| Reconnaissance (1740) | 0.0 [0.0 ; 0.0] | 0.3 [0.0 ; 0.8] | 0.0 [0.0 ; 0.0] | 96.6 [94.7 ; 98.7] | 97.2 [95.1 ; 98.9] | 62.5 [50.7 ; 78.0] |
| Shellcode (223) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] | 78.9 [69.2 ; 87.7] | 74.0 [64.4 ; 84.7] | 84.3 [73.4 ; 93.7] |
| Worms (24) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 21.1] | 8.3 [0.0 ; 21.1] | 95.8 [88.5 ; 100.0] | 91.7 [81.2 ; 100.0] | 95.8 [87.0 ; 100.0] |

**Tableau 7.** Sans TTL, rappel par famille lu au même taux 0.01 % (en %, [intervalle par blocs])

| Famille (n test) | Isolation Forest | Autoencodeur moyen | Autoencodeur petit | Supervisé A | Supervisé B | Supervisé C |
|---|---|---|---|---|---|---|
| Analysis (301) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.4] | 0.0 [0.0 ; 0.0] | 80.4 [0.0 ; 100.0] | 79.4 [0.0 ; 99.2] | 80.1 [0.0 ; 99.6] |
| Backdoors (299) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.4] | 0.0 [0.0 ; 0.0] | 91.3 [45.7 ; 97.6] | 92.0 [51.5 ; 97.1] | 89.0 [33.3 ; 97.2] |
| DoS (825) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 1.0] | 1.5 [0.0 ; 4.4] | 65.7 [44.4 ; 80.5] | 70.1 [51.0 ; 83.0] | 58.9 [34.0 ; 78.1] |
| Exploits (4042) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.4] | 0.5 [0.1 ; 2.6] | 70.7 [62.0 ; 77.5] | 77.6 [70.8 ; 84.1] | 49.3 [40.9 ; 60.1] |
| Fuzzers (3991) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.1] | 0.0 [0.0 ; 0.1] | 7.1 [0.7 ; 19.0] | 7.8 [1.0 ; 20.9] | 7.1 [0.7 ; 19.0] |
| Generic (2833) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.1] | 0.1 [0.0 ; 1.7] | 89.5 [82.4 ; 91.8] | 92.7 [86.2 ; 95.3] | 91.2 [83.7 ; 94.5] |
| Reconnaissance (1740) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.4] | 0.0 [0.0 ; 0.0] | 73.4 [65.8 ; 80.3] | 79.8 [72.9 ; 86.6] | 3.9 [2.5 ; 7.0] |
| Shellcode (223) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] | 12.1 [5.4 ; 18.6] | 21.5 [10.0 ; 31.3] | 17.9 [8.5 ; 31.1] |
| Worms (24) | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] | 8.3 [0.0 ; 21.1] | 62.5 [40.6 ; 78.6] | 66.7 [46.2 ; 83.3] | 16.7 [8.7 ; 38.7] |

**Les deux régimes** — sur les sept autres familles, A, B et C sont indiscernables ; sur les familles
retirées de C, C chute :

**Tableau 8.** Sans TTL, deux régimes : familles retirées de C contre les sept autres (rappel lu au même taux, en %)

| Modèle | Budget | Sept autres familles (vues par A, B, C) | Exploits + Reconnaissance (retirées de C) |
|---|---|---|---|
| Isolation Forest | 0.1 % | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.1] |
| Isolation Forest | 0.01 % | 0.0 [0.0 ; 0.0] | 0.0 [0.0 ; 0.0] |
| Autoencodeur moyen | 0.1 % | 0.2 [0.0 ; 2.4] | 0.4 [0.0 ; 5.9] |
| Autoencodeur moyen | 0.01 % | 0.0 [0.0 ; 0.2] | 0.0 [0.0 ; 0.4] |
| Autoencodeur petit | 0.1 % | 0.9 [0.3 ; 1.7] | 1.8 [0.7 ; 2.7] |
| Autoencodeur petit | 0.01 % | 0.2 [0.0 ; 1.0] | 0.3 [0.1 ; 1.8] |
| Supervisé A | 0.1 % | 63.9 [51.2 ; 75.0] | 93.3 [90.5 ; 96.2] |
| Supervisé A | 0.01 % | 46.1 [28.6 ; 59.7] | 71.5 [63.7 ; 77.9] |
| Supervisé B | 0.1 % | 63.4 [50.3 ; 74.5] | 93.5 [90.9 ; 96.2] |
| Supervisé B | 0.01 % | 48.2 [30.5 ; 62.0] | 78.3 [72.0 ; 84.7] |
| Supervisé C | 0.1 % | 69.2 [57.7 ; 79.0] | 80.3 [73.8 ; 87.3] |
| Supervisé C | 0.01 % | 45.9 [28.7 ; 60.4] | 35.7 [28.9 ; 44.7] |

**Écart B − C et A − B** (mêmes lignes de test, intervalles par blocs appariés) :

**Tableau 9.** Sans TTL : écarts de rappel lu au même taux, en points, IC par blocs apparié

| Famille | Budget | Rappel A / B / C | A − B (volume) | B − C (famille inédite) |
|---|---|---|---|---|
| Reconnaissance | 0.1 % | 96.6 / 97.2 / 62.5 | -0.6 [-1.1 ; +0.1] | +34.8 [+19.4 ; +45.6] |
| Reconnaissance | 0.01 % | 73.4 / 79.8 / 3.9 | -6.4 [-11.5 ; -2.3] | +75.9 [+69.3 ; +82.0] |
| Exploits | 0.1 % | 91.9 / 91.9 / 88.0 | -0.0 [-0.8 ; +0.9] | +4.0 [+2.2 ; +6.6] |
| Exploits | 0.01 % | 70.7 / 77.6 / 49.3 | -6.9 [-11.4 ; -3.2] | +28.3 [+20.8 ; +33.4] |

Sans jumeau dans A, B ni C, l'écart B − C sur Reconnaissance reste net :

**Tableau 10.** Sans TTL : Reconnaissance, écart B − C lu au même taux, sans jumeau dans A, B ni C (points, IC par blocs apparié)

| Budget | B − C sans jumeau |
|---|---|
| 0.1 % | +45.7 [+26.0 ; +58.3] |
| 0.01 % | +67.9 [+60.4 ; +75.8] |

**Contamination par jumeaux.** 449 des 1 740 lignes de test de Reconnaissance (25,8 %) ont un jumeau
exact (mêmes valeurs sur toutes les variables) dans A, 415 dans B, 1 dans C. La mémorisation gonfle le
rappel global de A et de B aux budgets stricts, mais n'explique pas l'écart B − C :

**Tableau 11.** Sans TTL : Reconnaissance (1 740 lignes de test), rappel avec et sans jumeau dans le jeu d'entraînement (en %, sans intervalle par blocs)

| Condition | Budget | Seuil | Tous | Avec jumeau | Sans jumeau |
|---|---|---|---|---|---|
| Supervisé A | 0.1 % | au seuil calibré | 96.4 | 100.0 (n = 449) | 95.1 (n = 1291) |
| Supervisé A | 0.1 % | lu au même taux | 96.6 | 100.0 (n = 449) | 95.4 (n = 1291) |
| Supervisé A | 0.01 % | au seuil calibré | 30.3 | 10.7 (n = 449) | 37.2 (n = 1291) |
| Supervisé A | 0.01 % | lu au même taux | 73.4 | 92.7 (n = 449) | 66.8 (n = 1291) |
| Supervisé B | 0.1 % | au seuil calibré | 96.1 | 100.0 (n = 415) | 94.9 (n = 1325) |
| Supervisé B | 0.1 % | lu au même taux | 97.2 | 100.0 (n = 415) | 96.4 (n = 1325) |
| Supervisé B | 0.01 % | au seuil calibré | 39.1 | 42.2 (n = 415) | 38.2 (n = 1325) |
| Supervisé B | 0.01 % | lu au même taux | 79.8 | 100.0 (n = 415) | 73.5 (n = 1325) |
| Supervisé C | 0.1 % | au seuil calibré | 35.7 | 100.0 (n = 1) | 35.7 (n = 1739) |
| Supervisé C | 0.1 % | lu au même taux | 62.5 | 100.0 (n = 1) | 62.4 (n = 1739) |
| Supervisé C | 0.01 % | au seuil calibré | 2.8 | 100.0 (n = 1) | 2.7 (n = 1739) |
| Supervisé C | 0.01 % | lu au même taux | 3.9 | 100.0 (n = 1) | 3.9 (n = 1739) |

**Entre modèles non supervisés** (écarts appariés) :

**Tableau 12.** Sans TTL : écarts APPARIÉS entre modèles non supervisés (points de rappel ou d'AUC-PR ; [IC par blocs])

| Écart | AUC-PR | Rappel lu au même taux 1 % | Rappel lu au même taux 0.1 % | Rappel lu au même taux 0.01 % |
|---|---|---|---|---|
| Autoencodeur petit − Autoencodeur moyen | -0.030 [-0.078 ; -0.011] | -0.17 [-5.11 ; +1.00] | +1.01 [-2.19 ; +1.45] | +0.27 [+0.06 ; +1.10] |
| Isolation Forest − Autoencodeur moyen | +0.027 [-0.042 ; +0.055] | -2.26 [-15.77 ; +0.39] | -0.27 [-3.83 ; +0.00] | +0.00 [-0.25 ; +0.00] |
| Isolation Forest − Autoencodeur petit | +0.057 [+0.010 ; +0.094] | -2.09 [-10.97 ; +0.22] | -1.28 [-1.94 ; -0.53] | -0.27 [-1.30 ; -0.06] |

### 4.2 Avec TTL : mesure du raccourci

Rappel lu au même taux, sans et avec les colonnes TTL :

**Tableau 13.** Mesure du raccourci TTL : rappel lu au même taux 1 % (en %, [intervalle par blocs])

| Modèle | Sans TTL | Avec TTL |
|---|---|---|
| Isolation Forest | 2.9 [1.7 ; 4.3] | 42.9 [31.7 ; 53.8] |
| Autoencodeur moyen | 5.1 [2.0 ; 18.9] | 6.1 [3.6 ; 46.3] |
| Autoencodeur petit | 5.0 [2.6 ; 14.3] | 6.2 [2.8 ; 27.2] |
| Supervisé A | 100.0 [99.9 ; 100.0] | 100.0 [100.0 ; 100.0] |
| Supervisé B | 99.9 [99.9 ; 100.0] | 100.0 [100.0 ; 100.0] |
| Supervisé C | 99.8 [99.7 ; 100.0] | 100.0 [100.0 ; 100.0] |

**Tableau 14.** Mesure du raccourci TTL : rappel lu au même taux 0.1 % (en %, [intervalle par blocs])

| Modèle | Sans TTL | Avec TTL |
|---|---|---|
| Isolation Forest | 0.0 [0.0 ; 0.0] | 2.5 [1.3 ; 4.6] |
| Autoencodeur moyen | 0.3 [0.0 ; 3.8] | 0.6 [0.1 ; 5.0] |
| Autoencodeur petit | 1.3 [0.5 ; 2.0] | 1.4 [0.5 ; 2.8] |
| Supervisé A | 75.8 [69.6 ; 82.2] | 85.6 [79.7 ; 95.7] |
| Supervisé B | 75.6 [69.1 ; 81.8] | 82.5 [75.3 ; 93.5] |
| Supervisé C | 73.7 [66.2 ; 81.3] | 86.3 [76.8 ; 96.8] |

Écart B − C et A − B avec TTL :

**Tableau 15.** Avec TTL : écarts de rappel lu au même taux, en points, IC par blocs apparié

| Famille | Budget | Rappel A / B / C | A − B (volume) | B − C (famille inédite) |
|---|---|---|---|---|
| Reconnaissance | 0.1 % | 98.9 / 98.7 / 89.9 | +0.2 [-0.3 ; +1.6] | +8.7 [+0.2 ; +22.6] |
| Reconnaissance | 0.01 % | 96.6 / 95.8 / 42.2 | +0.7 [-0.0 ; +2.4] | +53.6 [+31.1 ; +62.4] |
| Exploits | 0.1 % | 97.4 / 96.7 / 94.8 | +0.7 [-0.1 ; +2.3] | +1.9 [+0.1 ; +3.5] |
| Exploits | 0.01 % | 91.4 / 89.2 / 83.6 | +2.2 [-0.2 ; +4.9] | +5.6 [+0.8 ; +8.9] |

Écarts appariés entre modèles non supervisés avec TTL :

**Tableau 16.** Avec TTL : écarts APPARIÉS entre modèles non supervisés (points de rappel ou d'AUC-PR ; [IC par blocs])

| Écart | AUC-PR | Rappel lu au même taux 1 % | Rappel lu au même taux 0.1 % | Rappel lu au même taux 0.01 % |
|---|---|---|---|---|
| Autoencodeur petit − Autoencodeur moyen | -0.007 [-0.057 ; +0.007] | +0.12 [-24.14 ; +5.24] | +0.77 [-2.65 ; +1.17] | +0.27 [-0.18 ; +0.62] |
| Isolation Forest − Autoencodeur moyen | +0.187 [+0.063 ; +0.250] | +36.81 [-0.63 ; +47.59] | +1.84 [-1.55 ; +3.46] | +0.06 [-0.62 ; +0.62] |
| Isolation Forest − Autoencodeur petit | +0.194 [+0.081 ; +0.263] | +36.69 [+11.60 ; +47.47] | +1.07 [-0.28 ; +2.90] | -0.22 [-0.88 ; +0.39] |

Dérive temporelle sur familles connues (supervisé, rappel des attaques du jour d'entraînement tenues à
l'écart, au moment non vu, contre rappel du test, à seuil égal ; sans intervalle par blocs) :

**Tableau 17.** Supervisé : rappel des attaques tenues à l'écart (jour 2) contre rappel du test, au seuil calibré (en %, sans intervalle par blocs)

| Condition | Budget | Tenues à l'écart (jour 2) | Test, mêmes familles |
|---|---|---|---|
| A (sans TTL) | 1 % | 93.2 | 92.2 |
| A (sans TTL) | 0.1 % | 80.2 | 74.0 |
| A (sans TTL) | 0.01 % | 60.5 | 44.7 |
| B (sans TTL) | 1 % | 92.9 | 91.7 |
| B (sans TTL) | 0.1 % | 78.8 | 72.3 |
| B (sans TTL) | 0.01 % | 54.6 | 45.3 |
| C (sans TTL) | 1 % | 90.0 | 87.3 |
| C (sans TTL) | 0.1 % | 70.3 | 58.6 |
| C (sans TTL) | 0.01 % | 57.7 | 44.9 |
| A (avec TTL) | 1 % | 93.3 | 91.0 |
| A (avec TTL) | 0.1 % | 79.9 | 73.3 |
| A (avec TTL) | 0.01 % | 59.9 | 49.4 |
| B (avec TTL) | 1 % | 93.4 | 91.5 |
| B (avec TTL) | 0.1 % | 79.9 | 74.0 |
| B (avec TTL) | 0.01 % | 58.9 | 46.0 |
| C (avec TTL) | 1 % | 90.1 | 88.2 |
| C (avec TTL) | 0.1 % | 70.6 | 59.8 |
| C (avec TTL) | 0.01 % | 59.2 | 46.9 |

## 5. Analyse

**Ce que le supervisé perd sur l'inédit.** Sans TTL, un modèle qui n'a jamais vu Reconnaissance la
détecte à 3,9 % à 0,01 % de faux positifs, contre 79,8 % quand il l'a vue (condition B), et à 62,5 %
contre 97,2 % à 0,1 % (tableau 9). Pour Exploits, la perte est faible à 0,1 % (+4,0 points de
B − C) et nette à 0,01 % (+28,3 : 49,3 % contre 77,6 %). Exploitation d'une vulnérabilité et
balayage se comportent donc très différemment, comme le protocole le faisait espérer. La perte est
**spécifique aux familles retirées** : sur les sept autres, C n'est pas moins bon que A ou B
(tableau 8). Elle dépend du budget : à 1 % de faux positifs, le rappel de toutes les conditions
est saturé à plus de 99,7 % et ne discrimine rien.

**Ce n'est pas un effet de volume, ni de mémorisation.** L'écart A − B, qui mesure le volume seul, est
faible ou de signe incertain (par exemple −6,4 points [−11,5 ; −2,3] sur Reconnaissance à 0,01 %, sans
TTL) ; il n'est pas interprété (§6, variabilité d'entraînement non mesurée). Et l'écart B − C sur
Reconnaissance persiste sans les lignes à jumeau : +67,9 points [+60,4 ; +75,8] à 0,01 %.

**Ce que le TTL offrait.** Les flux normaux ont un TTL source de 31 dans 94,0 % des cas au jour 2 et
98,3 % au jour 1 ; `ct_state_ttl` vaut 1 ou 2 pour 98,7 % des attaques du jour 2 et 98,8 % de celles
du jour 1, contre 2,9 % et 0,5 % des normaux. Les familles retirées portent la même signature
(Exploits 98,3 %, Reconnaissance 99,5 %). C'est une caractéristique des hôtes générateurs du banc
d'essai plutôt qu'une signature d'attaque, comparable au risque d'apprendre une adresse IP.

- **Pour l'Isolation Forest, le TTL faisait presque toute la détection** : rappel lu à 1 % de
  42,9 % [31,7 ; 53,8] avec, 2,9 % [1,7 ; 4,3] sans ; AUC-PR 0,308 [0,170 ; 0,442] contre 0,118 [0,058 ;
  0,180]. Un TTL de 254 face à des normaux à 31 est une anomalie triviale.
- **Pour le supervisé, il faisait une partie du travail** : rappel lu à 0,1 % de l'ordre de 10 points
  plus haut avec TTL, mais les intervalles non appariés se recouvrent : l'apport n'est pas établi
  statistiquement. D'autres variables séparent aussi les attaques (importance en gain sans TTL :
  `Dload` 33,9 % en A, `ackdat` 22,9 % en B, `dmeansz` 32,0 % en C).
- **Le TTL masquait une partie de la perte sur les familles inédites** : avec TTL, B − C sur
  Reconnaissance vaut +53,6 points [+31,1 ; +62,4] à 0,01 % et +8,7 [+0,2 ; +22,6] à 0,1 ; sans TTL
  +75,9 [+69,3 ; +82,0] et +34,8 [+19,4 ; +45,6].

**Pourquoi les modèles non supervisés détectent si peu.** Sans TTL, ils sont peu au-dessus de la
prévalence et peu discernables entre eux : les écarts appariés d'AUC-PR sont −0,030 [−0,078 ; −0,011]
(petit − moyen), +0,027 [−0,042 ; +0,055] (Isolation Forest − moyen) et +0,057 [+0,010 ; +0,094]
(Isolation Forest − petit). **Le petit autoencodeur ne détecte pas mieux que le moyen**, alors que ce
dernier reconstruit les normaux tenus à l'écart 31,6 fois mieux (erreur moyenne 0,00110 contre
0,03476) : avec TTL, aucune différence ; sans TTL, l'AUC-PR du moyen est plus élevée. Reconstruire
mieux les normaux n'aide pas à détecter, sur ces données. Le meilleur non supervisé avec TTL
(Isolation Forest) ne bat les autoencodeurs que grâce au TTL (écart apparié d'AUC-PR +0,187
[+0,063 ; +0,250] contre le moyen avec TTL, +0,027 [−0,042 ; +0,055] sans).

**Calibration : le taux visé n'est pas le taux obtenu, et l'écart dépend du modèle.** Avec le budget de
référence de 0,1 % et le seuil calibré sur le jour 2, le taux observé au test sans TTL est de 0,132 %
[0,118 ; 0,148] pour l'Isolation Forest, 1,63 % [0,41 ; 3,57] pour l'autoencodeur moyen, 0,71 %
[0,21 ; 1,51] pour le petit, et de 0,058 % à 0,082 % pour le supervisé (tableau 3). Le rapport
entre le quantile 99 % des scores des normaux du test et celui des scores hors échantillon de la
calibration vaut **0,95 (Isolation Forest), 2,5 (petit) et 12 (moyen)** avec TTL, 0,95, 2,5 et 9,6
sans : plus un modèle épouse le trafic normal d'entraînement (indicateur commun, quantile 99 % dans
l'échantillon sur hors échantillon : 0,99, 0,87, 0,69 avec TTL), plus sa calibration s'effondre sur du
trafic normal qu'il n'a pas vu. **Ce sont trois observations, pas une loi.** La queue plus lourde des
normaux du jour d'entraînement est concentrée dans des flux d'état INT ou REQ en séries denses (médiane du compteur
`ct_dst_src_ltm` de 22 au jour 2, contre 2 au jour 1 pour les flux INT), dix combinaisons (protocole, état, service)
fournissent 98,5 % des dépassements du seuil.

**Dérive sur les familles connues.** À seuil calibré égal, le rappel du test est de 1,0 à 15,8 points
sous celui des attaques du jour d'entraînement tenues à l'écart (sans TTL, tableau 17). Ce n'est
pas une perte de capacité de détection pure : le taux de faux positifs du test est lui aussi plus bas
que celui de la calibration, donc les scores des normaux et ceux des attaques sont décalés ensemble.

**Fuzzers** est la famille la plus difficile pour le supervisé (rappel lu à 0,1 % : 29,8 % en A sans
TTL) : plusieurs de ses flux ont exactement les mêmes valeurs que des flux normaux (449 combinaisons
communes).

**Réponse à la question.** Un modèle qui n'a jamais vu d'attaque en détecte très peu (rappel lu à
0,1 % de faux positifs : de 0 à 1,3 % sans TTL), et le peu qu'il détecte avec le TTL est un raccourci
du banc d'essai. Un supervisé perd, sur une famille inédite, de quelques points à plusieurs dizaines de
points de rappel selon la famille et le budget, alors qu'aucune perte n'est discernable sur les familles qu'il a
vues ; mais il reste bien au-dessus de tout modèle qui n'a jamais vu d'attaque, y compris sur les
familles inédites (80,3 % [73,8 ; 87,3] pour Exploits et Reconnaissance dans C à 0,1 %, contre 0,4 %
et 1,8 % pour les autoencodeurs).

## 6. Limites et pistes d'amélioration

**Limites connues du jeu de données.**

- **Labellisation contestée.** Les étiquettes sont produites par la génération du trafic et par des
  outils, sans vérification indépendante. Ici, 1 913 lignes (463 combinaisons) de comportement
  identique portent l'étiquette normal et l'étiquette attaque ; les libellés d'un même jour ont été
  saisis en deux lots aux conventions différentes. Les normaux à TTL source 254, 2,89 % au jour 2 contre
  0,42 % au jour 1, pourraient être des flux issus des hôtes générateurs d'attaques étiquetés normaux
  (hypothèse non vérifiée). Les flux d'état INT ou REQ en séries denses étiquetés normaux au jour 2
  (médiane de `ct_dst_src_ltm` de 22) ressemblent à un profil de balayage : **hypothèse non vérifiée et
  non affirmée**, mais à signaler ; une vérification serait possible avec `srcip`, `dstip` et `dsport`,
  présents dans `data/raw`.
- **Trafic synthétique.** Les attaques sont générées par un outil (IXIA PerfectStorm) dans un banc
  d'essai ; leurs hôtes ont un TTL caractéristique (§5). Le débit (environ 80 000 flux normaux par heure)
  est celui d'un banc d'essai, non d'un réseau réel : les nombres de fausses alertes par heure sont à
  lire avec cette réserve.
- **Obsolescence des familles.** Les attaques datent de janvier et février 2015 ; les familles
  (Generic, Fuzzers, Worms...) ne reflètent pas les menaces actuelles, et Generic (67 % du volume brut
  des attaques) est presque entièrement de la redondance (89 % de copies exactes au jour 2).

**Limites de ce travail.**

- **Le protocole mesure ce qu'un raccourci identifié offrait ; il ne prouve pas qu'il n'en reste
  aucun.** Après le retrait du TTL, `Dload`, `ackdat`, `dmeansz` et l'état de la connexion portent
  encore le modèle supervisé. Une régression d'ablations n'a pas de critère d'arrêt : aucune autre
  ablation n'a été faite.
- **Variabilité d'entraînement non mesurée.** Une seule exécution par condition, un seul tirage de B ;
  XGBoost est déterministe à données fixées et les autoencodeurs ont une graine fixée. **Les petits
  écarts ne sont donc pas interprétables** : ce document n'interprète que des écarts de plusieurs
  dizaines de points (B − C sur Reconnaissance, sur Exploits à 0,01 %). Les intervalles couvrent
  l'échantillonnage du test, pas l'entraînement.
- **Le sens du temps est inversé** : entraînement sur le 18 février, test sur les 22 et 23 janvier.
  Ce n'est pas un déploiement réel (entraîner sur le passé, évaluer sur le futur) ; le choix vient du
  volume d'attaques (§3.1).
- **La calibration ne se transfère pas d'un jour à l'autre** : le budget visé est une cible, non une
  garantie ; le taux observé décide du déploiement (§5).
- **Les rappels des petites familles** (Analysis, Backdoors, Shellcode, Worms) ont des intervalles par
  blocs qui couvrent presque [0 ; 100] et ne sont pas interprétables.
- **Un seul découpage, une seule grille d'hyperparamètres** (quatre configurations, réglées sur C),
  des autoencodeurs à deux tailles seulement ; le lien entre fidélité de reconstruction et effondrement de
  la calibration repose sur trois modèles.
- **Précision et F1 par famille non définis** (§3.6) ; la précision et le F1 sont rapportés au niveau
  global.

**Pistes non traitées, identifiées.**

- **Répéter l'entraînement** sur plusieurs graines et plusieurs tirages de B (le protocole supervisé
  complet coûte quelques minutes) pour mesurer la variabilité d'entraînement.
- **Transformation des durées de handshake.** `log1p` est appliqué à `ackdat`, `tcprtt` et `synack` sans
  effet notable sur 99 % de leurs valeurs, car leurs valeurs typiques sont de l'ordre de 10⁻⁴ à 10⁻¹ :
  une transformation qui tient compte de l'échelle (par exemple `log(x + ε)` calé sur l'entraînement)
  reste à tester.
- **Gradation de la capacité de l'autoencodeur** (nombre d'epochs, tailles intermédiaires) pour tester
  si l'effondrement de la calibration est monotone en la fidélité.
- **Vérifier l'hypothèse de balayage** et l'origine des normaux à TTL 254 avec les adresses et ports
  exclus des variables.
- **Découpage dans le sens du temps** (entraîner sur janvier, tester sur février) si le volume le permet.

## 7. Reproduction

Les commandes ci-dessous sont celles qui ont produit les résultats de ce document ; toutes les valeurs
qui influencent un résultat (chemins, graines, seuils, hyperparamètres) sont dans `config.toml` (et
`config_sans_ttl.toml`, qui n'écrit que ses différences).

**Prérequis** : Python 3.12, environ 8 Go de RAM (la préparation atteint environ 4,5 Go), aucun GPU. Le
temps de calcul varie d'un facteur 3 selon le moment sur la machine utilisée (mesuré) ; les durées
ci-dessous sont indicatives.

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt     # versions figées ; PyTorch en version CPU
# Placer les fichiers du jeu dans data/raw/ (voir §2), puis :

# 1. Préparation (86 s) : découpage, déduplication, jeux unsup, A, B, C et test ; contrôles d'intégrité
venv/bin/python src/prepare.py
venv/bin/python src/verify_prepare.py

# 2. Modèles, version AVEC les colonnes TTL
venv/bin/python src/models/isolation_forest.py    # 46 s
venv/bin/python src/models/autoencoder.py         # deux architectures : petit de 5,5 à 11,8 min, moyen de 12,5 à 31 min selon le moment
venv/bin/python src/models/supervised.py          # recherche d'hyperparamètres sur C, puis A, B, C : 13 min

# 3. Version SANS les colonnes TTL (résultat principal). Nécessite l'étape 2 : elle réutilise la
#    configuration retenue par la recherche du supervisé (results/supervised_search.json)
venv/bin/python src/prepare.py --config config_sans_ttl.toml
venv/bin/python src/verify_prepare.py --config config_sans_ttl.toml
venv/bin/python src/models/isolation_forest.py --config config_sans_ttl.toml
venv/bin/python src/models/supervised.py --config config_sans_ttl.toml --skip-tuning
venv/bin/python src/models/autoencoder.py --config config_sans_ttl.toml

# 4. Intervalles par blocs de temps et tables de ce document
for c in config.toml config_sans_ttl.toml; do
  venv/bin/python src/paired_bootstrap.py --config $c
  venv/bin/python src/block_ci.py --config $c
done
venv/bin/python src/compare_ablation.py
venv/bin/python src/report_tables.py
```

Les jeux et les résultats sont écrits dans `data/processed/` (avec TTL) et `data/processed_sans_ttl/`,
ignorés par git. Les résultats sont reproductibles : le petit autoencodeur relancé seul donne des scores
identiques bit à bit, la préparation donne un manifeste identique et un tirage de B identique.

**Audits des données** (chaque script correspond à une entrée du journal) : `inspect_raw.py`
(effectifs, colonnes, libellés), `inspect_time.py` (répartition entre les deux jours),
`inspect_duplicates.py` et `inspect_plafond.py` (doublons, contradictions, plafond), `ic_rappel.py`,
`inspect_columns.py`, `inspect_skew.py`, `inspect_debit.py`, `inspect_normals.py`, `inspect_ttl.py`,
`bench_autoencoder.py` et `bench_supervised.py` (coûts).

**Organisation du dépôt** : `src/prepare.py` (données), `src/models/` (`isolation_forest.py`,
`autoencoder.py`, `supervised.py`, `calibration.py`), `src/evaluate.py` (seuils, métriques, jumeaux),
`config*.toml`, `report/mesures.md` (journal de mesures).

**Non encore écrit** : un `Makefile` qui enchaîne ces commandes, un script `src/download.py` (le
téléchargement est manuel, voir §2) et le notebook `notebooks/resultats.ipynb`.
