# Journal de mesures

Une entrée par mesure, datée, avec la commande exacte. Rien d'estimé.
Les résultats qui contredisent une hypothèse restent écrits.

Environnement : Python 3.12.13, bibliothèque standard uniquement (le venv est
vide à cette date). Les commandes sont lancées depuis la racine du dépôt.

---

## M01 — Audit des CSV bruts UNSW-NB15 (2026-09-18)

Données : `data/raw/UNSW-NB15_{1,2,3,4}.csv` + `NUSW-NB15_features.csv`,
récupérés depuis le SharePoint officiel. Les CSV n'ont pas d'en-tête ; le
fichier 1 commence par un BOM UTF-8 (`ef bb bf`), lu avec `utf-8-sig`.

Commande :

    python3 src/inspect_raw.py

### 1. Nombre d'enregistrements

- UNSW-NB15_1.csv : 700 001
- UNSW-NB15_2.csv : 700 001
- UNSW-NB15_3.csv : 700 001
- UNSW-NB15_4.csv : 440 044
- Total : **2 540 047**. Valeur officielle : 2 540 044. **Écart : +3.**

Cause de l'écart, vérifiée par la commande ci-dessous : la dernière ligne des
fichiers 1, 2 et 3 est identique (octet pour octet, hors `\r`) à la première
ligne du fichier suivant. Ce sont 3 enregistrements comptés deux fois à la
jonction des fichiers. 2 540 047 − 3 = 2 540 044, soit la valeur officielle.

    cd data/raw && for i in 1 2 3; do j=$((i+1)); [ "$(tail -n1 UNSW-NB15_$i.csv | tr -d '\r')" = "$(head -n1 UNSW-NB15_$j.csv | tr -d '\r')" ] && echo oui || echo non; done

Résultat : `oui`, `oui`, `oui`.

Conséquence pour `prepare.py` : ces 3 doublons de jonction sont à retirer à la
concaténation (supprimer la première ligne des fichiers 2 à 4), sans quoi
chaque enregistrement concerné est compté deux fois.

Observation annexe, non explorée : `sort | uniq -d` trouve des lignes
identiques *à l'intérieur* de chaque fichier (nombre de lignes distinctes
apparaissant plusieurs fois : 33 306, 15 241, 24 034 et 15 627 pour les
fichiers 1 à 4). Ce n'est pas l'écart de 3 ci-dessus. Leur traitement (les
conserver ou non) est une décision à prendre avant le découpage, car des
doublons répartis entre entraînement et test sont une forme de fuite.

    cd data/raw && for i in 1 2 3 4; do sed 's/\r$//' UNSW-NB15_$i.csv | sort | uniq -d | wc -l; done

### 2. Nombre de colonnes

- Chaque ligne des 4 CSV compte 49 champs (2 540 047 lignes sur 2 540 047).
- `NUSW-NB15_features.csv` déclare 49 features. **Cohérent.**
- Colonnes 48 et 49 : `attack_cat` et `Label`.
- Défaut de nommage dans le fichier features : la colonne 44 s'appelle
  `ct_src_ ltm` (avec une espace). À normaliser en `ct_src_ltm` lors du
  chargement. Le champ « Type » du même fichier a aussi une espace finale dans
  son en-tête (`Type `), sans conséquence ici.

### 3. Effectifs par `attack_cat` (valeurs brutes) et contrôle par `Label`

Label global : 0 → 2 218 764 ; 1 → 321 283 (sur les 2 540 047 lignes, doublons
de jonction inclus).

Valeurs brutes de `attack_cat`, telles qu'écrites dans les fichiers
(l'espace compte, les libellés sont entre apostrophes) :

- `''` (vide) : 2 218 764, tous Label=0
- `' Fuzzers'` : 5 051, tous Label=1
- `' Fuzzers '` : 19 195, tous Label=1
- `' Reconnaissance '` : 12 228, tous Label=1
- `' Shellcode '` : 1 288, tous Label=1
- `'Analysis'` : 2 677, tous Label=1
- `'Backdoor'` : 1 795, tous Label=1
- `'Backdoors'` : 534, tous Label=1
- `'DoS'` : 16 353, tous Label=1
- `'Exploits'` : 44 525, tous Label=1
- `'Generic'` : 215 481, tous Label=1
- `'Reconnaissance'` : 1 759, tous Label=1
- `'Shellcode'` : 223, tous Label=1
- `'Worms'` : 174, tous Label=1

Contrôle croisé : le trafic normal correspond exactement à `attack_cat` vide
(2 218 764 = 2 218 764), et toute ligne à `attack_cat` non vide a Label=1
(321 283 au total). Aucune contradiction entre les deux colonnes.

### 4. Incohérences de libellés

14 variantes brutes pour 10 catégories d'attaque + le normal.

- Espaces parasites : `' Fuzzers'` et `' Fuzzers '` (deux variantes),
  `' Reconnaissance '`, `' Shellcode '`. Sans `strip()`, Fuzzers, Reconnaissance
  et Shellcode sont chacun scindés en deux classes distinctes.
- Après `strip().lower()` : 11 valeurs (normal + 10 catégories), avec les
  effectifs suivants : Fuzzers 24 246 ; Reconnaissance 13 987 ; Shellcode
  1 511 ; Analysis 2 677 ; DoS 16 353 ; Exploits 44 525 ; Generic 215 481 ;
  Worms 174 ; Backdoor 1 795 ; Backdoors 534.
- **`Backdoor` (1 795) et `Backdoors` (534) subsistent comme deux libellés
  distincts après normalisation.** Le fichier features parle de « Backdoors ».
  La fusion en une seule famille (2 329 au total) n'est pas faite ici : c'est
  une décision de préparation à prendre et à documenter.
- La casse seule n'est pas en cause dans ces données (aucune variante ne
  diffère uniquement par la casse) ; le défaut porte sur les espaces et sur le
  singulier/pluriel de Backdoor(s).
- Le fichier features liste « Backdoors, DoS Exploits, ... » : la virgule
  manquante entre DoS et Exploits est une coquille de la documentation ; ce
  sont bien deux catégories dans les données.

Les effectifs ci-dessus incluent les 3 doublons de jonction ; leur catégorie
n'a pas été identifiée dans cette mesure.

---

## M02 — Répartition temporelle des CSV entre les deux jours (2026-09-18)

Colonne `Stime` (29), horodatage Unix converti en UTC. Le fuseau d'origine
n'est pas documenté ; toutes les dates ci-dessous sont en UTC.

Commande :

    python3 src/inspect_time.py

Par fichier :

- UNSW-NB15_1.csv : 2015-01-22 11:49:37 → 2015-01-22 19:44:02 ; 700 001 lignes,
  toutes le 22-01.
- UNSW-NB15_2.csv : 2015-01-22 19:43:15 → 2015-02-18 03:45:29 ; **à cheval sur
  les deux jours** : 352 862 lignes le 22-01, 34 340 le 23-01, 312 799 le 18-02.
- UNSW-NB15_3.csv : 2015-02-18 03:44:59 → 2015-02-18 09:00:09 ; 700 001 lignes,
  toutes le 18-02.
- UNSW-NB15_4.csv : 2015-02-18 08:59:44 → 2015-02-18 12:21:08 ; 440 044 lignes,
  toutes le 18-02.

Total par jour : 22-01 : 1 052 863 ; 23-01 : 34 340 (uniquement du normal) ;
18-02 : 1 452 844. Somme : 2 540 047 (doublons de jonction inclus).

Les fichiers ne sont donc pas alignés sur les jours : la frontière entre les
deux simulations tombe au milieu du fichier 2. Un découpage par jour se fait
sur `Stime`, pas sur le numéro de fichier.

Les fichiers ne sont pas triés par `Stime` (test de monotonie faux pour les 4)
et se chevauchent d'environ une minute aux jonctions (max du fichier 1 :
19:44:02, min du fichier 2 : 19:43:15). Tout découpage temporel doit trier ou
filtrer sur `Stime` explicitement.

Écart avec le ReadMe : celui-ci parle de la simulation du **17**-2-2015 ; dans
les données, tous les enregistrements du second jour ont un `Stime` le
**18**-02 en UTC (03:44 → 12:21). Cause non élucidée (fuseau d'enregistrement ?
date du ReadMe approximative ?). Ne pas affirmer l'une ou l'autre dans le README.

### Familles par jour (libellés après `strip()`)

Jour 1 (22-01, 23-01 inclus) : normal 1 064 988 (1 030 648 le 22-01 + 34 340
le 23-01) ; Analysis 526 ; Backdoors 534 ; DoS 1 167 ;
Exploits 5 409 ; Fuzzers 5 051 ; Generic 7 522 ; Reconnaissance 1 759 ;
Shellcode 223 ; Worms 24. Total attaques jour 1 : 22 215.

Jour 2 (18-02) : normal 1 153 776 ; Analysis 2 151 ; Backdoor 1 795 ;
DoS 15 186 ; Exploits 39 116 ; Fuzzers 19 195 ; Generic 207 959 ;
Reconnaissance 12 228 ; Shellcode 1 288 ; Worms 150. Total attaques jour 2 :
299 068.

Contrôle : 22 215 + 299 068 = 321 283 attaques ; 1 064 988 + 1 153 776 =
2 218 764 normaux. Les deux coïncident avec M01.

Deux constats :

1. **Les 9 familles sont présentes les deux jours, mais dans des proportions
   très différentes.** Generic : 7 522 le jour 1 contre 207 959 le jour 2.
   Worms : 24 contre 150. Le jour 1 ne contient que 22 215 attaques sur
   1 087 203 enregistrements.
2. **Les variantes de libellés de M01 correspondent aux jours, pas au hasard.**
   `Backdoors` (534) n'apparaît que le jour 1 et `Backdoor` (1 795) que le
   jour 2 ; `' Fuzzers'` (5 051), `'Reconnaissance'` (1 759) et `'Shellcode'`
   (223) sont les libellés du jour 1, `' Fuzzers '` (19 195),
   `' Reconnaissance '` (12 228) et `' Shellcode '` (1 288) ceux du jour 2
   (mêmes effectifs que dans M01, constat fait par recoupement des deux
   sorties). L'étiquetage a donc été fait en deux lots avec des conventions
   d'écriture différentes. `Backdoor` et `Backdoors` ne coexistent jamais le
   même jour : c'est un même libellé écrit de deux façons, non deux familles.

Note : les chiffres du jour 1 « normal » ci-dessus ont été recalculés à la
main à partir de la sortie du script (1 030 648 + 34 340) ; le script ne
donne que les deux composantes par date.

---

## M03 — Fusion Backdoor / Backdoors : état de la vérification (2026-09-18)

Critère posé : fusionner si l'article MilCIS 2015 (Moustafa & Slay) compte
neuf familles.

- **L'article lui-même n'a pas pu être lu** (IEEE Xplore et Semantic Scholar
  n'ont renvoyé aucun texte). Le critère n'est donc pas vérifié sur la source
  demandée.
- Ce qui a été lu : la page du projet UNSW-NB15 (UNSW Research,
  https://research.unsw.edu.au/projects/unsw-nb15-dataset), qui liste
  « Fuzzers, Analysis, Backdoors, DoS, Exploits, Generic, Reconnaissance,
  Shellcode and Worms », soit **neuf** familles, avec « Backdoors » au pluriel.
  Ce n'est pas l'article ; c'est le même auteur et le même jeu.
- Le fichier features du jeu dit aussi neuf catégories (« nine categories »)
  et écrit « Backdoors ».
- Le recoupement de M02 (Backdoor et Backdoors ne coexistent jamais le même
  jour) va dans le même sens.

Décision proposée, à confirmer après lecture de l'article : fusionner en
`Backdoors` (2 329 enregistrements : 534 + 1 795, doublons de jonction inclus).
Rien n'est encore fusionné dans le code (`prepare.py` n'existe pas).

---

## M04 — Points du ReadMe à reprendre dans le README du dépôt (2026-09-18)

Source : `data/raw/ReadMe.pdf`, lu en entier.

- **Licence.** Usage libre « for academic research purposes », à perpétuité ;
  « Use for commercial purposes is strictly prohibited » ; Nour Moustafa
  conserve ses droits d'auteur.
- **Citation obligatoire de deux articles :**
  1. Moustafa & Slay, « UNSW-NB15: a comprehensive data set for network
     intrusion detection systems (UNSW-NB15 network data set) », Military
     Communications and Information Systems Conference (MilCIS), 2015, IEEE.
  2. Moustafa & Slay, « The evaluation of Network Anomaly Detection Systems:
     Statistical analysis of the UNSW-NB15 data set and the comparison with the
     KDD99 data set », Information Security Journal: A Global Perspective, 2016,
     pp. 1-14.
- **Génération.** Paquets bruts produits avec l'outil IXIA PerfectStorm, au
  Cyber Range Lab de l'ACCS (Australian Centre for Cyber Security), pour
  produire « a hybrid of real modern normal activities and synthetic
  contemporary attack activities » : trafic normal réel, attaques synthétiques.
- **Deux jours de simulation :** 22-1-2015 et 17-2-2015 (voir M02 pour l'écart
  de date constaté dans les données).
- Le ReadMe renvoie à l'article MilCIS pour la description des catégories et ne
  tranche pas la question Backdoor/Backdoors.
- Le jeu est distribué en pcap, Bro, Argus et CSV ; les 4 CSV sont ceux « for
  classification purposes ».
