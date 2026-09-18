# Journal de mesures

Une entrée par mesure, datée, avec la commande exacte. Rien d'estimé.
Les résultats qui contredisent une hypothèse restent écrits.

Environnement : Python 3.12.13. Les premières mesures (M01 à M10) n'utilisent que la
bibliothèque standard (le venv était alors vide) ; depuis M11, voir `requirements.txt`.
Les commandes sont lancées depuis la racine du dépôt.

> **Avertissement sur les intervalles de confiance.** Les intervalles de Wilson
> consignés en M09, M16, M20 et M24 supposent des observations indépendantes. Or les
> attaques du test arrivent en rafales (Reconnaissance et Exploits tombent chacun dans
> 12 blocs de 10 minutes sur 76, M25) : **ces intervalles sont trop étroits**, de 3 à 5
> fois pour les rappels par famille (M26). Seuls les intervalles par blocs de temps
> (M25, M26, M28) remontent dans le README ; les rappels sans intervalle par blocs y
> figurent sans intervalle.

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

---

## M20 — Autoencodeurs moyen et petit, sur le même pied, et corrections de M18 (2026-09-18)

Décisions et code committés avant ce résultat (M19, `config.toml`,
`src/models/autoencoder.py`). Aucun réglage n'a été fait après lecture des
résultats. Commandes (les deux exécutées en parallèle, lancées à 21 h 00) :

    venv/bin/python src/models/autoencoder.py --arch moyen
    venv/bin/python src/models/autoencoder.py --arch petit
    venv/bin/python src/models/autoencoder.py --compare-only

Même calibration que l'Isolation Forest (M16) : 5 blocs de temps contigus,
préprocesseur réajusté par bloc, budgets 1 %, 0,1 % (référence) et 0,01 %. 30
epochs, lot 1 024, Adam 10⁻³, MSE sans écrêtage, 4 threads, graine 42. Perte
d'entraînement du modèle final à l'epoch 30 : moyen 0,00088, petit 0,03150.

### Corrections de M18 (coût et threads)

- **Les estimations de M18 étaient fausses d'un facteur 3 à 6.** M18 annonçait
  3,5 min (petit) et 6,5 min (moyen) pour 30 epochs. Mesuré : petit **709 s
  (11,8 min) seul**, 1 398 s en parallèle ; moyen **1 868 s (31 min) en
  parallèle**, non mesuré seul. Les deux en parallèle ont pris 31,1 min de
  temps réel (durée du moyen, le plus long), ce qui **dépasse de peu le budget de
  30 minutes** de l'auteur.
  Exécuter les deux architectures en parallèle est 2,1 fois plus lent pour
  chacune (petit : 1 386 s en parallèle contre 701 s seul, dans la seconde
  exécution) : aucun gain.
- **Cause : le temps par epoch varie d'un facteur 3 sur cette machine selon le
  moment, indépendamment du nombre de threads** (cause non investiguée). Petit,
  lot 1 024 : 1,11 s dans la première série de mesures de M18, 3,2 à 3,6 s dans
  toutes les mesures suivantes. M18 en avait tiré à tort que « 4 threads est le
  bon réglage » : la mesure à 4 threads était la première de la série, celles à
  1, 2 et 8 threads sont venues après, dans le régime lent. Mesures refaites
  après coup (petit puis moyen, lot 1 024) : 4 threads 3,59 s et 6,29 s ; 2
  threads 3,54 s et 6,78 s ; 1 thread 3,18 s et 5,83 s. **Sur ces réseaux le
  nombre de threads ne change pas le temps** ; la conclusion de M18 sur les
  threads est retirée. `threads = 4` reste dans `config.toml` (décision
  d'origine), utile pour fixer les résultats : la relance du petit donne des
  scores identiques bit à bit (voir plus bas).
- **Surcoût fixe** d'environ une minute par architecture (préprocesseur réajusté
  à chaque bloc, notation, rapport), non compté dans les estimations de M18.

### Reproductibilité

Le petit relancé seul (701 s) donne des scores du test et hors échantillon
**identiques bit à bit** à la première exécution (écart absolu maximal 0), et des
résultats d'évaluation identiques. Le moyen n'a pas été relancé.

### Autoencodeur moyen [128, 64, 16] — 33 224 paramètres

- **AUC-PR 0,1213** (prévalence 1,395 %).
- Erreur de reconstruction des normaux hors échantillon : moyenne 0,00110,
  médiane 0,00021, quantile 99 % 0,01556.
- Budget 1 % : seuil 0,0156 ; **taux observé sur le test 6,9733 %** [6,9238 ;
  7,0232] (70 355 faux positifs, 5 585 par heure en moyenne, 27 120 la pire
  heure) ; rappel 58,19 % [57,38 ; 58,99] ; VP 8 308, FP 70 355, FN 5 970, VN
  938 563 ; précision 10,56 %.
- Budget 0,1 % : seuil 0,1011 ; **observé 1,8965 %** [1,8701 ; 1,9233] (19 134
  faux positifs, 1 519 par heure, 14 616 la pire heure) ; rappel 11,19 % [10,69 ;
  11,72] ; VP 1 598, FN 12 680 ; précision 7,71 %.
- Budget 0,01 % : seuil 0,4011 ; **observé 0,1940 %** [0,1856 ; 0,2027] (1 957
  faux positifs, 155 par heure) ; rappel 1,53 % [1,34 ; 1,75] ; précision 10,06 %.
- Rappel lu au même taux sur le test (1 % ; 0,1 % ; 0,01 %) : **6,11 %** [5,73 ;
  6,51] ; **0,64 %** [0,53 ; 0,79] ; **0,00 %** [0,00 ; 0,03].
- Quantiles du score (50 %, 99 %, 99,9 %, 99,99 %) : hors échantillon 0,0002 ;
  0,0156 ; 0,1011 ; 0,4001 · normaux du test 0,0002 ; 0,1875 ; 0,5655 ; 1,5590 ·
  attaques du test 0,0325 ; 0,4583 ; 0,9658 ; 1,2794.

### Autoencodeur petit [32, 16, 8] — 5 024 paramètres

- **AUC-PR 0,1144.**
- Erreur de reconstruction des normaux hors échantillon : moyenne 0,03476,
  médiane 0,02457, quantile 99 % 0,24403.
- Budget 1 % : seuil 0,2440 ; **observé 2,4589 %** [2,4288 ; 2,4893] (24 808
  faux positifs, 1 970 par heure, 15 922 la pire heure) ; rappel 22,80 % [22,12 ;
  23,50] ; VP 3 256, FP 24 808, FN 11 022, VN 984 110 ; précision 11,60 %.
- Budget 0,1 % : seuil 0,9381 ; **observé 0,3903 %** [0,3783 ; 0,4027] (3 938
  faux positifs, 313 par heure, 2 775 la pire heure) ; rappel 2,72 % [2,46 ;
  3,00] ; VP 388, FN 13 890 ; précision 8,97 %.
- Budget 0,01 % : seuil 3,2460 ; **observé 0,0036 %** [0,0026 ; 0,0049] (36
  faux positifs, 2,9 par heure) ; rappel 0,06 % [0,03 ; 0,11] ; VP 8 ; précision
  18,18 %.
- Rappel lu au même taux sur le test : **6,23 %** [5,84 ; 6,63] ; **1,41 %**
  [1,23 ; 1,62] ; **0,27 %** [0,20 ; 0,37].
- Quantiles du score : hors échantillon 0,0246 ; 0,2440 ; 0,9380 ; 3,2448 ·
  normaux du test 0,0282 ; 0,6007 ; 1,3158 ; 2,4825 · attaques du test 0,1333 ;
  1,5156 ; 3,0548 ; 4,0002.

### Rappel par famille (n = effectifs de test)

Au seuil calibré (le taux de faux positifs réel diffère d'un modèle à l'autre,
voir ci-dessus ; les comparaisons entre modèles se font plutôt sur le rappel lu
au même taux). Budget 1 % (analysis, backdoors, dos, exploits, fuzzers, generic,
reconnaissance, shellcode, worms), en % :

- moyen : 100,00 ; 90,30 ; 75,88 ; 75,61 ; 29,52 ; 92,87 ; 13,05 ; 3,14 ; 50,00 ;
- petit : 13,95 ; 10,37 ; 29,33 ; 52,87 ; 10,47 ; 8,22 ; 8,22 ; 0,90 ; 33,33.

Budget 0,1 % (référence) : moyen 8,64 ; 13,38 ; 16,97 ; 26,15 ; 3,08 ; 6,64 ;
1,15 ; 0,00 ; 16,67 · petit 1,33 ; 5,35 ; 7,15 ; 5,10 ; 1,20 ; 1,52 ; 0,46 ;
0,00 ; 16,67. Budget 0,01 % : moyen 0,66 ; 2,01 ; 4,24 ; 3,02 ; 0,20 ; 1,24 ;
0,40 ; 0,00 ; 16,67 · petit 0,00 ; 0,00 ; 0,85 ; 0,02 ; 0,00 ; 0,00 ; 0,00 ;
0,00 ; 0,00. Les intervalles de Wilson sont dans
`data/processed/results/autoencoder_*.json`.

Au même taux de faux positifs lu sur le test (1 % ; 0,1 % ; 0,01 %), en % :
Analysis moyen 1,00 ; 0,00 ; 0,00 · petit 1,66 ; 0,66 ; 0,00 — Backdoors 5,69 ;
1,00 ; 0,00 · 5,69 ; 3,34 ; 1,00 — DoS 10,67 ; 2,30 ; 0,00 · 11,76 ; 5,58 ; 1,70
— **Exploits 13,63 ; 1,16 ; 0,00 · 12,96 ; 2,13 ; 0,45** — Fuzzers 1,58 ; 0,00 ;
0,00 · 3,31 ; 0,75 ; 0,00 — Generic 4,66 ; 0,67 ; 0,00 · 3,39 ; 0,74 ; 0,14 —
**Reconnaissance 0,80 ; 0,11 ; 0,00 · 0,75 ; 0,34 ; 0,00** — Shellcode 0,00 ;
0,00 ; 0,00 · 0,45 ; 0,00 ; 0,00 — Worms 16,67 ; 8,33 ; 0,00 · 16,67 ; 4,17 ;
0,00.

Découpe avec/sans jumeau : identique à l'Isolation Forest (M16), car le jeu est
le même : 13 lignes d'attaque ont un jumeau (12 Fuzzers, 1 Shellcode), toutes
non détectées par les deux architectures ; Reconnaissance et Exploits n'ont
aucune ligne avec jumeau.

### Diagnostic de l'option 1

Optimisme mesuré (taux hors échantillon au seuil tiré des scores
d'entraînement, rapporté au budget visé ; 1 % / 0,1 % / 0,01 %) : moyen ×1,30 /
×1,72 / ×3,27 ; petit ×1,18 / ×1,31 / ×2,96 ; pour mémoire Isolation Forest
×1,30 / ×1,32 / ×4,12 (M16). Ces écarts sont bien plus petits que l'écart de
calibration jour 2 → jour 1 (voir ci-dessous).

### Comparaison des trois modèles

- **AUC-PR : Isolation Forest 0,3081 ; moyen 0,1213 ; petit 0,1144.** Les deux
  autoencodeurs sont à 8,7 et 8,2 fois la prévalence ; l'Isolation Forest à 22
  fois. **Aucun autoencodeur ne bat l'Isolation Forest sur l'AUC-PR** (règle du
  projet : le rapporter tel quel). La différence moyen-petit (0,0069) n'a pas
  d'intervalle de confiance calculé.
- **Rappel lu au même taux de faux positifs sur le test** (1 % ; 0,1 % ; 0,01 %) :
  Isolation Forest 42,92 % ; 2,49 % ; 0,06 % · moyen 6,11 % ; 0,64 % ; 0,00 % ·
  petit 6,23 % ; 1,41 % ; 0,27 %. À 1 %, l'Isolation Forest est 7 fois meilleure
  que les deux autoencodeurs, qui sont indiscernables entre eux (intervalles qui
  se recouvrent). À 0,1 % et 0,01 %, **le petit est meilleur que le moyen**
  (1,41 % contre 0,64 %, intervalles disjoints ; 0,27 % contre 0,00 %). À 0,1 %
  l'Isolation Forest reste devant (2,49 %) ; à 0,01 % le petit la dépasse (0,27 %
  contre 0,06 %, tous rappels très bas). Le moyen reconstruit les
  normaux hors échantillon 31,6 fois mieux en moyenne (0,00110 contre 0,03476 ;
  117 fois pour la médiane) sans mieux détecter : au taux de 1 % il est
  équivalent, aux taux stricts il est moins bon, et son AUC-PR n'est meilleure
  que de 0,0069.
- **Taux de faux positifs observé sur le test contre visé (1 % ; 0,1 % ; 0,01 %)** :
  Isolation Forest 0,1152 % ; 0,0162 % ; 0,0038 % (au-dessous, calibration
  conservatrice) · petit 2,4589 % ; 0,3903 % ; 0,0036 % (2,5 fois et 3,9 fois
  au-dessus, puis au-dessous) · moyen 6,9733 % ; 1,8965 % ; 0,1940 % (7 fois, 19
  fois et 19 fois au-dessus). À budget de référence 0,1 %, le seuil déployable
  donne 13 fausses alertes par heure pour l'Isolation Forest, 313 pour le petit et
  1 519 pour le moyen (au lieu des 80 visées).
- **La calibration jour 2 → jour 1 se dégrade quand le modèle colle plus aux
  normaux du jour 2.** Rapport entre le quantile 99 % des scores des normaux du
  test et celui des scores hors échantillon du jour 2 : Isolation Forest 0,95
  (0,5882 / 0,6190) ; petit 2,46 (0,6007 / 0,2440) ; moyen 12,0 (0,1875 / 0,0156).
  Constat sur trois modèles, pas une loi établie. Les médianes des normaux
  coïncident (moyen : 0,0002 des deux côtés). Cela recoupe M17 : les normaux du
  jour 2 et du jour 1 diffèrent surtout dans les queues (flux INT/REQ denses).

### Lecture

- La question posée en M19 (le petit détecte-t-il mieux que le moyen malgré une
  reconstruction bien moins bonne ?) reçoit une réponse **partielle** : pas au
  taux de 1 % ni sur l'AUC-PR, mais oui aux taux stricts de 0,1 % et 0,01 %, où
  l'écart est significatif au sens des intervalles de M20 (indépendance des
  lignes supposée, optimiste).
- Les deux autoencodeurs sont des références faibles face à l'Isolation Forest sur
  ces données. Ces résultats ne sont pas expliqués : ce qui reste à examiner
  (non fait) est ce qui, dans les normaux du jour 1, obtient une forte erreur de
  reconstruction chez le moyen.
- Le budget de référence 0,1 % ne donne du contraste qu'entre modèles à
  calibration comparable ; le taux observé, pas le taux visé, est ce qui décide
  du déploiement. À reprendre dans le README (limites) : calibration sous dérive
  temporelle.

---

## M21 — Résultat : la calibration s'effondre d'autant plus que le modèle épouse les normaux d'entraînement (2026-09-18)

Décision de l'auteur : consigner explicitement comme **résultat**, non comme note
technique, ce qui ressort de M16 et M20. Aucune nouvelle exécution : les chiffres
viennent des quantiles déjà consignés.

### Le constat

Rapport entre le quantile 99 % des scores des normaux **du test** et celui des
scores **hors échantillon** des normaux du jour 2 (la calibration) :

- Isolation Forest : **0,95** (0,5882 / 0,6190) ;
- autoencodeur petit : **2,46** (0,6007 / 0,2440) ;
- autoencodeur moyen : **12,0** (0,1875 / 0,0156).

Conséquence sur le taux de faux positifs observé pour un budget de 1 % : 0,12 %
(Isolation Forest), 2,46 % (petit), 6,97 % (moyen). Plus un modèle épouse le
trafic normal d'entraînement, plus sa calibration s'effondre sur du trafic
normal qu'il n'a pas vu. Le seuil déployable calibré sur le jour 2 ne tient pas
sur le jour 1 pour les modèles qui collent le plus au jour 2.

### Indicateur de fidélité sur une échelle commune

La fidélité de reconstruction n'est mesurée que pour les autoencodeurs (erreur
hors échantillon : moyen 0,00110, petit 0,03476, soit 31,6 fois). L'Isolation
Forest ne reconstruit rien. Un indicateur commun aux trois : le rapport entre le
quantile 99 % des scores d'un modèle sur ses propres normaux d'entraînement et
celui des scores hors échantillon (arithmétique sur les quantiles de M16 et
M20). Plus il est bas, plus le modèle note mieux ce qu'il a vu que ce qu'il n'a
pas vu, sur le même jour :

- Isolation Forest **0,993** (0,6145 / 0,6190) ;
- petit **0,871** (0,2126 / 0,2440) ;
- moyen **0,686** (0,0107 / 0,0156).

Cet ordre est celui du rapport de calibration ci-dessus (0,95 ; 2,46 ; 12,0).

### Ce que cela établit, et ce que cela n'établit pas

- **Trois points, pas une loi.** Trois modèles, une seule expérience, un seul
  découpage temporel.
- **Les trois modèles diffèrent par plus d'un facteur** : l'Isolation Forest est
  d'une autre famille (arbres d'isolement, sous-échantillons de 256 lignes) ; sa
  position sur l'axe « fidélité » n'est pas mesurée par la même grandeur que celle
  des autoencodeurs, seulement par l'indicateur commun ci-dessus.
- **Le contraste le plus propre est entre les deux autoencodeurs** : même famille,
  même perte, mêmes données, un seul facteur qui change (la capacité, 5 024
  contre 33 224 paramètres). Le rapport de calibration passe de 2,46 à 12,0.
- **Non testé** : une gradation de la capacité ou du nombre d'epochs, qui dirait
  si le rapport de calibration est monotone en la fidélité. Sans cela, le lien
  avec la fidélité reste une association observée sur trois points.
- Cela recoupe M17 : les normaux du jour 2 et du jour 1 diffèrent surtout dans les
  queues (flux INT/REQ denses), donc un modèle qui apprend finement le jour 2 note
  mal ces différences.

### À reprendre dans le README

Section limites : la calibration d'un seuil sur un jour ne se transfère pas à
un autre jour ; le budget de faux positifs visé est une cible, pas une garantie ;
c'est le taux observé qui décide du déploiement. Rapporter les trois rapports
(0,95 ; 2,46 ; 12,0), présentés comme trois observations et non comme une loi.

---

## M22 — Coût d'un gradient boosting sur cette machine (2026-09-18)

Question : chiffrer les 18 entraînements du protocole supervisé (3 conditions ×
(5 blocs de calibration + 1 modèle final)) avant de choisir la méthode de
calibration. Aucune métrique de détection n'est évaluée, aucun hyperparamètre
n'est choisi.

### Choix de la bibliothèque

**XGBoost (paquet `xgboost-cpu` 3.4.1)**, pas LightGBM. LightGBM 4.7.0 s'installe
mais ne se charge pas (`libgomp.so.1: cannot open shared object file`) : il
exige la bibliothèque système OpenMP, absente de cette machine et à installer par
`apt`, ce qui contredit la règle « le dépôt tourne sur une machine vierge en
suivant uniquement le README ». `xgboost-cpu` embarque sa propre `libgomp` (24 Mo
dans le venv ; le paquet `xgboost` complet fait plus de 300 Mo). Les deux
bibliothèques sont autorisées par le cahier des charges ; le choix est motivé par
l'installation, non par la performance. LightGBM a été désinstallé.

### Temps mesurés

Commandes (jeu A : 1 036 218 lignes × 58 colonnes, 85 365 attaques, 8,24 % ;
`tree_method = hist`, taux d'apprentissage par défaut, graine 42) :

    venv/bin/python src/bench_supervised.py --threads 4
    venv/bin/python src/bench_supervised.py --threads 8 --depths 6 --trees 300

Entraînement (4 threads ; première puis seconde exécution, à quelques minutes
d'écart, stables à 5 % près) :

- 100 arbres, profondeur 6 : 14,0 s et 15,0 s ;
- 300 arbres, profondeur 6 : 35,8 s et 35,7 s ;
- 100 arbres, profondeur 10 : 17,8 s et 18,7 s ;
- 300 arbres, profondeur 10 : 49,3 s et 49,9 s ;
- notation de 1 023 196 lignes : 0,8 à 4,1 s selon la taille du modèle ;
- **8 threads, 300 arbres, profondeur 6 : 45,1 s**, contre 35,7 s à 4 threads (plus
  lent, comme en M18 pour l'autoencodeur) ;
- pic de mémoire : environ 2,9 Go.

### Coût du protocole (arithmétique sur ces temps, pas une exécution complète)

Par condition : 5 blocs à 80 % des lignes plus un modèle final à 100 % = 5,0
entraînements pleins ; 15 pour les trois conditions (B et C ont 3 % de lignes de
moins que A, négligé). Avec 4 threads :

- 100 arbres, profondeur 6 : 15 × 14,0 s = 210 s (3,5 min) ;
- 300 arbres, profondeur 6 : 15 × 35,8 s = 537 s (9,0 min) ;
- 300 arbres, profondeur 10 : 15 × 49,3 s = 740 s (12,3 min) ;
- plus environ 2 min de surcoût fixe (préprocesseur réajusté par bloc, notation).

Une recherche d'hyperparamètres sur 4 configurations (profondeur 6 ou 10, 100 ou
300 arbres) par validation croisée en 5 blocs coûterait (14,0 + 35,8 + 17,8 +
49,3) × 5 × 0,8 = 468 s (7,8 min) sur les données d'une condition.

**Le protocole tient largement dans le budget de 30 minutes.** Réserve : le temps
par epoch de l'autoencodeur a varié d'un facteur 3 selon le moment (M18, M20) ;
ces temps-ci sont stables sur deux exécutions rapprochées, mais un facteur 3
donnerait 27 min pour 300 arbres de profondeur 6.

### Contexte pour la calibration supervisée

Prévalence des attaques : 8,24 % dans A (85 365 sur 1 036 218), 5,01 % dans B et C
(50 191 sur 1 001 044), 1,395 % dans le test (M10, M11).

---

## M23 — Modèle supervisé : grille et critère déclarés avant la recherche (2026-09-18)

Ces décisions et la section `[supervised]` de `config.toml` sont committées avant
l'écriture de `src/models/supervised.py` et avant toute recherche
d'hyperparamètres, pour que la déclaration d'avance soit vérifiable.

### Décisions de l'auteur

1. **XGBoost (paquet `xgboost-cpu`) confirmé.** Argument retenu : un README qui
   exige un `apt install` préalable ne tient pas sa promesse de reproduction (M22).
2. **Réglage des hyperparamètres : option 2 de M22.**
   - **Grille : profondeur maximale 6 ou 10, 100 ou 300 arbres** (4 configurations).
   - **Critère : AUC-PR (précision moyenne) sur les blocs tenus à l'écart**,
     cohérent avec le reste du projet. Précision de l'assistant, à valider : la
     précision moyenne est calculée bloc par bloc (normaux et attaques du bloc,
     scores du modèle entraîné sans lui), puis **moyennée sur les 5 blocs** ; la
     configuration à la moyenne la plus haute est retenue ; à égalité à 4
     décimales, la moins coûteuse (moins d'arbres, puis profondeur moindre). La
     précision moyenne poolée sur les 5 blocs est aussi calculée, à titre
     d'information, et ne sert pas à choisir.
   - **Réglage sur les données de C, puis figé pour A, B et C.** Les familles
     retirées (Exploits, Reconnaissance) n'influencent ainsi aucune décision,
     même indirectement, et les trois conditions ne diffèrent que par leurs
     données. Contrepartie acceptée : la configuration retenue n'est pas
     nécessairement la meilleure pour A ou B.
   - Tous les autres hyperparamètres gardent les défauts de la bibliothèque
     (taux d'apprentissage, régularisation, sous-échantillonnage ; poids de classes
     non modifié), graine 42, 4 threads.
3. **Deux ajouts retenus au rapport commun** (mêmes budgets 1 %, 0,1 % et 0,01 %,
   même calibration en 5 blocs de temps que M16) :
   - **le rappel sur les attaques tenues à l'écart** : les blocs de la validation
     croisée contiennent des attaques ; au seuil calibré, leur rappel est le
     rappel sur les familles vues, un jour connu, à un moment non vu. Comparé au
     rappel du test, il isole la dérive temporelle sur familles connues (intérêt
     particulier de l'auteur) ;
   - **un diagnostic au seuil 0,5** par défaut de la bibliothèque, pour montrer
     où il tombe.
4. **Rapport : A, B et C sur le même pied, avec la découpe jumeau/sans jumeau**,
   qui sert enfin ici : 449 lignes de test de Reconnaissance (25,8 %) ont un jumeau
   dans A (415 dans B, 1 dans C ; M11).

### Précisions de mise en œuvre

- **Score** : la marge (log-odds) du modèle plutôt que la probabilité, pour éviter
  les égalités de scores près de 0 et de 1 ; la précision moyenne et le seuil par
  budget de faux positifs n'en dépendent pas (monotone). Le seuil 0,5 du
  diagnostic correspond à la marge 0.
- **Seuil de déploiement** : le quantile 1 − b des scores hors échantillon des
  seuls normaux, comme pour les modèles non supervisés ; les attaques ne servent
  jamais à le fixer. Ce seuil ne dépend pas de la prévalence d'attaques
  d'entraînement (8,24 % dans A, 5,01 % dans B et C, contre 1,395 % au test) ; la
  précision au seuil, elle, dépend de la prévalence du test.

### Vérification des données avant de fixer la règle d'agrégation

Attaques par bloc de temps de C (5 blocs de 200 208 ou 200 209 lignes) : 8 904 ;
11 155 ; 10 047 ; 10 207 ; 9 878 (4,45 % à 5,57 % de chaque bloc). Les 7 familles
de C sont présentes dans chaque bloc (Worms : 31, 32, 27, 30, 27 ; Shellcode 248 à
270 ; Analysis 308 à 549). La répartition est comparable pour A (15 932 à 18 763
attaques par bloc, 7,69 % à 9,05 %) et B (9 357 à 11 105). La précision moyenne
par bloc est donc bien définie et la moyenne sur les blocs est une règle
d'agrégation raisonnable.

---

## M24 — Modèle supervisé sur A, B et C, et signature TTL (2026-09-18)

Grille et critère committés avant la recherche (M23, `8396d06`), code committé avant
l'exécution (`65719c7`). Commandes :

    venv/bin/python src/models/supervised.py
    venv/bin/python src/inspect_ttl.py

Durées : recherche 494 s ; conditions A, B, C 89, 82 et 82 s ; **12,9 min au total**
(22 h 26 à 22 h 39), dans le budget de 30 minutes.

### Recherche d'hyperparamètres (données de C, 5 blocs de temps)

Précision moyenne (AUC-PR) par bloc tenu à l'écart (blocs 1 à 5), moyenne
(critère) et poolée (information) :

- profondeur 6, 100 arbres : 0,9439 0,9598 0,9580 0,9656 0,9553 ; **moyenne 0,9565** ;
  poolée 0,9568 ;
- profondeur 6, 300 arbres : 0,9422 0,9587 0,9565 0,9642 0,9538 ; 0,9551 ; 0,9554 ;
- profondeur 10, 100 arbres : 0,9413 0,9576 0,9561 0,9636 0,9534 ; 0,9544 ; 0,9547 ;
- profondeur 10, 300 arbres : 0,9392 0,9565 0,9552 0,9629 0,9517 ; 0,9531 ; 0,9535.

**Retenue : profondeur 6, 100 arbres** (la plus haute et la moins coûteuse),
figée pour A, B et C. Les écarts entre configurations sont petits (0,0034 entre la
meilleure et la pire) et la complexité supplémentaire dégrade légèrement le critère.

### Résultats (mêmes budgets 1 %, 0,1 % référence, 0,01 % ; même calibration que M16)

**AUC-PR au test : A 0,9757 ; B 0,9696 ; C 0,9744** (prévalence 1,395 %).

**Taux de faux positifs observé au test contre visé, rappel calibré, précision**
(1 % ; 0,1 % ; 0,01 %) :

- **A** : 0,1804 % ; 0,0087 % ; 0,0006 % · rappel 90,96 % ; 73,33 % ; 49,38 % ·
  précision 87,71 % ; 99,17 % ; 99,91 %. À 0,1 % : 88 faux positifs, 7,0 fausses
  alertes par heure en moyenne, 42 la pire heure ; VP 10 470, FN 3 808.
- **B** : 0,2281 % ; 0,0193 % ; 0,0007 % · rappel 91,51 % ; 74,02 % ; 46,02 % ·
  précision 85,03 % ; 98,19 % ; 99,89 %. À 0,1 % : 195 faux positifs, 15,5 par
  heure, 96 la pire heure.
- **C** : 0,1493 % ; 0,0096 % ; 0,0006 % · rappel 91,62 % ; 64,18 % ; 44,52 % ·
  précision 89,68 % ; 98,95 % ; 99,91 %. À 0,1 % : 97 faux positifs, 7,7 par heure,
  50 la pire heure.

**Le taux observé est inférieur au taux visé** dans les trois conditions (de 4,4 à 17
fois selon le budget) : la calibration jour 2 → jour 1 est conservatrice, comme pour
l'Isolation Forest (M16) et à l'inverse des autoencodeurs (M20). Au budget de
référence, 7 à 15 fausses alertes par heure au lieu des 80 visées.

**Rappel lu au même taux sur le test** (1 % ; 0,1 % ; 0,01 %) : A **100,00 %** ;
85,56 % ; 73,74 % · B **100,00 %** ; 82,48 % ; 71,27 % · C **100,00 %** ; 86,29 % ;
64,52 %. **À 1 % le rappel est saturé à 100 % pour les trois conditions** : ce
budget n'a aucun contraste pour un modèle supervisé ici (le seuil lu vaut −11 : la
quasi-totalité des normaux a une marge proche de −11 et toutes les attaques sont
au-dessus). Le contraste se lit à 0,1 % et 0,01 %.

**Diagnostic au seuil par défaut (marge 0, probabilité 0,5)** : test : A taux de faux
positifs 0,1301 %, rappel 87,49 % (VP 12 492, FP 1 313, FN 1 786) ; B 0,1346 %,
84,86 % ; C 0,0846 %, 84,31 %. Hors échantillon (jour 2) : A 0,6698 %, 90,62 % ; B
0,3517 %, 86,79 % ; C 0,5981 %, 84,16 %. Le seuil par défaut ne correspond à aucun
budget : il donne un taux de faux positifs de 0,08 % à 0,13 % au test et de 0,35 % à
0,67 % hors échantillon.

### Rappel sur les attaques tenues à l'écart contre rappel du test (même seuil calibré, mêmes familles)

Tenues à l'écart (jour 2, moment non vu, à taux de faux positifs = budget) / test
(à ce même seuil, où le taux de faux positifs est plus bas que le budget) :

- **A** : 93,33 / 90,96 % (1 %) ; 79,90 / 73,33 % (0,1 %) ; 59,91 / 49,38 % (0,01 %) ;
- **B** : 93,35 / 91,51 % ; 79,88 / 74,02 % ; 58,90 / 46,02 % ;
- **C** (7 familles vues) : 90,06 / 88,18 % ; 70,56 / 59,78 % ; 59,24 / 46,89 %.

À seuil égal, le test est en dessous de 2 à 13 points. **Ce n'est pas une perte de
capacité de détection pure** : le taux de faux positifs au test est lui aussi plus
bas que celui de la calibration, donc les scores des normaux et ceux des attaques
sont décalés vers le bas au test. À taux de faux positifs égal, le rappel du test
n'est pas inférieur à celui des blocs tenus à l'écart (A, toutes familles : 85,56 %
lu au test contre 79,90 % hors échantillon à 0,1 % ; 73,74 % contre 59,91 % à
0,01 %). Par famille au budget 0,1 % (A, hors échantillon / test) : Reconnaissance
99,42 / 96,49 ; Exploits 92,54 / 90,82 ; DoS 91,47 / 87,27 ; Fuzzers 22,96 / 22,90 ;
Generic 98,44 / 98,02.

### Les familles retirées de C, avec la découpe jumeau/sans jumeau

Rappel au test, **lu au même taux** (A ; B ; C) :

- **Exploits** : 100,00 ; 100,00 ; 100,00 % (1 %) · 97,40 ; 96,68 ; 94,83 % (0,1 %) ·
  91,37 ; 89,16 ; 83,57 % (0,01 %).
- **Reconnaissance** : 100,00 ; 100,00 ; 100,00 % (1 %) · 98,91 ; 98,68 ; **89,94 %**
  (0,1 %) · 96,55 ; 95,80 ; **42,18 %** (0,01 %).

Écarts en points (A − B : effet du volume seul ; B − C : effet de la famille inédite
à volume constant), rappel lu au même taux : Exploits 0,1 % : +0,72 et +1,86 ;
0,01 % : +2,20 et +5,59 · **Reconnaissance 0,1 % : +0,23 et +8,74 ; 0,01 % : +0,75 et
+53,62**. Aucun intervalle de confiance sur ces écarts n'est calculé (mesures
appariées, non faites).

Au seuil calibré : Exploits 0,1 % : A 90,82, B 91,49, C 83,23 % ; 0,01 % : 58,41 ;
52,89 ; 55,84 %. Reconnaissance 0,1 % : 96,49 ; 96,38 ; **41,38 %** ; 0,01 % : 50,06 ;
38,97 ; **6,67 %**.

**Découpe jumeau/sans jumeau, Reconnaissance** (449 lignes avec jumeau dans A, 415 dans
B, 1 dans C) : au seuil calibré à 0,01 %, A 91,3 % avec jumeau contre 35,71 % sans ;
B 49,6 % contre 35,62 % ; à 0,1 %, A 100 % contre 95,27 %. La mémorisation gonfle
donc bien le rappel global de A et de B aux budgets stricts. **Elle n'explique pas
l'écart B − C** : sans jumeau, l'écart lu au même taux est de +52,34 points à 0,01 %
(94,49 % pour B contre 42,15 % pour C) et de +8,32 à 0,1 %, contre +53,62 et +8,74
avec toutes les lignes. Exploits n'a que 3 lignes avec jumeau : sans objet.

### Importance des variables (gain du modèle final)

- A : ct_state_ttl **65,2 %**, sttl 14,0 %, proto arp 8,5 %, service `-` 4,1 %.
- B : ct_state_ttl **51,5 %**, proto arp 17,4 %, service `-` 10,0 %, proto unas 8,5 %,
  sttl 2,4 %.
- C : ct_state_ttl **70,4 %**, proto tcp 9,5 %, ct_dst_sport_ltm 8,9 %, sttl 4,5 %.

### Ce que séparent les colonnes TTL (mesure descriptive)

`ct_state_ttl` est décrit dans le fichier features comme le nombre de connexions par
état selon des plages de TTL source et destination (colonnes 6, 10, 11).

- **Normaux** : TTL source 31 pour 94,0 % des flux au jour 2 et 98,3 % au jour 1 ;
  `ct_state_ttl` = 0 pour 96,6 % (jour 2) et 99,4 % (jour 1).
- **Attaques** : `ct_state_ttl` vaut 1 ou 2 pour **98,7 %** des attaques au jour 2
  (53,2 % + 45,5 %) et **98,8 %** au jour 1 (60,0 % + 38,8 %), contre 2,9 % (2,1 % +
  0,8 %) et 0,5 % (0,3 % + 0,2 %) des normaux. TTL source ≥ 200 : 79,9 % des attaques
  et 2,9 % des normaux au jour 2 ; 79,5 % et 0,42 % au jour 1.
- **Les familles retirées portent la même signature** (jour 1) : Exploits
  `ct_state_ttl` 1 ou 2 pour 98,3 % (TTL source 254 pour 40,4 %, 62 pour 59,4 %) ;
  Reconnaissance 99,5 % (TTL source 254 pour 99,9 %).
- Les normaux à TTL source 254 sont 2,89 % au jour 2 contre 0,42 % au jour 1 (recoupe
  M17 : quantile 99 % de `sttl` des normaux 254 contre 31).

### Lecture

- **Réponse à la question du projet, sous réserve de la mesure TTL.** Retirer les
  familles de l'entraînement coûte peu sur **Exploits** (B − C : +1,9 point à 0,1 %,
  +5,6 à 0,01 % ; C garde 83,6 % de rappel à 0,01 %) et beaucoup sur
  **Reconnaissance** aux budgets stricts (B − C : +8,7 à 0,1 %, **+53,6 à 0,01 %** :
  42 % contre 96 %). Le volume seul (A − B) coûte moins de 1 point sur Reconnaissance
  et jusqu'à 2,2 points sur Exploits. Exploitation d'une vulnérabilité et balayage se
  comportent donc de façon très différente, comme l'auteur l'anticipait (M10).
- **Réserve majeure : ces résultats sont très probablement gonflés par un artefact du
  banc d'essai.** Le modèle repose pour 52 à 70 % sur `ct_state_ttl`, qui sépare à
  lui seul 98,8 % des attaques de 99,5 % des normaux au jour 1, y compris pour les
  familles jamais vues. Une AUC-PR de 0,97 pour C, dont 40 % des attaques du test
  sont de familles absentes de l'entraînement, est cohérente avec un raccourci
  partagé par toutes les familles (TTL des hôtes générateurs) et non avec une
  généralisation du comportement d'attaque. **Non testé** : l'ablation des colonnes
  TTL (`sttl`, `dttl`, `ct_state_ttl`), qui dirait ce qui reste. Cette réserve
  s'applique aussi à l'Isolation Forest et aux autoencodeurs, pour lesquels un TTL
  de 254 est une anomalie par rapport aux normaux à 31.
- Le budget de 1 % ne discrimine pas les conditions supervisées (100 % partout) ; la
  lecture utile est à 0,1 % et 0,01 %.
- L'écart de calibration (taux observé de 4 à 17 fois sous le budget) est du même
  sens que pour l'Isolation Forest et opposé à celui des autoencodeurs.

### À reprendre dans le README (limites)

Artefact TTL : `ct_state_ttl` et `sttl` séparent attaques et normaux dans les deux
jours et pour toutes les familles ; le trafic normal a un TTL source de 31 (94 % à
98 %), les attaques 254 ou 62 (`ct_state_ttl` 1 ou 2 dans 98,7 % des cas). C'est une
caractéristique du banc d'essai synthétique (IXIA PerfectStorm, M04) plutôt qu'une
signature d'attaque, comparable au risque d'apprendre une adresse IP. Hypothèse non
vérifiée : les normaux à TTL source 254 (2,89 % au jour 2 contre 0,42 % au jour 1)
seraient des flux issus des hôtes générateurs d'attaques étiquetés normaux, ce qui
rejoindrait la labellisation contestée (M19).

---

## M25 — Ablation TTL et rééchantillonnage apparié : décisions déclarées avant tout résultat (2026-09-18)

Ces décisions, `config_sans_ttl.toml` et l'héritage de configuration
(`load_config`, clé `extends`) sont committés avant toute exécution sans TTL et avant
tout calcul d'intervalle, pour que la déclaration d'avance soit vérifiable.

### 1. Ablation TTL

**Décision de l'auteur** : retirer `sttl`, `dttl` et `ct_state_ttl` des features,
déclaré d'avance comme l'exclusion des IP et des horodatages (M08), et réentraîner :

- **les trois modèles supervisés A, B, C** avec la configuration figée (profondeur 6,
  100 arbres, M24), sans nouvelle recherche d'hyperparamètres ;
- **les trois modèles non supervisés** : Isolation Forest, autoencodeur moyen et
  autoencodeur petit, mêmes hyperparamètres, même calibration en 5 blocs de temps,
  mêmes budgets. Argument de l'auteur : un TTL de 254 face à des normaux à 31 est une
  anomalie triviale, donc le raccourci vaut aussi pour eux.

**Colonnes retirées** (numéros du fichier features) : `sttl` (10), `dttl` (11),
`ct_state_ttl` (37, décrite dans le fichier features comme le nombre de connexions par
état selon des plages de TTL source et destination, donc dérivée de l'état et des
TTL). Il reste **38 features**, contre 41.

**Rapport** : les deux versions **côte à côte, avec et sans TTL**. Ce n'est pas une
correction : c'est une mesure de ce que le banc d'essai offre comme raccourci, et elle
ira dans le README comme résultat.

Ce qui ne change pas : lignes des jeux (les jeux A, B, C, unsup et test contiennent
exactement les mêmes lignes ; le tirage de B ne dépend pas des colonnes), graines,
découpage temporel, déduplication, budgets 1 % / 0,1 % (référence) / 0,01 %. Ce qui
change mécaniquement : la liste des colonnes log1p (recalculée par jeu sur l'entraînement,
les colonnes TTL en moins), la dimension d'entrée des autoencodeurs, et le marquage des
jumeaux (défini sur les features, donc sur 38 colonnes : davantage de lignes peuvent
avoir un jumeau).

**Ce qui n'est pas retiré, et n'est pas déclaré ici** : les autres colonnes qui pourraient
porter un artefact du banc d'essai (compteurs `ct_*`, protocole `arp`, service `-`,
apparus dans l'importance des variables de M24). Une éventuelle seconde ablation serait
une nouvelle décision, à déclarer avant d'être lancée.

Exécution prévue (jeux et résultats dans `data/processed_sans_ttl/`) :

    venv/bin/python src/prepare.py --config config_sans_ttl.toml
    venv/bin/python src/verify_prepare.py --config config_sans_ttl.toml
    venv/bin/python src/models/isolation_forest.py --config config_sans_ttl.toml
    venv/bin/python src/models/supervised.py --config config_sans_ttl.toml --skip-tuning
    venv/bin/python src/models/autoencoder.py --config config_sans_ttl.toml

### 2. Intervalles sur les écarts B − C par rééchantillonnage apparié

**Décision de l'auteur** : intervalles sur les écarts B − C par rééchantillonnage
**apparié** (mêmes lignes de test pour les deux conditions), **sur Reconnaissance à
0,01 % en priorité** (« le résultat central »).

**Vérification préalable des données** (répartition des lignes de test dans le temps ;
test : 1 023 196 lignes sur 756 minutes) :

- blocs de 5 minutes : 150 blocs non vides ; les 1 740 lignes de Reconnaissance tombent
  dans **24 blocs** (le plus chargé en contient 4,8 %, les trois plus chargés 14,3 %) ;
  celles d'Exploits (4 042) dans 24 blocs (8,7 % ; 17,7 %) ;
- blocs de 10 minutes : 76 blocs ; Reconnaissance dans **12 blocs** (9,4 % ; 27,8 %),
  Exploits dans 12 blocs (13,1 % ; 30,9 %) ;
- blocs de 30 minutes : 26 blocs ; les deux familles dans 4 blocs seulement.

**Les attaques du test arrivent en quelques rafales** : le nombre d'observations
indépendantes pour le rappel d'une famille est de l'ordre de la dizaine de blocs, pas de
1 740 ou 4 042 lignes. **Les intervalles de Wilson consignés jusqu'ici (M09, M16, M20,
M24), qui supposent des lignes indépendantes, sont donc beaucoup trop étroits pour les
rappels par famille.** Le rééchantillonnage par blocs de temps est nécessaire.

**Méthode déclarée** (`src/paired_bootstrap.py`) :

- **Rééchantillonnage apparié par blocs de temps** : on tire, avec remise, des blocs de
  temps contigus du test ; les deux conditions comparées sont évaluées sur les mêmes
  lignes tirées. **Variante principale : blocs de 10 minutes.** Sensibilité : blocs de
  5 minutes, et rééchantillonnage des lignes une à une (indépendance supposée, montré
  pour mesurer de combien elle sous-estime l'incertitude). 1 000 réplications, graine
  42, intervalle à 95 % par percentiles.
- **Grandeur** : écart de rappel en points de pourcentage, pour Exploits et
  Reconnaissance, A − B (volume) et B − C (famille inédite), à 1 %, 0,1 % et 0,01 %.
  **Deux points de fonctionnement** : au **même taux lu sur le test** (le seuil de chaque
  condition est recalculé à chaque réplication sur les normaux tirés), et au **seuil
  calibré** (seuils fixes de la calibration).
- **Variante sans jumeau** : pour Reconnaissance, écartement des lignes de test ayant un
  jumeau dans B ou dans C, pour que la contamination (M11, M24) ne joue pas.
- Appliqué aux **deux versions**, avec et sans TTL.

---

## M26 — Ablation TTL : résultats avec et sans TTL, et intervalles apparié par blocs (2026-09-18)

Décisions et colonnes déclarées avant tout résultat (M25, `d5af93f`). Commandes :

    venv/bin/python src/prepare.py --config config_sans_ttl.toml
    venv/bin/python src/verify_prepare.py --config config_sans_ttl.toml
    venv/bin/python src/models/isolation_forest.py --config config_sans_ttl.toml
    venv/bin/python src/models/supervised.py --config config_sans_ttl.toml --skip-tuning
    venv/bin/python src/models/autoencoder.py --config config_sans_ttl.toml
    venv/bin/python src/paired_bootstrap.py --config config.toml
    venv/bin/python src/paired_bootstrap.py --config config_sans_ttl.toml
    venv/bin/python src/compare_ablation.py

Durées : préparation et contrôles, Isolation Forest, supervisé (3 × 82 à 91 s),
autoencodeurs (moyen 751 s, petit 329 s) : 26 min de bout en bout ; rééchantillonnage
en parallèle. Contrôles d'intégrité sans TTL : mêmes doublons supprimés (416 624 et 64 006),
mêmes effectifs par jeu et par famille, 29 colonnes log1p (au lieu de 32) et listes
identiques dans les quatre jeux, scaler ajusté sur l'entraînement seul (écart nul), B et C
inclus dans A, dimensions de X 53 (unsup), 55 (A), 54 (B et C). Jumeaux (38 colonnes) :
unsup 1 020, A 1 561, B 1 509, C 1 110 lignes de test (M11, avec TTL : 1 017, 1 555, 1 503,
1 104) ; Reconnaissance 449, 415 et 1 dans A, B, C, inchangé.

### AUC-PR au test (avec TTL / sans TTL) ; prévalence 1,395 %

- Isolation Forest **0,3081 / 0,1176** ; autoencodeur moyen 0,1213 / 0,0909 ; petit
  0,1144 / 0,0608.
- Supervisé A 0,9757 / 0,9484 ; B 0,9696 / 0,9495 ; C 0,9744 / 0,9440.

### Par budget (avec / sans, en %) : taux de faux positifs observé ; rappel calibré ; rappel lu au même taux

Budget 1 % :
- Isolation Forest : 0,1152 / 0,4117 ; 3,39 / 0,39 ; **42,92 / 2,88**.
- AE moyen : 6,9733 / 5,4359 ; 58,19 / 46,52 ; 6,11 / 5,13. AE petit : 2,4589 / 3,1411 ;
  22,80 / 15,41 ; 6,23 / 4,97.
- Supervisé A : 0,1804 / 0,3248 ; 90,96 / 92,21 ; 100,00 / 99,95. B : 0,2281 / 0,3232 ;
  91,51 / 91,70 ; 100,00 / 99,94. C : 0,1493 / 0,2277 ; 91,62 / 90,17 ; 100,00 / 99,85.

Budget 0,1 % (référence) :
- Isolation Forest : 0,0162 / 0,1321 ; 0,27 / 0,03 ; **2,49 / 0,01**.
- AE moyen : 1,8965 / 1,6290 ; 11,19 / 9,11 ; 0,64 / 0,28. AE petit : 0,3903 / 0,7108 ;
  2,72 / 3,63 ; 1,41 / 1,29.
- Supervisé A : 0,0087 / 0,0824 ; 73,33 / 73,97 ; **85,56 / 75,83**. B : 0,0193 / 0,0651 ;
  74,02 / 72,35 ; **82,48 / 75,59**. C : 0,0096 / 0,0578 ; 64,18 / 61,54 ; **86,29 / 73,69**.

Budget 0,01 % :
- Isolation Forest : 0,0038 / 0,0714 ; 0,02 / 0,00 ; 0,06 / 0,00.
- AE moyen : 0,1940 / 0,2172 ; 1,53 / 0,85 ; 0,00 / 0,00. AE petit : 0,0036 / 0,0001 ;
  0,06 / 0,01 ; 0,27 / 0,27.
- Supervisé A : 0,0006 / 0,0048 ; 49,38 / 44,71 ; **73,74 / 56,42**. B : 0,0007 / 0,0023 ;
  46,02 / 45,31 ; **71,27 / 60,39**. C : 0,0006 / 0,0076 ; 44,52 / 39,85 ; **64,52 / 41,78**.

Sans TTL l'Isolation Forest passe **au-dessus** du taux visé aux budgets stricts (0,1321 %
pour 0,1 %, 0,0714 % pour 0,01 %) alors qu'elle était au-dessous avec TTL.

### Rappel lu au même taux, par famille (1 % ; 0,1 % ; 0,01 % ; avec / sans TTL, en %)

Exploits : IF 13,88 / 2,25 ; 1,01 / 0,02 ; 0,12 / 0,00 · AE moyen 13,63 / 11,95 ; 1,16 /
0,40 ; 0,00 / 0,00 · AE petit 12,96 / 11,18 ; 2,13 / 2,60 ; 0,45 / 0,49 · sup. A 100,00 /
99,85 ; 97,40 / 91,86 ; 91,37 / 70,73 · B 100,00 / 99,80 ; 96,68 / 91,91 ; 89,16 / 77,61 ·
C 100,00 / 99,68 ; 94,83 / 87,95 ; 83,57 / 49,33.

Reconnaissance : IF 42,18 / 0,46 ; 0,34 / 0,00 ; 0,00 / 0,00 · AE moyen 0,80 / 0,69 ; 0,11 /
0,29 ; 0,00 · AE petit 0,75 / 0,34 ; 0,34 / 0,00 ; 0,00 · sup. A 100,00 / 99,94 ; 98,91 / 96,61 ;
96,55 / 73,45 · B 100,00 / 100,00 ; 98,68 / 97,24 ; 95,80 / 79,83 · C 100,00 / 99,89 ; 89,94 /
**62,47** ; 42,18 / **3,91**.

Toutes les familles, budget 0,1 %, lu au même taux (avec / sans ; colonnes : IF, AE moyen, AE
petit, sup. A, B, C) : Analysis 3,3/0,0 · 0,0/0,3 · 0,7/0,0 · 88,0/80,7 · 92,4/81,1 · 82,7/81,1 ;
Backdoors 4,7/0,0 · 1,0/0,3 · 3,3/0,0 · 99,0/96,7 · 98,7/96,7 · 98,3/97,0 ; DoS 3,6/0,0 · 2,3/0,6 ·
5,6/3,3 · 96,5/89,0 · 95,4/89,9 · 95,8/88,8 ; Exploits 1,0/0,0 · 1,2/0,4 · 2,1/2,6 · 97,4/91,9 ·
96,7/91,9 · 94,8/88,0 ; **Fuzzers 5,7/0,0 · 0,0/0,2 · 0,8/0,1 · 53,5/29,8 · 43,9/28,5 · 63,6/40,2** ;
Generic 0,8/0,0 · 0,7/0,1 · 0,7/1,6 · 99,8/98,1 · 99,4/98,4 · 99,6/98,8 ; Reconnaissance 0,3/0,0 ·
0,1/0,3 · 0,3/0,0 · 98,9/96,6 · 98,7/97,2 · 89,9/62,5 ; Shellcode 0,0/0,0 · 0,0/0,0 · 0,0/0,0 ·
96,0/78,9 · 89,7/74,0 · 92,4/84,3 ; Worms 8,3/0,0 · 8,3/0,0 · 4,2/8,3 · 100,0/95,8 · 100,0/91,7 ·
100,0/95,8.

### Importance des variables du modèle supervisé sans TTL (gain)

A : Dload 33,9 %, ackdat 13,9 %, state CON 12,1 %. B : ackdat 22,9 %, dmeansz 22,5 %, smeansz
7,3 %. C : dmeansz 32,0 %, ackdat 13,4 %, state INT 9,2 %. Avec TTL (M24) : ct_state_ttl 52 à
70 %. Diagnostic au seuil par défaut sans TTL (test) : A taux de faux positifs 0,2512 %, rappel
88,09 % ; B 0,1812 %, 82,48 % ; C 0,1508 %, 81,80 %.

### Calibration sans TTL : le motif de M21 persiste

Rapport du quantile 99 % des scores des normaux du test sur celui des scores hors
échantillon : Isolation Forest **0,948** (0,5865 / 0,6186), AE petit **2,54** (0,6128 /
0,2414), AE moyen **9,60** (0,1354 / 0,0141) ; avec TTL : 0,95 ; 2,46 ; 12,0. Indicateur
commun (quantile 99 % dans l'échantillon / hors échantillon) : 1,010 ; 0,956 ; 0,752
(avec TTL 0,993 ; 0,871 ; 0,686). L'ordre est le même sans TTL ; toujours trois points,
pas une loi. Erreur de reconstruction hors échantillon sans TTL : moyen 0,00094 (médiane
0,00023), petit 0,03950 (0,02835).

### Rééchantillonnage apparié par blocs de temps (1 000 réplications, graine 42, IC à 95 %)

Écarts en points de rappel lu au même taux. **Variante principale : blocs de 10 minutes**
(76 blocs, 12 contiennent Reconnaissance, 12 Exploits) :

- **Reconnaissance, avec TTL** : B − C +8,74 [+0,20 ; +22,59] à 0,1 % ; **+53,62 [+31,12 ; +62,44]
  à 0,01 %** ; A − B +0,75 [−0,04 ; +2,42] à 0,01 %.
- **Reconnaissance, sans TTL** : B − C **+34,77 [+19,41 ; +45,59]** à 0,1 % ; **+75,92 [+69,28 ;
  +82,05] à 0,01 %** ; A − B −6,38 [−11,46 ; −2,33] à 0,01 %.
- **Exploits, avec TTL** : B − C +1,86 [+0,09 ; +3,47] à 0,1 % ; +5,59 [+0,81 ; +8,94] à
  0,01 % ; A − B +2,20 [−0,16 ; +4,92].
- **Exploits, sans TTL** : B − C +3,96 [+2,20 ; +6,57] à 0,1 % ; **+28,28 [+20,82 ; +33,36] à
  0,01 %** ; A − B −6,88 [−11,37 ; −3,24].
- **Sans jumeau** (lignes sans jumeau dans A, B ni C), Reconnaissance : avec TTL B − C +11,77
  [+0,28 ; +29,45] à 0,1 % et +63,98 [+41,47 ; +70,34] à 0,01 % ; sans TTL +45,70 [+26,04 ;
  +58,28] et +67,93 [+60,41 ; +75,80]. La contamination par jumeaux (M11) ne fait pas l'écart.
- Au seuil calibré (seuils fixes), Reconnaissance : B − C +55,00 [+51,09 ; +58,80] à 0,1 % et
  +32,30 [+26,38 ; +38,57] à 0,01 % avec TTL ; +60,40 [+55,89 ; +65,55] et +36,38 [+30,61 ;
  +42,27] sans TTL.

**Les intervalles par blocs sont beaucoup plus larges que par lignes** : pour Reconnaissance
avec TTL à 0,01 %, largeur 31,3 points (blocs de 10 minutes), 25,4 (blocs de 5 minutes, [+35,65 ;
+61,07]) et 10,1 (lignes une à une, [+46,86 ; +56,96]) ; à 0,1 %, 22,4 contre 4,8 (lignes). Les
intervalles de Wilson des rappels par famille (M09, M16, M20, M24) sont de l'ordre des seconds :
ils sont trop étroits. Le résultat central (B − C à 0,01 % sur Reconnaissance) exclut zéro
dans toutes les variantes et les deux versions.

**Limites de ces intervalles** : ils couvrent l'échantillonnage des lignes de test (par blocs
de temps), pas la variabilité de l'entraînement (une seule exécution par condition, un seul
tirage de B, XGBoost déterministe à données fixées). Le A − B significativement négatif sans
TTL à 0,01 % (−6,4 et −6,9 points) pourrait refléter cette variabilité plutôt qu'un effet du
volume ; non testé.

### Lecture

- **Le TTL était l'essentiel de la détection non supervisée par l'Isolation Forest** : AUC-PR
  0,308 → 0,118 ; rappel lu à 1 % 42,9 % → 2,9 % ; Reconnaissance 42,2 % → 0,5 %. Sans lui, les
  trois modèles non supervisés sont très faibles aux budgets stricts (rappel lu à 0,1 % :
  0,01 % à 1,29 % ; AUC-PR de 4,4 à 8,4 fois la prévalence, contre 8,2 à 22 fois avec TTL).
- **Le supervisé perd une partie de ses performances mais reste très bon** : AUC-PR 0,976 →
  0,948 (A), rappel lu à 0,1 % 85,6 → 75,8 %, à 0,01 % 73,7 → 56,4 %. D'autres colonnes séparent
  aussi les attaques (`Dload`, `ackdat`, `dmeansz`, état de la connexion : importance du gain).
  Le TTL est donc un raccourci parmi d'autres, ou ces colonnes portent une vraie séparabilité ;
  la mesure ne permet pas de trancher, et aucune autre ablation n'a été déclarée.
- **Correction de la lecture de M24** : M24 écrivait que les résultats étaient « très
  probablement gonflés » par le TTL et que l'AUC-PR de C était « cohérente avec un raccourci
  partagé par toutes les familles ». L'ablation montre que **le TTL gonflait surtout le rappel
  sur les familles inédites**, et masquait donc une perte plus grande : sans TTL, l'effet de la
  famille inédite (B − C) est bien plus net, sur Reconnaissance comme sur Exploits (voir ci-dessus).
  L'effet sur l'AUC-PR globale reste modeste (0,03).
- **Réponse au projet, version sans TTL** : un modèle supervisé qui n'a jamais vu une famille la
  détecte nettement moins bien aux budgets stricts. Reconnaissance : 62,5 % au lieu de 97,2 % à
  0,1 %, 3,9 % au lieu de 79,8 % à 0,01 % ; Exploits : 88,0 % au lieu de 91,9 % à 0,1 %, 49,3 % au
  lieu de 77,6 % à 0,01 %. À 1 % le rappel reste saturé (99,7 % à 99,9 %). Un modèle qui n'a jamais
  vu d'attaque (non supervisé) n'en détecte presque aucune aux budgets stricts sans TTL.
- **Fuzzers** est la famille la plus difficile pour le supervisé (rappel lu à 0,1 % : 29,8 %,
  28,5 %, 40,2 % sans TTL ; 53,5 %, 43,9 %, 63,6 % avec) : plusieurs de ses flux sont indiscernables
  de flux normaux (M07, 449 combinaisons normal / Fuzzers).

### À reprendre dans le README (résultat)

Deux versions côte à côte, avec et sans les colonnes TTL. Mesure de ce que le banc d'essai offre
comme raccourci : le TTL porte l'essentiel de la détection de l'Isolation Forest, une partie de
celle du supervisé, et masque une part de la perte sur les familles inédites. Les intervalles de
confiance des rappels par famille doivent être ceux par blocs de temps.

---

## M27 — Limites formulées, et méthode des intervalles du README (2026-09-18)

Décisions de l'auteur, consignées avant tout calcul de la section suivante.

### Limite sur les ablations (arrêt décidé)

**Le protocole mesure ce qu'un raccourci identifié offrait ; il ne prouve pas qu'il n'en
reste aucun.** Une régression d'ablations n'a pas de critère d'arrêt : chaque colonne
retirée peut en révéler une autre (après le TTL, `Dload`, `ackdat`, `dmeansz` et l'état de
la connexion portent encore le modèle supervisé, M26). L'auteur décide de **ne pas faire
d'autre ablation** ; le README nomme cette limite dans la même formulation. Ce qui est
mesuré : l'apport du TTL. Ce qui ne l'est pas : ce qui resterait sans les autres colonnes
que le supervisé exploite.

### Limite sur la variabilité d'entraînement

**Une seule exécution par condition, un seul tirage de B** (graine 42), XGBoost déterministe
à données fixées, autoencodeurs à graine fixée. **La variabilité d'entraînement n'est pas
mesurée**, donc les petits écarts ne sont pas interprétables. Exemples concernés : le A − B
significativement négatif sans TTL à 0,01 % (−6,4 points pour Reconnaissance, −6,9 pour
Exploits, M26), la différence d'AUC-PR entre autoencodeur moyen et petit (0,007, M20), les écarts de
quelques points entre A, B et C à 0,1 %. Aucun seuil chiffré d'interprétabilité n'est posé,
faute de mesure : le README n'interprète que les écarts de plusieurs dizaines de points
(par exemple B − C sur Reconnaissance à 0,01 %) et le dit. **Non fait, piste** : répéter
l'entraînement sur plusieurs graines et plusieurs tirages de B (le protocole supervisé
complet coûte environ 5 minutes), pour mesurer cette variabilité.

### Intervalles du README : méthode déclarée

Pour que seuls des intervalles par blocs figurent dans le README, ils sont calculés pour
tous les chiffres qui y apparaissent avec un intervalle, **avec la méthode de M25** : 1 000
réplications, blocs de temps de 10 minutes, graine 42, intervalle à 95 % par percentiles, les
mêmes blocs tirés pour tous les modèles dans une réplication. Grandeurs (`src/block_ci.py`,
version avec et sans TTL) :

- l'AUC-PR de chaque modèle ;
- le taux de faux positifs observé au seuil calibré, le rappel global au seuil calibré et au
  même taux lu sur le test (le seuil est recalculé à chaque réplication sur les normaux tirés),
  à chaque budget ;
- le rappel par famille aux mêmes points de fonctionnement ;
- le rappel de deux groupes de familles : **les familles retirées de C** (Exploits et
  Reconnaissance) et **les sept autres**, qui permettent de comparer A, B et C sur les mêmes
  lignes.

Pas d'intervalle par blocs, donc rapportés sans intervalle : le rappel sur les attaques tenues à
l'écart, les rapports de calibration (0,95 ; 2,5 ; 12 et leurs équivalents sans TTL), le
diagnostic au seuil par défaut.

---

## M28 — Intervalles par blocs de temps pour tous les modèles, et corrections de M20 et M26 (2026-09-18)

Méthode déclarée en M27 (1 000 réplications, blocs de 10 minutes, graine 42, IC à 95 %),
plus des **écarts appariés** entre les trois modèles non supervisés, ajoutés à la
demande de la question posée d'avance en M19 (mêmes blocs tirés dans chaque réplication).
Commandes (les deux versions, avec et sans TTL) :

    venv/bin/python src/block_ci.py --config config.toml
    venv/bin/python src/block_ci.py --config config_sans_ttl.toml
    venv/bin/python src/report_tables.py

Contrôle : le point estimé coïncide avec les valeurs écrites par les modèles (écart
absolu maximal de 1,1·10⁻¹⁶ sur l'AUC-PR, nul sur les rappels et taux). Deux exécutions
successives (avec et sans les écarts appariés) donnent des intervalles marginaux
identiques. Les tables du README sont générées par `src/report_tables.py` depuis
`block_ci.json`, `paired_bootstrap.json` et les JSON des modèles.

### AUC-PR au test, [IC par blocs] (sans TTL / avec TTL)

- Isolation Forest 0,118 [0,058 ; 0,180] / 0,308 [0,170 ; 0,442] ;
- autoencodeur moyen 0,091 [0,041 ; 0,196] / 0,121 [0,053 ; 0,297] ; petit 0,061
  [0,029 ; 0,120] / 0,114 [0,052 ; 0,247] ;
- supervisé A 0,948 [0,905 ; 0,968] / 0,976 [0,957 ; 0,988] ; B 0,950 [0,909 ; 0,970] /
  0,970 [0,947 ; 0,985] ; C 0,944 [0,896 ; 0,964] / 0,974 [0,953 ; 0,987].

### Écarts appariés entre modèles non supervisés (AUC-PR ; rappel lu au même taux à 1 %, 0,1 %, 0,01 %, en points)

- **Avec TTL** : petit − moyen −0,007 [−0,057 ; +0,007] ; +0,12 [−24,14 ; +5,24] ; +0,77
  [−2,65 ; +1,17] ; +0,27 [−0,18 ; +0,62]. Isolation Forest − moyen +0,187 [+0,063 ; +0,250] ;
  +36,81 [−0,63 ; +47,59] ; +1,84 [−1,55 ; +3,46] ; +0,06 [−0,62 ; +0,62]. Isolation Forest −
  petit +0,194 [+0,081 ; +0,263] ; +36,69 [+11,60 ; +47,47] ; +1,07 [−0,28 ; +2,90] ; −0,22
  [−0,88 ; +0,39].
- **Sans TTL** : petit − moyen −0,030 [−0,078 ; −0,011] ; −0,17 [−5,11 ; +1,00] ; +1,01
  [−2,19 ; +1,45] ; +0,27 [+0,06 ; +1,10]. Isolation Forest − moyen +0,027 [−0,042 ; +0,055] ;
  −2,26 [−15,77 ; +0,39] ; −0,27 [−3,83 ; 0,00] ; 0,00 [−0,25 ; 0,00]. Isolation Forest − petit
  +0,057 [+0,010 ; +0,094] ; −2,09 [−10,97 ; +0,22] ; −1,28 [−1,94 ; −0,53] ; −0,27 [−1,30 ; −0,06].

### Corrections

- **M20 : « le petit détecte mieux que le moyen aux taux stricts » est retiré.** Cette
  affirmation reposait sur des intervalles de Wilson « disjoints », trop étroits. Avec
  les écarts appariés par blocs : avec TTL, aucune différence (AUC-PR −0,007
  [−0,057 ; +0,007] ; rappel à 0,1 % +0,77 [−2,65 ; +1,17] ; à 0,01 % +0,27 [−0,18 ; +0,62]) ; sans
  TTL, **le moyen a une AUC-PR plus élevée** (petit − moyen −0,030 [−0,078 ; −0,011]) et
  l'avantage du petit à 0,01 % est de 0,27 point [+0,06 ; +1,10], inférieur au point de rappel,
  donc non interprétable (M27). La réponse à la question posée d'avance en M19 est : **non, le
  petit ne détecte pas mieux que le moyen**, ni avec ni sans TTL.
- **M20 : « aucun autoencodeur ne bat l'Isolation Forest sur l'AUC-PR »** : confirmé avec TTL
  (IF − moyen +0,187 [+0,063 ; +0,250] ; IF − petit +0,194 [+0,081 ; +0,263]) ; **sans TTL, non
  établi** contre le moyen (+0,027 [−0,042 ; +0,055]) et faible contre le petit (+0,057
  [+0,010 ; +0,094]).
- **M26 : le TTL et le supervisé.** Rappel lu à 0,1 % : A 75,8 [69,6 ; 82,2] sans TTL contre 85,6
  [79,7 ; 95,7] avec ; B 75,6 [69,1 ; 81,8] contre 82,5 [75,3 ; 93,5] ; C 73,7 [66,2 ; 81,3]
  contre 86,3 [76,8 ; 96,8]. **Les intervalles se recouvrent** (comparaison non appariée, non
  faite) : l'apport du TTL au rappel du supervisé est de l'ordre de 10 points mais n'est pas établi
  statistiquement. Pour l'Isolation Forest il l'est : rappel lu à 1 % 2,9 [1,7 ; 4,3] sans TTL contre
  42,9 [31,7 ; 53,8] avec (intervalles disjoints) ; l'AUC-PR (0,118 [0,058 ; 0,180] contre 0,308
  [0,170 ; 0,442]) se recouvre à peine.

### Ce qui reste solide, et ce qui ne l'est pas

- **Solide (écarts de plusieurs dizaines de points, IC apparié excluant zéro)** : B − C sur
  Reconnaissance à 0,01 % sans TTL +75,9 [+69,3 ; +82,0] et à 0,1 % +34,8 [+19,4 ; +45,6] ; sur
  Exploits à 0,01 % sans TTL +28,3 [+20,8 ; +33,4] (M26).
- **Contrôle spécifique aux familles retirées** (sans TTL, rappel lu au même taux, groupes) : sur
  les **sept autres familles**, A, B et C sont indiscernables (0,1 % : 63,9 [51,2 ; 75,0], 63,4
  [50,3 ; 74,5], 69,2 [57,7 ; 79,0] ; 0,01 % : 46,1 [28,6 ; 59,7], 48,2 [30,5 ; 62,0], 45,9 [28,7 ;
  60,4]) ; sur **Exploits + Reconnaissance**, C chute : 0,1 % A 93,3 [90,5 ; 96,2], B 93,5 [90,9 ;
  96,2], C **80,3 [73,8 ; 87,3]** ; 0,01 % A 71,5 [63,7 ; 77,9], B 78,3 [72,0 ; 84,7], C **35,7
  [28,9 ; 44,7]**. La perte est spécifique aux familles retirées.
- **Familles de petit effectif** : les intervalles par blocs couvrent presque tout l'intervalle
  possible (Analysis, sans TTL, rappel lu à 0,1 % : 80,7 [0,0 ; 100,0] ; Backdoors 96,7 [76,7 ; 99,5] ;
  Worms 95,8 [88,5 ; 100,0] ; Shellcode 78,9 [69,2 ; 87,7]) : les rappels par famille de ces
  familles ne sont pas interprétables individuellement.
- **Écarts de quelques points** entre A, B et C, ou entre modèles non supervisés : non
  interprétés (M27, variabilité d'entraînement non mesurée).

