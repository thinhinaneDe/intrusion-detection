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

---

## M09 — Copies exactes par famille, et précision atteignable par famille au test (2026-09-18)

Commande (9 s) :

    python3 src/ic_rappel.py

Même chaîne que M08 (découpage temporel, puis déduplication exacte sur 49
colonnes par côté). Les effectifs par famille sont ici mesurés directement ;
ils coïncident avec ceux calculés par différence en M08.

### Résultat sur la qualité du jeu : la majorité des attaques Generic du jour 2 sont des copies exactes

Ce n'est pas seulement une étape de nettoyage : c'est une propriété du jeu,
à rapporter comme telle dans le README.

Part de lignes supprimées par la déduplication exacte, par famille.

Jour 2 (entraînement) : **Generic 89,2 % (185 414 sur 207 959, il en reste
22 545)** ; DoS 68,1 % (10 346 sur 15 186) ; Exploits 39,8 % (15 559 sur
39 116) ; Analysis 12,5 % ; Fuzzers 7,2 % ; Backdoors 6,2 % ; Reconnaissance
5,0 % ; Worms 2,0 % ; Shellcode 0 % ; normal 17,6 % (202 921 sur 1 153 774).

Jour 1 (test) : **Generic 62,3 % (4 689 sur 7 522)** ; Backdoors 44,0 % ;
Analysis 42,8 % ; DoS 29,3 % ; Exploits 25,3 % ; Fuzzers 21,0 % ;
Reconnaissance 1,1 % ; Shellcode 0 % ; Worms 0 % ; normal 5,3 % (56 069 sur
1 064 987).

Les taux diffèrent beaucoup entre les deux jours pour une même famille
(Generic : 89,2 % contre 62,3 % ; Backdoors : 6,2 % contre 44,0 %), ce qui
ne se réduit pas à une propriété de la famille. Ce qui produit ces copies (une
même trame journalisée plusieurs fois, un outil de génération qui répète un
flux identique, ou autre) n'a pas été investigué : la mesure établit
l'existence des copies, pas leur cause. Il s'agit de copies sur les 49
colonnes, c'est-à-dire aussi mêmes IP, mêmes ports, même seconde.

### Effectifs du test après déduplication (jour 1)

Attaques : 14 278 au total. Exploits 4 042 ; Fuzzers 3 991 ; Generic 2 833 ;
Reconnaissance 1 740 ; DoS 825 ; Analysis 301 ; Backdoors 299 ; Shellcode 223 ;
Worms 24. Normal : 1 008 918.

### Intervalle de confiance à 95 % d'un rappel hypothétique de 0,80

Le rappel de 0,80 est une hypothèse de travail choisie pour comparer la
précision de mesure des familles entre elles. **Ce n'est pas une performance
mesurée ni attendue.** Les intervalles dépendent seulement de l'effectif de
test. Wilson, avec p = 0,80 ; contrôle par le Clopper-Pearson exact avec
k = arrondi(0,80 × n) succès (donc un rappel observé k/n très légèrement
différent de 0,80).

- Worms, n = 24 : Wilson [0,604 ; 0,913], demi-largeur 15,4 points ; exact
  (k = 19) [0,578 ; 0,929].
- Shellcode, n = 223 : [0,743 ; 0,847], ±5,2 points ; exact (k = 178)
  [0,739 ; 0,849].
- Backdoors, n = 299 : [0,751 ; 0,841], ±4,5 points ; exact (k = 239)
  [0,749 ; 0,843].
- Analysis, n = 301 : [0,751 ; 0,841], ±4,5 points ; exact (k = 241)
  [0,751 ; 0,844].
- DoS, n = 825 : [0,771 ; 0,826], ±2,7 points ; exact (k = 660) [0,771 ; 0,827].
- Reconnaissance, n = 1 740 : [0,781 ; 0,818], ±1,9 point ; exact (k = 1 392)
  [0,780 ; 0,819].
- Generic, n = 2 833 : [0,785 ; 0,814], ±1,5 point ; exact (k = 2 266)
  [0,785 ; 0,814].
- Fuzzers, n = 3 991 : [0,787 ; 0,812], ±1,2 point ; exact (k = 3 193)
  [0,787 ; 0,812].
- Exploits, n = 4 042 : [0,787 ; 0,812], ±1,2 point ; exact (k = 3 234)
  [0,787 ; 0,812].

Wilson et exact concordent à 0,02 près sauf pour Worms (écart de 2 points sur
la borne basse), où l'approximation est la moins bonne.

Lecture :

- **Worms est la seule famille dont l'intervalle est trop large pour
  conclure** : avec 24 lignes, un rappel de 0,60 et un rappel de 0,90 sont
  tous les deux compatibles avec la mesure. Les autres ont une demi-largeur
  d'au plus 5,2 points.
- Le seuil entre « exploitable » et « trop petit » dépend de l'écart qu'on
  cherche à voir entre le témoin et le traitement (M05) : il n'est pas fixé ici.
- **Ces intervalles sont optimistes.** Ils supposent des lignes indépendantes.
  Des flux issus d'une même rafale ou d'un même balayage ne le sont pas, et la
  proportion de copies exactes trouvée ci-dessus indique que la répétition est
  fréquente. Le nombre effectif d'observations indépendantes est inférieur à
  n ; de combien, cela n'a pas été mesuré.
- Ils portent sur un rappel isolé. La comparaison témoin/traitement se fait sur
  les mêmes lignes de test (mesures appariées) ; sa précision n'est pas celle
  d'un rappel isolé et n'est pas calculée ici.

Correction sur M08 : j'y écrivais que le plafond intéressant était celui du
Fuzzers. Les 11 faux négatifs irréductibles au test pèsent 11 lignes sur
3 991 Fuzzers (0,3 %, calcul arithmétique) : au niveau binaire, ce plafond est
négligeable même pour cette famille. Le plafond notable reste celui des
familles entre elles (M08, niveau multiclasse).

---

## M10 — Familles retirées de l'entraînement supervisé, composition résultante (2026-09-18)

### Décision de l'auteur

Familles retirées de l'entraînement supervisé (condition « traitement ») :
**Exploits et Reconnaissance.**

Raisons données : ce sont les deux familles où la mesure au test est la plus
précise (demi-largeurs de ±1,2 et ±1,9 point sur un rappel hypothétique de
0,80, M09) ; elles sont conceptuellement distinctes (exploitation d'une
vulnérabilité contre balayage exploratoire), donc si un modèle en détecte une
et pas l'autre, le résultat est interprétable.

Écartées : **Worms** (24 lignes au test, ±15,4 points, non concluant) et
**Generic** (le retirer amputerait l'entraînement d'environ 26 % de ses
attaques, ce qui dégraderait le modèle pour une raison étrangère à
l'expérience).

Le témoin (M05) garde toutes les familles à l'entraînement. Les deux
conditions utilisent la même partition temporelle et le même jeu de test.

### Vérification et composition

Calcul arithmétique à partir des effectifs mesurés en M09 (aucune lecture des
données). Commande :

    python3 -c "
    train = {'Exploits':23557,'Fuzzers':17804,'Generic':22545,'Reconnaissance':11617,'DoS':4840,'Analysis':1883,'Backdoors':1684,'Shellcode':1288,'Worms':147}
    test  = {'Exploits':4042,'Fuzzers':3991,'Generic':2833,'Reconnaissance':1740,'DoS':825,'Analysis':301,'Backdoors':299,'Shellcode':223,'Worms':24}
    normal_train, normal_test = 950853, 1008918
    removed = ['Exploits','Reconnaissance']
    ta = sum(train.values()); rm = sum(train[f] for f in removed); left = ta - rm
    print('attaques train', ta, '| retirées', rm, f'({100*rm/ta:.1f} %)', '| restantes', left)
    for f, n in sorted(train.items(), key=lambda kv: -kv[1]):
        if f not in removed: print(f'  {f:14s} {n:6d}  {100*n/left:5.1f} % des attaques restantes')
    print(f'part d attaques dans train: témoin {100*ta/(ta+normal_train):.2f} % -> traitement {100*left/(left+normal_train):.2f} %')
    print(f'ratio normal/attaque: témoin {normal_train/ta:.1f} -> traitement {normal_train/left:.1f}')
    tt = sum(test.values()); tr = sum(test[f] for f in removed)
    print('test: attaques', tt, '| familles retirées', tr, f'({100*tr/tt:.1f} %)', '| familles vues', tt-tr)
    "

Résultat :

- Attaques d'entraînement (après déduplication) : 85 365. Retirées : 23 557
  (Exploits) + 11 617 (Reconnaissance) = **35 174, soit 41,2 %**. Le chiffre
  de l'auteur est confirmé. **Restent 50 191 attaques.**
- Composition d'entraînement du traitement, attaques : Generic 22 545
  (44,9 %) ; Fuzzers 17 804 (35,5 %) ; DoS 4 840 (9,6 %) ; Analysis 1 883
  (3,8 %) ; Backdoors 1 684 (3,4 %) ; Shellcode 1 288 (2,6 %) ; Worms 147
  (0,3 %). Generic et Fuzzers font à eux deux environ 80 % des attaques
  restantes.
- Normal d'entraînement : 950 853 dans les deux conditions.
- Part d'attaques à l'entraînement : 8,24 % (témoin) → 5,01 % (traitement).
  Rapport normal/attaque : 11,1 → 18,9.
- Test : 14 278 attaques, dont **5 782 (40,5 %) de familles retirées**
  (Exploits 4 042 + Reconnaissance 1 740) et 8 496 de familles vues.

### Le volume restant est-il suffisant ?

Avis, non mesure : je n'ai entraîné aucun modèle, et aucune performance n'est
estimée ici.

- Le volume absolu ne paraît pas être le problème : 50 191 attaques contre
  950 853 normaux, c'est de quoi entraîner un gradient boosting. Les familles
  minces sont Worms (147) et, plus modestement, Shellcode (1 288), Backdoors
  (1 684) et Analysis (1 883). Le déséquilibre passe de 11 pour 1 à 19 pour 1 ;
  cela se traite au niveau du modèle (pondération de classes) et du seuil, et
  reste à décider.
- **Le vrai risque n'est pas le volume mais la confusion des effets.** Le
  traitement diffère du témoin par trois choses à la fois : la famille absente,
  41 % d'attaques en moins, et une composition dominée à 80 % par Generic et
  Fuzzers. L'écart témoin/traitement mesure la somme des trois. Or la règle
  posée en M05 est que cet écart isole l'effet « famille inédite ».

Options pour isoler l'effet, à trancher par l'auteur :

1. **Deux conditions seulement** (telles que décidées). Simple ; l'écart reste
   attribuable à la famille inédite *et* à la perte de données, sans pouvoir
   les séparer.
2. **Témoin à volume égal** : une troisième condition, où l'on retire du
   témoin 35 174 lignes d'attaque tirées au hasard, proportionnellement aux
   familles (graine fixée). Même volume que le traitement, mais les familles
   restent toutes présentes. Coût faible ; ne sépare pas la composition.
3. **Courbe d'apprentissage du témoin** : entraîner le témoin sur plusieurs
   fractions de ses attaques, et lire la sensibilité de la performance au
   volume. Plus informatif, plus de calculs (peu, avec un boosting).

Recommandation : l'option 2 comme minimum, l'option 3 si le temps le permet.
Ce n'est qu'une recommandation ; le choix appartient à l'auteur.

---

## M11 — Protocole à trois conditions, préparation des données et contrôles (2026-09-18)

### Décisions de l'auteur (M05, M10 suite)

Option 2 retenue : **trois conditions supervisées**, plus le non supervisé.

- **A — témoin complet** : toutes les familles, 85 365 attaques.
- **B — témoin à volume égal** : 50 191 attaques tirées au hasard
  proportionnellement aux familles de A, toutes les familles présentes, graine
  fixée (42, `config.toml`, section `sampling`).
- **C — traitement** : Exploits et Reconnaissance retirés, 50 191 attaques.
- **A − B** mesure l'effet du volume seul ; **B − C** mesure l'effet de la
  famille inédite à volume constant : c'est ce second écart qui répond à la
  question du projet.
- L'option 3 (courbe d'apprentissage du témoin) est gardée pour la fin.
- **Non supervisé** (autoencodeur et Isolation Forest) : entraînement sur les
  950 853 normaux du jour 2 uniquement, aucune attaque d'aucune famille. Même
  jeu de test que les trois conditions supervisées.

### Préparation : `src/prepare.py`

Commande (86 s, environ 4,5 Go de mémoire au pic) :

    venv/bin/python src/prepare.py

Configuration : `config.toml` (chemin, date de coupure, familles retirées,
colonnes exclues, graine, seuil des modalités rares). Sorties dans
`data/processed/` (gitignoré) : `train_{unsup,A,B,C}.parquet`, `test.parquet`,
`preprocessor_{unsup,A,B,C}.joblib`, `manifest.json`.

Lignes lues après retrait des 3 doublons de jonction : 2 540 044. Doublons
exacts (49 colonnes) supprimés par côté après le découpage : entraînement
416 624, test 64 006, identiques à M08.

Effectifs écrits (attaques par famille) :

- **unsup** : 950 853 lignes, tous normaux.
- **A** : 1 036 218 lignes, dont 85 365 attaques : Analysis 1 883 ; Backdoors
  1 684 ; DoS 4 840 ; Exploits 23 557 ; Fuzzers 17 804 ; Generic 22 545 ;
  Reconnaissance 11 617 ; Shellcode 1 288 ; Worms 147.
- **B** : 1 001 044 lignes, dont 50 191 attaques : Analysis 1 107 ; Backdoors
  990 ; DoS 2 846 ; Exploits 13 851 ; Fuzzers 10 468 ; Generic 13 256 ;
  Reconnaissance 6 830 ; Shellcode 757 ; Worms 86. Répartition par plus grands
  restes, proportionnelle à A.
- **C** : 1 001 044 lignes, dont 50 191 attaques : Analysis 1 883 ; Backdoors
  1 684 ; DoS 4 840 ; Fuzzers 17 804 ; Generic 22 545 ; Shellcode 1 288 ;
  Worms 147.
- **Test** : 1 023 196 lignes, dont 14 278 attaques : Analysis 301 ; Backdoors
  299 ; DoS 825 ; Exploits 4 042 ; Fuzzers 3 991 ; Generic 2 833 ;
  Reconnaissance 1 740 ; Shellcode 223 ; Worms 24. Normaux : 1 008 918.

Tous ces effectifs coïncident avec M09 et M10.

Choix de préparation :

- **Un préprocesseur par jeu, ajusté sur les seules lignes de ce jeu.** Un
  préprocesseur commun, ajusté sur tout le jour 2, aurait emporté dans C les
  statistiques des familles retirées, et dans le non supervisé celles des
  attaques. Le test est transformé au chargement avec le préprocesseur du jeu
  évalué (`load_set`).
- **Encodage** : one-hot de `proto`, `state`, `service`, avec regroupement des
  modalités de fréquence inférieure à 0,1 % de l'entraînement (`min_frequency =
  0,001`) et envoi des modalités jamais vues dans ce groupe. **Valeur par défaut
  à valider par l'auteur.** Motivation mesurée : `proto` a 134 modalités au
  jour 2 dont la plupart sous 400 lignes ; `state` 14 au jour 2 et 16 au jour 1
  (`CLO` et `URH` absentes du jour 2 : 269 lignes de test) ; `proto` a une
  modalité (`esp`, 2 lignes de test) absente du jour 2 ; `service` : aucune.
  Dimensions de X après encodage : 56 (unsup), 58 (A), 57 (B et C).
- **Scaler** : `StandardScaler`, sans transformation logarithmique. Les colonnes
  ont des queues très lourdes (Sload jusqu'à 5,99·10⁹, sbytes jusqu'à 1,4·10⁷).
  Sans effet pour un gradient boosting, probablement important pour
  l'autoencodeur : **décision de modélisation à prendre avant l'autoencodeur,
  non prise ici.**
- **Vides des trois colonnes `ct_flw_http_mthd`, `is_ftp_login`, `ct_ftp_cmd`
  remplacés par 0** (voir ci-dessous).

### Mesure : les vides de trois colonnes sont propres au jour 2

Commande :

    python3 src/inspect_columns.py

Vides (jour 2 / jour 1) : `ct_flw_http_mthd` 1 348 143 / 0 ; `is_ftp_login`
1 429 877 / 0 ; `ct_ftp_cmd` 1 429 877 / 0 (avant déduplication). Aucune valeur
non numérique dans les 41 features.

- Au jour 2, les valeurs renseignées de `is_ftp_login` et `ct_ftp_cmd` ne
  valent jamais 0 (`is_ftp_login` : 1 → 22 779, 4 → 156, 2 → 30 ; `ct_ftp_cmd`
  : mêmes effectifs) ; `ct_flw_http_mthd` : jamais 0 non plus parmi ses valeurs
  les plus fréquentes (1, 4, 2, 9, 30, 16). Le jour 1 écrit 0 explicitement :
  1 066 592 fois pour `is_ftp_login`, 986 790 fois pour `ct_flw_http_mthd`.
- Au jour 2, chaque ligne a exactement l'un de ces cas : les trois vides
  (1 325 178 lignes), `ct_flw_http_mthd` renseigné seul (104 699), ou les deux
  colonnes FTP renseignées seules (22 965). Aucune ligne n'a les deux groupes
  renseignés.

Lecture : au jour 2, un blanc est un 0 écrit autrement (hypothèse cohérente
avec toutes les observations, non prouvée par une documentation). Laisser des
NaN ferait apprendre au modèle le jour d'entraînement. Le remplacement par 0
aligne les deux jours.

### Correction de M07 et M08 : le zéro recoupement entre jours était mécanique

M07 annonçait « 0 combinaison présente aux deux jours » sur C et C′, et
concluait à l'absence de copie comportementale entre entraînement et test. **Ce
zéro était dû au format** : au jour 2 ces trois colonnes sont vides, au jour 1
elles valent 0, donc deux lignes de comportement identique ne pouvaient jamais
coïncider en comparaison textuelle. M07 relevait un zéro sans en avoir trouvé la
cause (« n'a pas été cherché ») ; elle est maintenant identifiée.

Contrôle : option `--blank-as-zero` ajoutée à `src/inspect_duplicates.py` (les
blancs de ces trois colonnes deviennent 0 avant comparaison des features).
Commande :

    python3 src/inspect_duplicates.py --blank-as-zero

Résultat, avant déduplication, sur C (41 colonnes) : **689 combinaisons
présentes aux deux jours** (2 358 lignes du jour 1, 3 844 lignes du jour 2),
dont 27 à étiquettes contradictoires. Sur B′ (45 colonnes, IP et ports
conservés, sans horodatages) : 114 combinaisons (851 lignes du jour 1). Les
contradictions de C changent aussi, parce que des lignes des deux jours se
regroupent : 2 590 combinaisons et 42 322 lignes (au lieu de 2 579 et 42 282),
dont normal contre attaque 463 combinaisons, 1 913 lignes (au lieu de 453 et
1 879). Les chiffres de M07 correspondent à la comparaison textuelle brute ; ceux-ci à la
comparaison après alignement des blancs, qui est celle des données réellement
utilisées. Ces derniers sont ceux à retenir.

Ce qui reste valable : les plafonds de M08 sont calculés côté par côté, or un
blanc et un 0 ne coexistent jamais dans un même jour ; ils ne changent donc pas.
Le zéro doublon exact entre jours sur les 49 colonnes (M06) reste vrai, car
`Stime` en fait partie. Ce qui tombe : l'affirmation de M07 selon laquelle il n'y
aurait aucune copie comportementale entre entraînement et test.

### Mesure sur les données écrites : lignes de test avec un jumeau à l'entraînement

Commande (contrôles d'intégrité, environ 1 min) :

    venv/bin/python src/verify_prepare.py

Après déduplication et alignement des blancs, sur les 41 features (sans
`Stime`), nombre de lignes de test dont les features sont identiques à celles
d'au moins une ligne du jeu d'entraînement :

- unsup : 1 017 lignes ; A : 1 555 ; B : 1 503 ; C : 1 104.
- **Reconnaissance, test (1 740 lignes) : 449 (25,80 %) ont un jumeau dans A,
  415 (23,85 %) dans B, 1 (0,06 %) dans C.** Tous étiquetés attaque, donc de la
  même étiquette binaire.
- Generic : 68 sur 2 833 (2,40 %) dans A et C ; 53 dans B.
- Exploits : 3 sur 4 042 (0,07 %) dans A ; 2 dans C.
- Analysis 2, Backdoors 2, DoS 5 (3 dans C), Shellcode 2 : négligeable.
- Fuzzers : 17 sur 3 991 dans A ; 10 d'entre elles ont un jumeau étiqueté
  normal seulement (étiquette opposée), 2 un jumeau mixte, 5 un jumeau attaque.
- Normal : 1 007 sur 1 008 918 (0,10 %) dans A, dont 3 avec jumeau attaque
  seulement et 8 avec jumeau mixte.
- Dans le jeu non supervisé, tous les jumeaux sont des normaux : 12 lignes
  Fuzzers et 1 Shellcode du test y ont un jumeau normal (donc indétectables
  par construction pour un modèle qui ne voit que ces normaux).

Lecture : **le rappel de A et de B sur Reconnaissance est gonflé par la
mémorisation** d'environ un quart des lignes de test (449 et 415 lignes qu'un
arbre reconnaît par identité), ce que C ne peut pas faire puisque la famille
est retirée. L'écart B − C sur Reconnaissance mélange donc « la famille est
inédite » et « des copies exactes ont disparu ». Ce n'est pas une fuite du test
vers l'entraînement au sens du scaler, mais c'est un biais de mesure à rapporter
et à traiter (par exemple en mesurant aussi le rappel hors des lignes à
jumeau). Exploits est quasi épargné (3 lignes sur 4 042), ce qui en fait la
mesure la plus propre de l'effet de la famille inédite. Non tranché ici.

### Contrôles d'intégrité de `verify_prepare.py`

- **Scaler ajusté sur l'entraînement seul** : l'écart entre la moyenne du
  scaler et la moyenne de l'entraînement est nul (0,000) pour les quatre jeux ;
  l'écart relatif maximal avec la moyenne du test est de 0,66 (unsup), 0,82 (A),
  0,78 (B), 0,79 (C).
- **Imbrication** : B et C sont inclus dans A ; les quatre jeux ont les mêmes
  normaux ; unsup ne contient aucune attaque ; C ne contient aucune famille
  retirée.
- **Chargement** : X sans NaN ni infini pour les quatre jeux.
- **Reproductibilité** : deux exécutions successives de `prepare.py` donnent
  un `manifest.json` identique et la même empreinte de B (somme des empreintes
  de lignes : 170760787752572768).
- **Découpage étanche** : `Stime` minimal de l'entraînement ≥ 2015-02-18 00:00
  UTC > `Stime` maximal du test (vérifié à chaque exécution).

---

## M12 — Asymétrie des features numériques et seuil pour log1p (2026-09-18)

### Décision de l'auteur

Appliquer `log1p` aux colonnes à queue lourde **avant** le scaler, avec un
critère de sélection mesuré (asymétrie) et non une liste écrite à la main. Le
seuil est proposé par l'assistant (ci-dessous) ; l'auteur ne l'a pas encore
validé. Motif de l'auteur : un autoencodeur entraîné sur des valeurs allant
jusqu'à 6 milliards reconstruirait surtout les colonnes à grande échelle.

L'implémentation dans `prepare.py` et ses contrôles sont en M13.

### Mesure

Commande :

    venv/bin/python src/inspect_skew.py

Asymétrie (skewness) de chacune des 38 features numériques, calculée **sur les
jeux d'entraînement seuls, jamais sur le test**. Le choix des colonnes est un
paramètre ajusté, comme la moyenne d'un scaler. Toutes les colonnes ont un
minimum ≥ 0 (les compteurs `ct_*` ≥ 1), donc log1p est défini partout.

Asymétrie brute, jeu A, par ordre décroissant : trans_depth 180,2 ; sbytes
101,5 ; sloss 92,0 ; Sjit 47,5 ; Spkts 33,1 ; ackdat 31,7 ; synack 29,9 ; Djit
28,8 ; Dintpkt 28,2 ; is_sm_ips_ports 27,8 ; tcprtt 24,2 ; res_bdy_len 23,2 ;
Sintpkt 21,1 ; Sload 16,5 ; ct_flw_http_mthd 13,0 ; dloss 11,3 ; dur 11,3 ;
dbytes 10,6 ; Dpkts 10,1 ; is_ftp_login 7,7 ; ct_ftp_cmd 7,7 ;
ct_src_dport_ltm 7,4 ; ct_dst_sport_ltm 7,3 ; ct_dst_src_ltm 5,2 ; ct_dst_ltm
5,2 ; ct_state_ttl 4,6 ; ct_src_ltm 4,4 ; ct_srv_dst 4,0 ; ct_srv_src 3,8 ;
smeansz 3,4 ; dttl 3,4 ; sttl 2,8 ; **Dload 1,75** ; dmeansz 1,2 ; stcpb 0,45 ;
dtcpb 0,45 ; dwin −0,81 ; swin −0,82.

Les valeurs décroissent presque sans saut : il n'y a pas de coupure naturelle
unique. Deux constats décident de la position du seuil :

1. **Stabilité entre les jeux.** Pour tout seuil entre 1,75 et 2,77, la liste de
   colonnes est identique dans les quatre jeux (unsup, A, B, C). La borne basse
   est l'asymétrie de `Dload` (1,62 à 1,75 selon le jeu), la borne haute celle de
   `sttl` (2,77 dans A). Aux seuils 3, 5 et 10, les listes diffèrent d'un jeu à
   l'autre, ce qui ferait varier le prétraitement entre B et C pour une raison
   étrangère à la famille retirée. Nombre de colonnes au-dessus : seuil 1 → 34
   (identique dans les 4 jeux) ; seuil 2 → 32 (identique) ; seuil 3 → 31 ou 32 ;
   seuil 5 → 25 ou 26 ; seuil 10 → 14 à 19.
2. **Sur-correction sous le seuil.** Sur `Dload` (1,75) et `dmeansz` (1,2),
   log1p ferait passer l'asymétrie à −1,82 et −1,44 : plus loin de zéro qu'avant.

**Seuil proposé : 2** (`log1p_skew_threshold`), au milieu de l'intervalle
[1,75 ; 2,77]. Il sélectionne **32 colonnes**, les mêmes dans les quatre jeux :
dur, sbytes, dbytes, sttl, dttl, sloss, dloss, Sload, Spkts, Dpkts, smeansz,
trans_depth, res_bdy_len, Sjit, Djit, Sintpkt, Dintpkt, tcprtt, synack, ackdat,
is_sm_ips_ports, ct_state_ttl, ct_flw_http_mthd, is_ftp_login, ct_ftp_cmd,
ct_srv_src, ct_srv_dst, ct_dst_ltm, ct_src_ltm, ct_src_dport_ltm,
ct_dst_sport_ltm, ct_dst_src_ltm. Restent sans log1p : Dload, dmeansz, stcpb,
dtcpb, swin, dwin. Le critère est mécanique ; l'auteur peut le remplacer en
changeant une valeur dans `config.toml`.

Deux remarques sur ce critère :

- `is_sm_ips_ports` (2 modalités) est sélectionnée par sa forte asymétrie ;
  log1p sur une colonne à valeurs {0, 1} est une transformation affine, sans
  effet une fois le scaler appliqué. Inoffensif, non retiré.
- L'asymétrie brute dépend beaucoup du jeu pour certaines colonnes : `trans_depth`
  vaut 2,97 (unsup) et 2,99 (C) contre 180,2 (A) et 183,7 (B). Les valeurs
  extrêmes de cette colonne se trouvent donc dans des lignes d'Exploits ou de
  Reconnaissance, absentes de C et de unsup. C'est une illustration mesurée de
  la raison pour laquelle le préprocesseur est ajusté jeu par jeu. Ici la
  sélection reste la même (2,97 > 2).

### Effet sur l'échelle (jeu de l'autoencodeur, normaux du jour 2 seuls)

Plus grande valeur standardisée |z| par colonne, avant puis après log1p, sur
les 32 colonnes sélectionnées : **maximum 166,1 → 78,8 ; médiane des maxima
21,3 → 5,6.**

- Les colonnes les plus étendues avant log1p : ackdat 166,1 ; Djit 162,4 ;
  tcprtt 158,1 ; sbytes 146,1 ; synack 124,3 ; Sjit 109,7 ; Sload 75,3 ; sloss
  55,8 ; ct_flw_http_mthd 45,5 ; Dintpkt 43,8.
- Après log1p : ackdat 78,8 ; Djit 3,6 ; tcprtt 57,9 ; sbytes 4,7 ; synack
  66,3 ; Sjit 3,4 ; Sload 5,6 ; sloss 4,5 ; ct_flw_http_mthd 13,1 ; Dintpkt 6,3.

Deux enseignements, qui nuancent le motif initial :

- **Sload n'est pas la colonne dominante** une fois les valeurs standardisées
  sur les normaux : |z| max de 75,3, derrière ackdat, Djit, tcprtt, sbytes,
  synack et Sjit. Le mécanisme invoqué (queues lourdes qui tirent
  l'apprentissage) est bien mesuré ; la colonne citée n'est pas la pire.
- **log1p corrige mal `ackdat`, `tcprtt` et `synack`** : leur |z| max reste à
  78,8, 57,9 et 66,3, et leur asymétrie de 31,7, 24,2 et 29,9 (jeu A) ne tombe
  qu'à 14,7, 10,0 et 14,7. Ces colonnes sont des durées en secondes dont le
  maximum est de l'ordre de 5 à 10 : hypothèse (non mesurée) : leurs valeurs
  typiques sont très inférieures à 1, domaine où log1p(x) ≈ x et où la
  transformation ne comprime presque rien. Une autre transformation (par exemple
  log(x + ε) avec ε calé sur l'entraînement, ou une mise à l'échelle par la
  valeur positive médiane avant log) réglerait peut-être cela ; non décidé, non
  implémenté, car l'auteur a demandé log1p.

---

## M13 — log1p avant le scaler, marquage des jumeaux : implémentation et contrôles (2026-09-18)

### Implémentation

- `config.toml`, section `preprocessing` : `log1p_skew_threshold = 2.0` (M12).
- `src/prepare.py` : `select_log_columns` calcule l'asymétrie de chaque colonne
  numérique **sur l'entraînement du jeu** et retient celles au-dessus du seuil ;
  le préprocesseur de chaque jeu applique alors log1p puis `StandardScaler` à ces
  colonnes, et `StandardScaler` seul aux autres. Une colonne sélectionnée qui
  prendrait une valeur négative arrête l'exécution. `manifest.json` conserve,
  par jeu, la liste `log1p_columns` et l'asymétrie brute de chaque colonne.
- `src/evaluate.py` : `mark_twins` et `twin_flags` marquent chaque ligne du test
  (`has_twin`, et `twin_kind` : none, attack, normal, mixed) selon qu'elle a un
  jumeau exact (41 features, valeurs nettoyées, avant encodage) dans le jeu
  d'entraînement évalué ; `recall_by_family` rapporte le rappel par famille
  d'attaque, avec l'effectif et le rappel des lignes avec jumeau et sans jumeau.
  Le marquage dépend du jeu (une ligne peut avoir un jumeau dans A et pas dans C).
  Usage prévu : `recall_by_family(test.family, test.label, y_pred,
  twin_flags("A")["has_twin"])`.

### Contrôles

Commandes :

    venv/bin/python src/prepare.py
    venv/bin/python src/verify_prepare.py

- **Sélection** : 32 colonnes log1p dans chacun des quatre jeux, listes
  identiques (contrôle du manifeste et du préprocesseur écrit), conformes à M12.
- **Scaler ajusté sur l'entraînement seul** : écart nul (0,000) entre la moyenne
  du scaler et la moyenne de l'entraînement transformé, pour les quatre jeux.
  Écart relatif maximal avec la moyenne du test transformé : 0,64 (unsup), 0,82
  (A), 0,77 (B), 0,76 (C).
- **Imbrication** : inchangée (B et C dans A, mêmes normaux, unsup sans attaque,
  C sans familles retirées).
- **Jumeaux** : effectifs identiques à M11 (1 017 lignes de test avec jumeau
  pour unsup, 1 555 pour A, 1 503 pour B, 1 104 pour C ; Reconnaissance : 449
  dans A, 415 dans B, 1 dans C), ce qui est attendu puisque le marquage porte sur
  les valeurs brutes nettoyées, avant log1p. L'empreinte de B est inchangée
  (170760787752572768).
- **Contrôle de `recall_by_family`** avec un prédicteur factice « mémoriseur »
  (il signale une ligne si elle a un jumeau étiqueté attaque dans A) :
  Reconnaissance, 1 740 lignes de test, dont 449 avec jumeau (rappel 1,000) et
  1 291 sans jumeau (rappel 0,000). Ce contrôle vérifie la mécanique de
  découpe ; ce n'est pas une performance.
- **Chargement** : X sans NaN ni infini pour les quatre jeux, mêmes dimensions
  qu'en M11 (56, 58, 57, 57 colonnes). Plus grande valeur absolue de X : sur
  l'entraînement 78,8 (unsup), 69,9 (A), 72,9 (B), 74,5 (C) ; sur le test 44,0,
  39,5, 41,0 et 41,6. Aucune valeur de test ne dépasse le maximum de
  l'entraînement, pour aucun des quatre jeux.

---

## M14 — Seuil log1p validé, et vérification de l'hypothèse sur ackdat, tcprtt, synack (2026-09-18)

### Décisions de l'auteur

1. **Seuil d'asymétrie de 2 validé.** L'argument retenu est la stabilité entre
   les quatre jeux, pas la position du seuil dans la distribution : un seuil qui
   ferait varier la liste de colonnes entre B et C changerait le prétraitement
   pour une raison étrangère à l'expérience.
2. **`ackdat`, `tcprtt`, `synack` acceptées en l'état** (M12). Si l'hypothèse
   ci-dessous se confirme, elle va dans les limites du README comme piste
   d'amélioration identifiée et non traitée.

### Mesure de l'hypothèse

Hypothèse (M12) : les valeurs typiques de ces trois colonnes sont très
inférieures à 1, domaine où log1p(x) ≈ x et où la transformation ne comprime
presque rien. Commande :

    venv/bin/python src/inspect_skew.py

Jeu unsup (950 853 normaux du jour 2), valeurs brutes avant log1p :

- **ackdat** : 29,8 % de valeurs nulles ; médiane 0,000123 ; quantile 99 %
  0,0851 ; maximum 5,51 ; 0,021 % des lignes ≥ 1. Sur les lignes non nulles
  (667 311) : médiane 0,00013 ; quantile 99 % 0,101 ; log1p(x)/x vaut 0,9999 à la
  médiane et 0,953 au quantile 99 %.
- **tcprtt** : 29,8 % nulles ; médiane 0,000634 ; quantile 99 % 0,185 ;
  maximum 10,04 ; 0,070 % des lignes ≥ 1. Lignes non nulles (667 342) : médiane
  0,000672 ; quantile 99 % 0,216 ; log1p(x)/x : 0,9997 et 0,905.
- **synack** : 29,8 % nulles ; médiane 0,000505 ; quantile 99 % 0,0986 ;
  maximum 4,53 ; 0,025 % des lignes ≥ 1. Lignes non nulles (667 342) : médiane
  0,000536 ; quantile 99 % 0,116 ; log1p(x)/x : 0,9997 et 0,946.

**L'hypothèse est confirmée.** Le rapport log1p(x)/x reste entre 0,90 et 1,00
jusqu'au quantile 99 % : la transformation ne comprime pratiquement rien sur 99 %
des lignes. Elle n'agit que sur la queue extrême (0,02 à 0,07 % des lignes,
celles ≥ 1), ce qui explique que le |z| maximal reste élevé (M12 : 78,8, 57,9,
66,3) alors que l'asymétrie ne tombe qu'à 14,7, 10,0 et 14,7.

Correction sur M12 : j'y écrivais « durées en secondes ». Le fichier features
ne donne aucune unité pour ces trois colonnes (il les décrit comme des temps de
mise en place de la connexion TCP). L'unité n'est pas établie ; l'échelle
mesurée ci-dessus ne dépend pas d'elle.

Environ 30 % de valeurs nulles dans ces trois colonnes : ce sont les flux sans
handshake TCP (une mesure du nombre de flux concernés par protocole n'a pas été
faite ici).

### À reprendre dans le README (section limites et pistes d'amélioration)

log1p est appliqué à `ackdat`, `tcprtt` et `synack` sans effet notable sur 99 %
de leurs valeurs, car ces durées sont typiquement de l'ordre de 10⁻⁴ à 10⁻¹
(médiane 0,0001 à 0,0006). Une transformation qui tient compte de l'échelle
(par exemple log(x + ε) avec ε calé sur l'entraînement, ou une division par la
médiane des valeurs non nulles avant le log) reste une piste identifiée, non
traitée ni testée.

---

## M15 — Débit horaire des flux, pour chiffrer un budget de faux positifs (2026-09-18)

Commande :

    venv/bin/python src/inspect_debit.py

Flux par heure UTC, d'après `Stime`, après déduplication.

- **Test (jour 1)** : 1 023 196 flux du 2015-01-22 11:49 au 2015-01-23 00:25 UTC
  (12,6 h), 14 heures avec des flux. Normaux par heure : médiane 79 548, maximum
  94 753 (16 h), moyenne sur l'étendue 80 096. Les heures d'extrémité sont
  partielles (13 486 à 11 h, 33 930 à 0 h) ; en dehors d'elles, le minimum est de
  62 537 (19 h).
- **Entraînement (jour 2)** : 1 036 218 flux du 2015-02-18 00:23 au 12:21 UTC
  (12,0 h), 13 heures. Normaux par heure : médiane 81 786, maximum 87 372,
  moyenne sur l'étendue 79 495.

**Le débit réel est d'environ 80 000 flux normaux par heure**, soit huit fois
les 10 000 flux/h de l'exemple du cahier des charges. Conversion (arithmétique
sur ce débit) : un taux de faux positifs de 1 % donne environ 800 fausses
alertes par heure ; 0,1 % environ 80 ; 0,01 % environ 8 ; 0,001 % environ 0,8.
Avec l'exemple du cahier des charges (2 % de faux positifs), on aurait ici
environ 1 600 fausses alertes par heure.

### À reprendre dans le README (limites)

- Le débit de ce jeu (environ 80 000 flux/h) est celui d'un banc d'essai
  synthétique, pas d'un réseau réel ; les nombres d'alertes par heure sont à
  lire avec cette réserve.
- **Le sens du temps est inversé** : le test (22-23 janvier 2015) précède
  l'entraînement (18 février 2015). Le modèle est entraîné sur le jour le plus
  récent et évalué sur le plus ancien. Le découpage est temporel et évite la
  fuite d'un tirage aléatoire, mais ne reproduit pas un déploiement réel, où
  l'on entraîne sur le passé pour évaluer sur le futur. Décision prise pour des
  raisons de volume (M05) ; à nommer comme limite.

---

## M16 — Isolation Forest sur le jeu non supervisé (2026-09-18)

### Décisions de l'auteur

1. **Seuil calibré par validation croisée par blocs de temps** (option 3). Une
   réserve de 10 % de normaux ne permet pas de calibrer sous 0,1 %, alors que le
   seuil utile s'y trouve. Si l'autoencodeur rend K entraînements trop coûteux,
   repli sur l'option 1 (seuil tiré des scores d'entraînement) pour lui seul,
   avec l'optimisme mesuré et documenté.
2. **Trois budgets de faux positifs rapportés : 1 %, 0,1 %, 0,01 %**, avec
   **0,1 % comme point de référence** (environ 80 fausses alertes par heure au
   débit de M15). Réserve de l'auteur : 0,01 % risque de donner un rappel trop
   bas pour que la comparaison entre modèles ait du contraste ; à revoir à la
   lecture.
3. **Hyperparamètres par défaut, graine fixée.** Régler sur les attaques
   romprait le protocole non supervisé.

### Implémentation

- `src/models/isolation_forest.py` : 100 arbres, `max_samples` = « auto »
  (256 lignes par arbre), graine 42, `config.toml` section `isolation_forest`.
  Le score d'anomalie est l'opposé de `score_samples` (plus grand = plus
  suspect) ; le paramètre `contamination` n'intervient pas.
- **Calibration** : les 950 853 normaux du jour 2, triés par `Stime`, sont coupés
  en **5 blocs de temps contigus** (`cv_folds = 5`, choix de l'assistant, non
  discuté) ; chaque bloc est noté par un modèle entraîné sur les 4 autres, avec
  un préprocesseur (sélection log1p, encodeur, scaler) **réajusté sur ces 4
  blocs seuls**. Le seuil d'un budget b est le quantile 1 − b de ces scores hors
  échantillon (`threshold_for_fpr`) ; une alerte est déclenchée quand le score
  est strictement supérieur au seuil.
- Le modèle final est entraîné sur tous les normaux (préprocesseur `unsup` de
  `prepare.py`) et évalué sur le test.
- `src/evaluate.py` : AUC-PR (précision moyenne), seuil par budget, matrice de
  confusion, précision, rappel global et par famille avec intervalle de Wilson
  et découpe avec/sans jumeau, fausses alertes par heure.
- Contrôle de la mécanique sur des scores synthétiques (loi normale, deux
  populations) : le taux sur la calibration reste sous le budget, le rappel
  observé est proche du rappel théorique, des scores tous égaux ne déclenchent
  aucune alerte. Contrôle non versionné ; `ic_rappel.py` donne toujours les
  intervalles de M09 après le déplacement de la fonction `wilson`.

### Mesures

Commande (46 s, deux exécutions successives : résultats identiques) :

    venv/bin/python src/models/isolation_forest.py

Test : 1 008 918 normaux, 14 278 attaques, étendue 12,6 h.

**AUC-PR : 0,3081** (un score aléatoire donnerait la prévalence, 1,395 %).

**Taux de faux positifs visé contre observé, et rappel global** (seuil
calibré sur les scores hors échantillon) :

- Budget 1 % : seuil 0,6190 ; taux sur la calibration 0,9999 % ; **taux observé
  sur le test 0,1152 %** [0,1087 ; 0,1220] ; 1 162 faux positifs, 92,2 fausses
  alertes par heure en moyenne, 520 la pire heure ; **rappel 3,39 %** [3,11 ;
  3,70]. Matrice : VP 484, FP 1 162, FN 13 794, VN 1 007 756 ; précision 29,40 %.
- Budget 0,1 % : seuil 0,6428 ; calibration 0,0997 % ; **test 0,0162 %**
  [0,0139 ; 0,0188] ; 163 faux positifs, 12,9 fausses alertes/h en moyenne, 98
  la pire heure ; **rappel 0,27 %** [0,19 ; 0,37]. Matrice : VP 38, FP 163, FN
  14 240, VN 1 008 755 ; précision 18,91 %.
- Budget 0,01 % : seuil 0,6582 ; calibration 0,0100 % ; **test 0,0038 %**
  [0,0027 ; 0,0052] ; 38 faux positifs, 3,0 fausses alertes/h, 26 la pire
  heure ; **rappel 0,02 %** [0,01 ; 0,06]. Matrice : VP 3, FP 38, FN 14 275, VN
  1 008 880 ; précision 7,32 %.

**Le taux observé sur le test est inférieur au taux visé**, de 8,7 fois (1 %),
6,2 fois (0,1 %) et 2,6 fois (0,01 %), soit l'inverse de l'attente (une dérive du
jour 2 vers le jour 1 devait faire monter le taux). Quantiles du score
d'anomalie (50 %, 99 %, 99,9 %, 99,99 %) :

- normaux d'entraînement, hors échantillon : 0,4272 ; 0,6190 ; 0,6428 ; 0,6582 ;
- normaux d'entraînement, dans l'échantillon : 0,4255 ; 0,6145 ; 0,6400 ; 0,6494 ;
- normaux du test : 0,4279 ; 0,5882 ; 0,6213 ; 0,6472 ;
- attaques du test : 0,5722 ; 0,6339 ; 0,6444 ; 0,6645.

Les médianes des normaux coïncident ; c'est la queue des normaux du jour 2 qui
est plus lourde que celle des normaux du jour 1. La cause n'a pas été
investiguée. Conséquence : la calibration jour 2 → jour 1 est conservatrice,
donc le seuil déployable est trop haut pour le test et coûte du rappel.

**Rappel lu au même taux de faux positifs sur le test** (seuil pris sur les
normaux du TEST : borne haute non déployable, utile pour comparer des modèles
hors qualité de calibration) : taux 1 % → **42,92 %** [42,11 ; 43,73] ; 0,1 % →
**2,49 %** [2,24 ; 2,75] ; 0,01 % → **0,06 %** [0,03 ; 0,11]. L'écart avec le
rappel calibré à 1 % (42,92 % contre 3,39 %) est celui de la calibration.

**Rappel par famille**, seuil calibré (n = effectif de test ; intervalles de
Wilson dans `data/processed/results/isolation_forest.json`) :

- Budget 1 % : Analysis 4,32 % ; Backdoors 5,69 % ; DoS 5,33 % ; Exploits 1,61 % ;
  Fuzzers 6,46 % ; Generic 2,75 % ; Reconnaissance 0,34 % ; Shellcode 0,00 % ;
  Worms 12,50 % [4,34 ; 31,00] (n = 24).
- Budget 0,1 % (référence) : Analysis 0 % ; Backdoors 0 % ; DoS 0,12 % ;
  Exploits 0,20 % ; Fuzzers 0,68 % ; Generic 0 % ; Reconnaissance 0 % ;
  Shellcode 0 % ; Worms 8,33 % [2,32 ; 25,85].
- Budget 0,01 % : Exploits 0,05 %, Fuzzers 0,03 %, toutes les autres 0 %.

**Rappel par famille au même taux lu sur le test** (1 % ; 0,1 % ; 0,01 %) :
Analysis 81,06 ; 3,32 ; 0,00 · Backdoors 84,95 ; 4,68 ; 0,00 · DoS 44,61 ;
3,64 ; 0,00 · **Exploits 13,88 ; 1,01 ; 0,12** · Fuzzers 35,43 ; 5,71 ; 0,08 ·
Generic 85,95 ; 0,85 ; 0,00 · **Reconnaissance 42,18 ; 0,34 ; 0,00** · Shellcode
49,78 ; 0,00 ; 0,00 · Worms 29,17 ; 8,33 ; 0,00 (tous en %). Au taux de 1 %,
Exploits est la famille la moins bien détectée (13,88 %), Reconnaissance a un
rappel de 42,18 %.

**Découpe avec/sans jumeau** : dans le jeu non supervisé, seules 13 lignes
d'attaque du test ont un jumeau (12 Fuzzers, 1 Shellcode ; leur jumeau est un
flux normal, M11) ; leur rappel est de 0 % à tous les budgets, celui des autres
lignes est celui du rappel par famille. Reconnaissance et Exploits n'ont
aucune ligne avec jumeau (Exploits 3 dans A, mais 0 dans unsup). La découpe est
donc sans objet pour ce modèle ; elle servira pour A, B et C.

### Diagnostic : l'option 1 (seuil tiré des scores d'entraînement du modèle)

Le seuil tiré des scores du modèle final sur ses propres normaux d'entraînement
donne : budget 1 % : seuil 0,6145 (au lieu de 0,6190), taux test 0,2676 %, rappel
7,52 % ; 0,1 % : 0,6400, test 0,0244 %, rappel 0,44 % ; 0,01 % : 0,6494, test
0,0086 %, rappel 0,04 %.

**Optimisme mesuré** : taux hors échantillon (les scores hors échantillon de
la calibration, jour 2, sans dérive vers le test) au seuil calculé dans
l'échantillon, comparé au budget visé : **×1,30 à 1 %** (1,3030 %), **×1,32 à
0,1 %** (0,1318 %), **×4,12 à 0,01 %** (0,0412 %). L'optimisme de l'option 1
est donc modeste à 1 % et 0,1 % mais quadruple à 0,01 %. Il inclut en partie
l'effet des blocs de temps (extrapolation dans le temps) en plus du
surapprentissage ; les deux ne sont pas séparés. À reprendre pour
l'autoencodeur si le repli sur l'option 1 est nécessaire.

### Lecture

- L'Isolation Forest est une référence faible aux budgets de déploiement : à
  0,1 %, le rappel est de 0,27 % (calibré) ou 2,49 % (lu au taux de 0,1 % sur le
  test) ; à 0,01 %, moins de 0,1 %. Le contraste entre budgets n'existe qu'à
  1 %. Cela ne préjuge pas de la tenue du budget de référence à 0,1 % pour
  l'autoencodeur et le gradient boosting ; la réserve de l'auteur sur 0,01 %
  se confirme pour ce modèle (3 attaques détectées sur 14 278).
- L'AUC-PR de 0,3081 (22 fois la prévalence) contraste avec ces rappels bas : la
  précision moyenne est dominée par la partie de la courbe à très faible rappel,
  où la précision est de 29 %, 19 % et 7 % aux trois budgets.
- Intervalles de confiance : indépendance des lignes supposée (optimiste, M09).
- Aucune valeur de score, de seuil ou de rappel ci-dessus n'est estimée ; toutes
  proviennent de la commande citée.

---

## M17 — Normaux du jour 2 contre normaux du jour 1 : d'où vient la queue (2026-09-18)

Question de l'auteur : la queue plus lourde des scores des normaux du jour 2
(M16) casse la calibration ; quelles colonnes diffèrent entre les deux jours, et
cela se rattache-t-il à quelque chose d'identifiable (protocole, service,
durée) ? Mesure, sans spéculation. Les normaux du test servent ici à décrire une
différence entre les jours, pas à régler un modèle ni un seuil. Commande :

    venv/bin/python src/inspect_normals.py

Normaux : 950 853 au jour 2, 1 008 918 au jour 1. Seuil de queue : quantile 99 %
des scores hors échantillon du jour 2 (0,6190, M16) ; dépassements : **9 509
flux au jour 2 (1,000 %), 1 162 au jour 1 (0,115 %)**.

### Ce qui diffère sur l'ensemble des normaux

- **Colonnes nominales** (distance de variation totale entre les deux jours) :
  proto 0,0139 (tcp 70,45 % contre 71,84 %, udp 29,00 % contre 27,67 %) ; state
  0,0242 ; service 0,0434. Écart le plus net : **state INT 2,689 % au jour 2
  contre 0,533 % au jour 1**, REQ 0,386 % contre 0,199 %, RST 0,046 % contre
  0,007 %, ECO 0,031 % contre 0,001 % ; service `-` 54,82 % contre 59,16 %, dns
  20,00 % contre 17,46 %.
- **Colonnes numériques**, statistique de Kolmogorov-Smirnov (0 = identiques) :
  seulement **6 colonnes sur 38 dépassent 0,1, aucune ne dépasse 0,3**. Dans
  l'ordre : ct_dst_src_ltm 0,213 (médiane 2 contre 1, quantile 99 % 28 contre 7) ;
  ackdat 0,212 ; ct_srv_dst 0,149 ; ct_srv_src 0,139 ; Sintpkt 0,121 ; Dintpkt
  0,106. Suivent tcprtt 0,094 et synack 0,061. Au centre les distributions se
  ressemblent ; l'écart est dans les queues : quantile 99 % de ackdat 0,0851
  contre 0,000992 (86 fois), tcprtt 0,185 contre 0,0031 (60 fois), synack 0,0986
  contre 0,0022 (45 fois), Sload 2,64·10⁸ contre 1,36·10⁷, sttl 254 contre 31,
  dttl 252 contre 29. Durée `dur` : KS 0,039, médianes 0,02591 s et 0,02592 s.

### Ce qui fournit les dépassements

Dix combinaisons (proto, état, service) fournissent **98,5 % des dépassements du
jour 2**. Lignes du jour 2 → dépassements (taux) contre lignes du jour 1 →
dépassements (taux) :

- (udp, INT, dns) : 17 985 → 2 624 (14,59 %) contre 2 564 → **0 (0,00 %)** ;
- (tcp, CON, `-`) : 4 418 → 2 054 (46,49 %) contre 5 622 → 356 (6,33 %) ;
- (udp, INT, `-`) : 6 117 → 1 880 (30,73 %) contre 1 359 → 228 (16,78 %) ;
- (ospf, REQ, `-`) : 1 362 → 1 045 (76,73 %) contre 1 520 → 11 (0,72 %) ;
- (arp, CON, `-`) : 2 021 → 603 (29,84 %) contre 1 881 → 28 (1,49 %) ;
- (tcp, REQ, `-`) : 2 158 → 582 (26,97 %) contre 451 → 0 ;
- (arp, INT, `-`) : 1 354 → 96 (7,09 %) contre 1 402 → 68 (4,85 %) ;
- (tcp, RST, ssh) : 60 → 51 contre 10 → 10.

Par catégorie isolée : **state INT** fournit 4 637 des 9 509 dépassements du
jour 2 (48,8 %) avec un taux de 18,14 % (contre 5,53 % au jour 1) ; REQ 1 677
(taux 45,68 % contre 0,75 %) ; CON 2 666 (1,03 % contre 0,14 %) ; FIN 475
(0,07 % contre 0,06 %). Par protocole : udp 1,65 % contre 0,08 % ; tcp 0,47 %
contre 0,11 % ; ospf 76,24 % contre 0,71 % ; arp 20,71 % contre 2,92 %. Par
service : dns 1,38 % contre **0,00 %** ; `-` 1,25 % contre 0,15 %.

Le trafic ordinaire a la même queue les deux jours : (tcp, FIN, http) 0,27 %
contre 0,26 %, (tcp, FIN, `-`) 0,04 % des deux côtés. L'excédent du jour 2 ne
vient pas de là.

### Ce qui distingue ces flux d'un jour à l'autre, à catégorie égale

- **state = INT** (25 569 lignes au jour 2, 5 375 au jour 1) : ce sont les
  compteurs de contexte `ct_*` qui diffèrent le plus. ct_dst_src_ltm KS 0,743
  (médiane **22 contre 2**, quantile 99 % 54 contre 13) ; ct_srv_dst 0,599
  (22 contre 6) ; ct_dst_sport_ltm 0,598 (7 contre 2) ; ct_srv_src 0,591 ;
  ct_src_ltm 0,581 (10 contre 2) ; ct_src_dport_ltm 0,579 (9 contre 2).
- **service = dns** (190 189 lignes au jour 2, 176 105 au jour 1) : Sintpkt KS
  0,562 (médianes 0,008 et 0,010, quantiles 99 % 0,018 et 0,021), Dintpkt 0,467,
  ct_dst_src_ltm 0,302 (quantile 99 % 42 contre 5), dur 0,156, Sload 0,142
  (quantile 99 % 5,28·10⁸ contre 1,17·10⁸).
- Parmi les flux en dépassement du jour 2, les médianes sont : ct_dst_src_ltm 12
  (contre 2 pour tous), Sintpkt 60,2 (contre 0,73), et **ackdat, tcprtt, synack
  = 0** : les flux de la queue n'ont pas de mesure de handshake. Les grandes
  valeurs de ackdat, tcprtt, synack au jour 2 (quantiles 99 % ci-dessus) sont
  donc une autre différence entre les jours, qui n'explique pas la queue des
  scores.

### Dans le temps

- Jour 2 : des dépassements **à chaque heure**, entre 0,5 % et 1,7 % des
  normaux de l'heure. Pas de rafale unique.
- Jour 1 : 909 des 1 162 dépassements (78 %) tombent dans deux heures, 12 h UTC
  (520, 0,6 %) et 16 h UTC (389, 0,4 %) ; les autres heures sont à 0,0 %–0,1 %.

### Lecture

Mesuré : la queue plus lourde du jour 2 est concentrée dans des flux **sans
réponse ou à peine répondus** (état INT et REQ, ou CON avec service `-`) sur
udp (dns compris), ospf et arp. Le jour 2 en contient plus (INT : 2,689 % contre
0,533 % ; udp/INT/dns : 17 985 lignes contre 2 564) et, à catégorie égale, ils
apparaissent avec des compteurs de contexte `ct_*` beaucoup plus élevés
(médiane de ct_dst_src_ltm 22 contre 2 pour INT), c'est-à-dire au milieu de
séries denses de connexions. Les flux normaux du jour 1 de ces mêmes catégories
sont plus rares et plus isolés, et ne dépassent presque jamais le seuil.

Non établi : la cause de cette différence de densité (génération du trafic,
configuration du banc de test), et si ces flux du jour 2 sont réellement
normaux ou du bruit d'étiquetage. Seul ce qui a été mesuré va dans le README.

Conséquence pour le protocole : la calibration jour 2 → jour 1 est
conservatrice parce que les normaux du jour 2 contiennent une population de
flux INT/REQ denses absente du jour 1. Elle n'est pas due à une dérive de
l'ensemble des colonnes (6 colonnes sur 38 avec KS > 0,1).

---

## M18 — Coût d'un autoencodeur sur cette machine, et ACP de référence (2026-09-18)

Contrainte de l'auteur : 8 Go de RAM, pas de GPU, moins de 30 minutes de temps
d'entraînement total pour pouvoir itérer ; savoir maintenant si les K
entraînements de la calibration en 5 blocs (M16) sont trop longs. PyTorch
2.14.0 (version CPU) installé dans le venv ; `requirements.txt` mis à jour.
Le banc ne cherche pas la meilleure architecture, n'utilise ni attaque ni test.

Commandes (les temps varient de quelques pour cent d'une exécution à l'autre) :

    venv/bin/python src/bench_autoencoder.py
    venv/bin/python src/bench_autoencoder.py --threads 8 --archs petit moyen --batch-sizes 1024 --curve-epochs 0
    venv/bin/python src/bench_autoencoder.py --threads 1 --archs petit moyen --batch-sizes 1024 --curve-epochs 0
    venv/bin/python src/bench_autoencoder.py --threads 2 --archs petit moyen --batch-sizes 1024 --curve-epochs 0
    venv/bin/python src/bench_autoencoder.py --archs moyen --batch-sizes 1024 --curve-archs moyen --curve-epochs 40
    venv/bin/python src/bench_autoencoder.py --archs --curve-archs

Autoencodeur mesuré : perceptron symétrique, ReLU, perte MSE moyenne par ligne
(sur les 56 colonnes), Adam, taux d'apprentissage 10⁻³, 56 colonnes en entrée
(jeu `unsup` après préprocesseur). Trois tailles de couches cachées, dont la
dernière est le goulot : « petit » [32, 16, 8] (5 024 paramètres), « moyen »
[128, 64, 16] (33 224), « large » [256, 128, 32] (103 256). Entraînement de bloc
= 760 682 lignes (80 % des 950 853 normaux).

### Temps d'une epoch sur 80 % des normaux (4 threads, le défaut de PyTorch ici)

- Petit : 3,11 s (lot 256), **1,11 s (lot 1 024)**, 0,91 s (lot 4 096).
- Moyen : 4,26 s (lot 256), **2,08 s (lot 1 024)**, 1,87 s (lot 4 096).
- Large : 13,20 s (lot 256), **12,15 s (lot 1 024)**, 8,48 s (lot 4 096).
- Notation des 950 853 normaux : petit 0,35 s, moyen 0,92 s, large 3,81 s (lot
  1 024).
- **Pic de mémoire : 2 273 Mo** (X en float32 : 213 Mo).

**Nombre de threads** (lot 1 024, une epoch, petit puis moyen) : 1 thread 3,63 s
et 6,68 s ; 2 threads 3,78 s et 6,50 s ; **4 threads 1,11 s et 2,08 s** ; **8
threads 6,57 s et 8,08 s**. Sur ces petits réseaux, 8 threads sont de 4 à 6 fois
plus lents que 4 (cause non investiguée). La machine annonce 8 cœurs logiques.
Le nombre de threads est donc à fixer explicitement dans le code et la
configuration (4), pas à laisser au défaut.

### Coût total de la calibration en 5 blocs plus le modèle final

Calcul arithmétique (**extrapolation linéaire des temps mesurés, pas une
exécution complète**) : 5 modèles de bloc sur 80 % des lignes plus un modèle
final sur 100 % (× 1,25) = 6,25 fois le temps d'une epoch de bloc, par epoch,
plus moins de 15 s de notation. Lot 1 024 :

- Petit : 30 epochs → 208 s (**3,5 min**) ; 50 epochs → 347 s (5,8 min).
- Moyen : 30 epochs → 390 s (**6,5 min**) ; 40 epochs → 520 s (8,7 min).
- Large : 15 epochs → 1 139 s (19 min) ; 30 epochs → 2 278 s (**38 min, hors
  budget**) ; avec un lot de 4 096 et 30 epochs → 1 590 s (26,5 min, à la
  limite, et l'optimisation change).

**La calibration en 5 blocs est donc abordable pour les architectures petite et
moyenne** (moins de 10 minutes chacune) ; le repli sur l'option 1 (seuil tiré
des scores d'entraînement) n'est pas nécessaire pour elles. Seule l'architecture
large dépasse le budget de 30 minutes.

### Convergence sur des normaux tenus à l'écart

Validation = dernier bloc de temps (20 % des normaux). Le préprocesseur `unsup`
a vu ce bloc : la fuite ne porte que sur le scaler, acceptable pour un banc de
vitesse, pas pour la calibration finale. Erreur de reconstruction par ligne
(moyenne, médiane, quantile 99 %) :

- **Petit**, epoch 15 : entraînement 0,0358 ; validation 0,0372 ; 0,02455 ;
  0,2795. Décroissance encore lente (epoch 7 : moyenne 0,0459).
- **Moyen**, epoch 15 : 0,0013 ; validation 0,0015 ; 0,00047 ; 0,0214. Epoch 30 :
  0,0009 ; validation 0,0009 ; 0,00020 ; 0,0142. Epoch 40 : 0,0008 ; validation
  0,0009 ; 0,00026 ; 0,0124. La validation fluctue d'une epoch à l'autre (epoch
  35 : moyenne 0,0010, médiane 0,00033) et se stabilise vers 25 à 30 epochs.

### ACP de référence (modèle linéaire équivalent)

Ajustée sur les mêmes 80 % des normaux, évaluée sur le même bloc de validation,
avec la même erreur par ligne. Variance expliquée cumulée : 4 composantes
61,33 % ; 8 : 79,88 % ; 12 : 88,73 % ; 16 : 93,65 % ; 24 : 98,54 % ; 32 :
99,76 % ; 48 : 100 %. Erreur de validation (moyenne, médiane, quantile 99 %) :

- ACP 8 composantes : 0,1578 ; 0,09251 ; 1,4275 ;
- ACP 16 composantes : 0,0507 ; 0,02725 ; 0,3709 ;
- ACP 32 composantes : 0,0016 ; 0,00038 ; 0,0206.

Lecture : à goulot égal l'autoencodeur reconstruit bien mieux que le modèle
linéaire : petit (goulot 8) 0,0372 contre 0,1578 (environ 4 fois mieux) ; moyen
(goulot 16) 0,0009 à 0,0015 contre 0,0507 (34 à 56 fois mieux), soit la
fidélité qu'il faut 32 composantes linéaires pour atteindre. Les normaux ont donc
une structure non linéaire que l'ACP ne capte qu'avec environ le double de
dimensions. Ce que cela ne dit pas : si un meilleur ajustement aux normaux
améliore la détection d'attaques (un autoencodeur trop fidèle reconstruit aussi
les attaques). Cela ne peut se lire que sur le test, donc ne peut pas servir à
choisir l'architecture sans rompre le protocole non supervisé.

---

## M19 — Autoencodeur : décisions déclarées avant tout résultat (2026-09-18)

Ces décisions et le fichier `config.toml` sont committés avant l'écriture et
l'exécution de `src/models/autoencoder.py`, pour que la déclaration d'avance soit
vérifiable dans l'historique.

### Décisions de l'auteur

1. **Architecture principale : « moyen » [128, 64, 16]** (33 224 paramètres).
2. **« Petit » [32, 16, 8] (5 024 paramètres) déclaré d'avance, rapporté sur le
   même pied que le moyen**, pas comme un simple test de sensibilité. Raison :
   d'après M18, le moyen reconstruit les normaux tenus à l'écart à 0,0009 (erreur
   moyenne, epochs 30 à 40) et le petit à 0,0372 (epoch 15), soit environ 41 fois
   moins bien. Un autoencodeur qui reconstruit les normaux presque parfaitement
   peut aussi reconstruire les attaques. **Si le petit détecte mieux que le moyen
   malgré une reconstruction 41 fois moins bonne, c'est un résultat central du
   projet**, pas une note de bas de page ; à l'inverse, si le moyen détecte mieux,
   cela se rapporte de la même façon. Aucun choix entre les deux après la lecture
   des résultats : les deux figurent, avec les mêmes mesures.
3. **Budget d'entraînement : 30 epochs fixes**, identiques pour les 5 blocs de
   calibration et le modèle final, sans arrêt précoce.
4. **Perte : erreur quadratique moyenne, sans écrêtage** des valeurs
   standardisées (les queues résiduelles de `ackdat`, `tcprtt`, `synack`, avec
   des |z| jusqu'à 79, sont laissées telles quelles et le risque est mesuré, pas
   masqué).
5. **4 threads fixés dans `config.toml`** (M18 : 8 threads sont 4 à 6 fois plus
   lents).
6. Le reste comme pour l'Isolation Forest (M16) : calibration en 5 blocs de temps
   contigus avec préprocesseur réajusté par bloc, budgets de faux positifs 1 %,
   0,1 % (référence) et 0,01 %, même rapport (AUC-PR, rappel aux trois budgets,
   taux visé contre observé, rappel par famille avec découpe jumeau/sans jumeau,
   rappel au taux lu sur le test). Autres réglages : lot 1 024, Adam, taux
   d'apprentissage 10⁻³, graine 42, ACP non utilisée pour le score.

### À reprendre dans le README (limites, labellisation contestée)

Les flux d'état INT ou REQ en séries denses (médiane de `ct_dst_src_ltm` de 22
pour les INT du jour 2, contre 2 au jour 1 ; 2,689 % des normaux du jour 2 sont
INT contre 0,533 % au jour 1 ; 17 985 flux udp/INT/dns au jour 2 contre 2 564 au
jour 1 ; M17) sont étiquetés **normaux** au jour 2. **Hypothèse de l'auteur, non
vérifiée et non affirmée** : ce profil ressemble à un balayage (nombreuses
connexions courtes sans réponse). À signaler tel quel, avec la labellisation
contestée du jeu (M04 et limites connues). Ce qui est mesuré : la densité de ces
flux et leur part dans la queue des scores (M17) ; ce qui ne l'est pas : leur
nature réelle. Une vérification serait possible avec `srcip`, `dstip` et
`dsport`, exclus des features mais présents dans `data/raw` (par exemple le
nombre de destinations et de ports distincts par source dans ces séries) ; elle
n'a pas été faite.
