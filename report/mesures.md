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

---

## M05 — Décisions de protocole (2026-09-18)

Décisions prises par l'auteur du projet, sur la base de M01 à M03. Ce ne sont
pas des mesures ; elles sont consignées pour tracer ce qui a été décidé avant
d'écrire `prepare.py`.

1. **Backdoor et Backdoors sont fusionnés** en `Backdoors`. Justification :
   preuve interne (M02) : les deux orthographes correspondent aux deux lots
   d'étiquetage (un par jour) et ne coexistent jamais ; la page officielle du
   projet et le fichier features annoncent neuf catégories. L'article MilCIS
   n'a pas été lu (voir M03) ; la décision ne s'appuie pas dessus. Cette entrée
   remplace le « à confirmer » de M03. Les libellés sont aussi normalisés par
   `strip()` (M01).
2. **Découpage temporel.** Entraînement : jour 2 (18-02, `Stime` ≥ 2015-02-18
   00:00 UTC). Test : jour 1 (22-01 + 23-01). Justification : le jour 1 n'a que
   22 215 attaques (M02), insuffisant pour entraîner. Conséquence à garder en
   tête : le jour 1 étant petit en attaques, certaines familles y ont peu
   d'exemples (Worms : 24, Shellcode : 223, Backdoors : 534, Analysis : 526,
   d'après M02, doublons de jonction inclus). Les effectifs de test définitifs
   sortiront de `prepare.py` et seront consignés à ce moment-là.
3. **Deux conditions sur la même partition**, pour ne pas confondre deux effets :
   - *témoin* : le supervisé s'entraîne sur toutes les familles du jour 2 ;
     ses résultats mesurent la dérive temporelle seule ;
   - *traitement* : une ou plusieurs familles sont retirées de
     l'entraînement supervisé ; l'écart avec le témoin isole l'effet « famille
     inédite ».
   Le choix des familles retirées reste à faire et à justifier (règle du
   projet : pas de tirage au hasard).
4. **Doublons** : décision différée jusqu'aux mesures de M06.

---

## M06 — Doublons exacts et contradictions d'étiquetage (2026-09-18)

Commande (24 s) :

    python3 src/inspect_duplicates.py

Le script écarte d'abord les 3 doublons de jonction (il vérifie qu'ils sont
identiques à la dernière ligne du fichier précédent), soit 2 540 044 lignes
lues. Les étiquettes sont comparées après `strip()`, minuscules et fusion
Backdoor → Backdoors. Les lignes et features sont comparées par empreinte
blake2b de 8 octets (risque de collision négligeable à cette taille, non
vérifié ligne à ligne).

### A. Vrais doublons (identiques sur les 49 colonnes)

- Lignes distinctes : 2 059 414.
- **Lignes en surplus : 480 630**, soit ce qu'on retire en gardant un seul
  exemplaire de chaque (2 540 044 − 2 059 414).
- Lignes distinctes présentes plusieurs fois : 88 207.
- Lignes distinctes présentes à la fois au jour 1 et au jour 2 : 0. Ce zéro est
  garanti par construction : `Stime` fait partie des 49 colonnes et diffère
  d'un jour à l'autre. **Il ne dit rien sur les doublons entre jours une fois
  les identifiants et horodatages écartés**, qui n'ont pas été mesurés.

### B. Contradictions d'étiquetage (features identiques, étiquettes différentes)

Sur les 47 features seules (colonnes 1 à 47, sans `attack_cat` ni `Label`) :

- Combinaisons de features distinctes : 2 048 616.
- Combinaisons présentes plusieurs fois : 84 948.
- **Combinaisons à étiquettes contradictoires : 2 251, couvrant 40 322 lignes.**
- Dont normal contre attaque : **0**. Dont famille d'attaque contre autre
  famille : 2 251 (40 322 lignes). Le `Label` binaire n'est donc jamais
  contradictoire ; seule l'attribution de la famille l'est.
- Combinaisons typiques : Exploits/Generic (80), DoS/Exploits (71),
  Exploits/Reconnaissance (56), Exploits/Fuzzers (36). Les plus nombreuses
  (1 234) mélangent 7 familles à la fois (Analysis, Backdoors, DoS, Exploits,
  Fuzzers, Generic, Reconnaissance) : ce sont des flux identiques que
  l'étiquetage a attribués à des familles différentes.

Variante ajoutée, hors demande, parce que `Stime` et `Ltime` empêchent deux
flux d'être « identiques » dès qu'ils diffèrent d'une seconde. Sans ces deux
colonnes (45 colonnes) : 2 036 323 combinaisons distinctes, 74 895 présentes
plusieurs fois, **2 177 contradictoires couvrant 40 322 lignes** (le même
nombre de lignes que sur 47 colonnes), toutes famille contre famille, aucune
normal contre attaque. Ce n'est pas un choix de features de modélisation : ces
colonnes sont simplement retirées pour voir si les horodatages masquaient des
contradictions.

### Lecture

Les deux phénomènes sont de nature différente. Les 480 630 lignes en surplus
sont de la redondance : elles biaisent l'évaluation si des copies se retrouvent
des deux côtés du découpage, mais ne contredisent rien. Les 40 322 lignes
contradictoires posent un problème d'étiquetage : un classifieur parfait ne peut
pas toutes les prédire correctes, ce qui plafonne les scores par famille sur ces
lignes. Sur les 47 features, la contradiction ne touche que l'attribution de la
famille, jamais normal contre attaque ; **cette dernière conclusion est
invalidée par M07** dès qu'on retire les identifiants (IP, ports).

---

## M07 — Contradictions sur les features comportementales (2026-09-18)

Remarque de l'auteur : les colonnes 1-47 contiennent srcip, dstip, sport,
dsport, Stime et Ltime, qui rendent deux flux « identiques » improbables. B ne
mesure donc pas la question posée. C l'exclut.

Le script `src/inspect_duplicates.py` a été étendu (sortie additive : A, B et
la variante 45 colonnes de M06 sont reproduits à l'identique, 480 630 surplus,
2 251 et 2 177 combinaisons contradictoires). Commande (46 s) :

    python3 src/inspect_duplicates.py

### Colonnes exclues pour C (numéros 1-indexés du fichier features)

Exclues : 1 srcip, 2 sport, 3 dstip, 4 dsport, 29 Stime, 30 Ltime. Restent 41
colonnes : proto, state, dur, sbytes, dbytes, sttl, dttl, sloss, dloss,
service, Sload, Dload, Spkts, Dpkts, swin, dwin, stcpb, dtcpb, smeansz,
dmeansz, trans_depth, res_bdy_len, Sjit, Djit, Sintpkt, Dintpkt, tcprtt,
synack, ackdat, is_sm_ips_ports, ct_state_ttl, ct_flw_http_mthd, is_ftp_login,
ct_ftp_cmd, ct_srv_src, ct_srv_dst, ct_dst_ltm, ct_src_ltm, ct_src_dport_ltm,
ct_dst_sport_ltm, ct_dst_src_ltm.

Variante C' (à valider) : C sans 21 stcpb ni 22 dtcpb, les numéros de séquence
TCP initiaux, tirés au hasard à chaque connexion. 39 colonnes.

Deux réserves de définition, non tranchées par les mesures : les colonnes
`ct_*` sont des compteurs de contexte (connexions récentes) et non des
propriétés du flux seul ; elles sont conservées dans C et C'. Et l'identité est
testée à l'égalité exacte des valeurs, y compris flottantes à plusieurs
décimales : c'est une définition stricte, donc le nombre de contradictions
trouvé est un minimum par rapport à une égalité « à peu près ».

### Résultats (2 540 044 lignes, doublons de jonction écartés)

C (41 colonnes) :

- combinaisons distinctes : 2 016 862 ; présentes plusieurs fois : 76 218 ;
- **combinaisons à étiquettes contradictoires : 2 579, couvrant 42 282 lignes** ;
- **dont normal contre attaque : 453 combinaisons, 1 879 lignes** ;
- dont famille contre famille : 2 126 combinaisons, 40 403 lignes.

Sur normal contre attaque, la paire (normal, Fuzzers) représente 449 des 453
combinaisons ; les 4 autres opposent normal à une autre famille (non détaillé
dans la sortie).

C' (39 colonnes) : 2 016 850 combinaisons distinctes ; contradictions
**identiques à C** (2 579 combinaisons, 42 282 lignes, 453 normal contre
attaque pour 1 879 lignes). Retirer stcpb et dtcpb ne change rien aux
contradictions : ils n'étaient pas discriminants ici.

Comparaison B → C : les contradictions famille contre famille sont du même
ordre (40 322 lignes contre 40 403). **Ce qui apparaît avec C, c'est le normal
contre attaque : 0 sur B, 453 combinaisons sur C.** Le B nul sur ce point venait
bien des identifiants, comme le supposait l'auteur ; en revanche B n'était pas
nul en général (2 251) parce que des flux de la même seconde, avec les mêmes
IP et ports, existent.

### Doublons entre les deux jours

Pour A, B, B', C et C' : **0 combinaison présente aux deux jours**, donc aucune
copie comportementale identique entre entraînement (jour 2) et test (jour 1)
selon cette définition stricte. Contrôle de plausibilité du mécanisme, sur des
sous-ensembles de colonnes plus étroits (script jetable, non versionné, dans le
répertoire temporaire de la session, non reproductible depuis le dépôt) :
jour 1 = 1 087 202 lignes, jour 2 = 1 452 842 ; sur proto+state+service :
174 groupes sur 184 communs aux deux jours ; sur 10 colonnes (proto, state,
service, sttl, dttl, sbytes, dbytes, Spkts, Dpkts, dur) : 63 292 groupes
communs, dont 382 258 lignes du jour 1. Le détecteur inter-jours fonctionne
donc. Quelle colonne, parmi les 41, fait tomber les recoupements à zéro n'a pas
été cherché.

---

## M08 — Décisions sur doublons et contradictions, et mesures associées (2026-09-18)

### Décisions de l'auteur (M05 suite)

1. **Doublons exacts (A) : supprimés, après le découpage temporel** (un
   exemplaire conservé par côté), pour ne pas déséquilibrer arbitrairement
   les deux jeux.
2. **Contradictions (C) : conservées.** Ce n'est pas du bruit à nettoyer mais
   une propriété du jeu ; elles constituent une borne supérieure de
   performance (voir plus bas, avec une correction de formulation).
3. **`ct_*`, `stcpb` et `dtcpb` conservés** comme features : ce sont des
   features de contexte, pas des identifiants.
4. **srcip, dstip, sport, dsport, Stime, Ltime exclus des features
   d'entraînement.** Un modèle qui apprendrait qu'une IP est malveillante
   aurait mémorisé la machine du banc d'essai, non une signature. `Stime` sert
   au découpage, pas à l'apprentissage. Le modèle voit donc les 41 colonnes de
   M07 (moins les cibles).

### Mesure 1 — Lignes supprimées de chaque côté par la déduplication exacte

Commande (26 s) :

    python3 src/inspect_plafond.py

Déduplication sur les 49 colonnes, appliquée séparément à chaque côté, après
retrait des 3 doublons de jonction.

- **Jour 2 (entraînement)** : 1 452 842 lignes avant, **416 624 supprimées**
  (28,7 %), 1 036 218 après.
- **Jour 1 (test)** : 1 087 202 lignes avant, **64 006 supprimées** (5,9 %),
  1 023 196 après.
- Contrôle : 416 624 + 64 006 = 480 630, le surplus de M06. Aucun doublon ne
  traversait les deux jours (M06), donc le résultat ne dépend pas de l'ordre
  découpage/déduplication pour ce décompte ; il dépend en revanche du côté.
- Les 3 doublons de jonction sont tous du normal : 1 au jour 1 (normal
  1 064 988 → 1 064 987), 2 au jour 2 (normal 1 153 776 → 1 153 774), par
  différence avec M02.

Lignes supprimées par classe, jour 2 : normal 202 921 ; Generic 185 414 ;
Exploits 15 559 ; DoS 10 346 ; Fuzzers 1 391 ; Reconnaissance 611 ;
Analysis 268 ; Backdoors 111 ; Worms 3 ; Shellcode 0.
Jour 1 : normal 56 069 ; Generic 4 689 ; Exploits 1 367 ; Fuzzers 1 060 ;
DoS 342 ; Backdoors 235 ; Analysis 225 ; Reconnaissance 19 ; Shellcode 0 ;
Worms 0.

Effectifs d'attaques restants par famille (calcul par différence entre M02 et
les suppressions ci-dessus, non imprimés tels quels par le script) :

- Jour 2 (entraînement), 85 365 attaques au total : Generic 22 545 ; Exploits
  23 557 ; Fuzzers 17 804 ; Reconnaissance 11 617 ; DoS 4 840 ; Analysis
  1 883 ; Backdoors 1 684 ; Shellcode 1 288 ; Worms 147.
- Jour 1 (test), 14 278 attaques au total : Exploits 4 042 ; Fuzzers 3 991 ;
  Generic 2 833 ; Reconnaissance 1 740 ; DoS 825 ; Analysis 301 ; Backdoors
  299 ; Shellcode 223 ; Worms 24.

Ce que la déduplication change, en clair :

- Les attaques du jour 2 passent de 299 068 à 85 365 (−71 %). **Generic passe
  de 207 959 à 22 545** : il représentait environ 70 % des attaques du jour 2
  avant, environ 26 % après (calcul arithmétique sur ces effectifs). L'énorme
  volume de Generic était presque entièrement des copies exactes.
- Part d'attaques dans l'entraînement : environ 20,6 % avant, 8,2 % après ;
  dans le test : environ 2,0 % avant, 1,4 % après.
- Le déséquilibre entre les deux côtés est réel et non arbitraire : 28,7 % de
  lignes supprimées à l'entraînement contre 5,9 % au test. Il vient de la
  nature du jeu (le jour 2 concentre les copies).
- Worms (147 en entraînement, 24 en test) et Shellcode (1 288 en
  entraînement, 223 en test) n'ont quasiment pas de doublons exacts et sont
  inchangés ou presque.

### Mesure 2 — Plafond de performance dû aux contradictions (borne supérieure)

Même commande. Définition : sur les 41 features retenues, des lignes
identiques à étiquettes différentes reçoivent la même sortie de tout modèle
qui est une fonction de ces 41 colonnes (le codage et la normalisation ne
peuvent que confondre des valeurs, jamais séparer deux valeurs identiques).
Au mieux, un modèle classe correctement la classe majoritaire de chaque
groupe ; le minimum d'erreurs est donc, par groupe, effectif − effectif de la
classe majoritaire. Calculé côté par côté, en connaissant les étiquettes du
côté évalué : c'est une borne oracle, pas un score atteignable.

**Correction de formulation.** Les 1 879 lignes normal/attaque
indiscernables ne sont pas toutes forcément mal classées : un modèle en
classe correctement une partie (la majorité de chaque groupe). Le minimum
d'erreurs binaires est de **706 avant déduplication** (652 en entraînement +
54 en test) et de **702 après** (648 + 54), pas de 1 879. Vérification de
cohérence avec M07 : avant déduplication, 1 738 + 141 = 1 879 lignes en
406 + 47 = 453 combinaisons.

Après déduplication (le cas retenu) :

- **Test (jour 1)**, 1 023 196 lignes : 47 combinaisons normal+attaque
  (140 lignes) ; **54 erreurs binaires minimales**, soit une accuracy
  binaire maximale de **99,9947 %**, c'est-à-dire 0,0053 point perdu.
  Règle majoritaire : 17 faux positifs, 11 faux négatifs, 25 groupes ex
  aequo (26 erreurs, à répartir entre FP et FN). Taux de faux positifs
  plancher : 0,0017 % des normaux. Rappel plafond sur les attaques : 99,9230 %
  (hors ex aequo). Les 11 faux négatifs sont tous du Fuzzers.
- **Entraînement (jour 2)**, 1 036 218 lignes : 406 combinaisons
  normal+attaque (1 729 lignes) ; 648 erreurs binaires minimales ; accuracy
  maximale 99,9375 % (0,0625 point perdu). Faux négatifs de la règle
  majoritaire : 227, tous du Fuzzers. Cette borne ne limite pas le score de
  test ; elle dit combien de bruit d'étiquette le modèle supervisé voit à
  l'entraînement.
- **Au niveau des familles (multiclasse)**, le plafond est plus bas : 337
  combinaisons à plusieurs classes au test (1 499 lignes), au minimum 1 121
  erreurs, soit une accuracy multiclasse maximale de 99,8904 %. Rapporté aux
  14 278 attaques du test, ces erreurs représentent **au plus 7,9 %**
  d'attaques dont la famille est irréductiblement ambiguë (le total compte
  aussi d'éventuelles erreurs sur des normaux ; la part exacte par famille
  n'est pas calculée). En entraînement : 10 414 erreurs, accuracy multiclasse
  maximale 98,9950 %.

Avant déduplication, mêmes grandeurs : test 54 erreurs binaires (99,9950 %),
2 591 erreurs multiclasses ; entraînement 652 (99,9551 %) et 21 256.

Lecture :

- En points d'accuracy binaire, la borne est quasi nulle (0,0053 point au
  test) : **les contradictions normal/attaque ne limitent pas sérieusement le
  score global**. L'accuracy est de toute façon la mauvaise mesure ici ; le
  plafond intéressant est celui des Fuzzers (le seul type d'attaque qui se
  retrouve classé « normal » par la majorité : 11 lignes au test) et celui des
  familles entre elles.
- Ce plafond est une borne supérieure : il ne compte que les lignes
  *exactement* identiques sur les 41 colonnes. Des lignes très proches mais
  non identiques, que le modèle ne sait pas séparer, ne sont pas comptées.
  Le plafond réel est donc inférieur ou égal à ces valeurs.
- Ces plafonds sont à rapporter tels quels dans le README (section
  limites), à côté de la mention de la labellisation contestée.
