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
