"""Inspection des CSV bruts UNSW-NB15 : effectifs, colonnes, libellés attack_cat.

Bibliothèque standard uniquement : cet audit précède toute préparation et ne
doit pas dépendre de la stack d'analyse.

Usage : python src/inspect_raw.py [--raw-dir data/raw]
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

CSV_NAMES = [f"UNSW-NB15_{i}.csv" for i in range(1, 5)]
FEATURES_NAME = "NUSW-NB15_features.csv"
# Colonnes 48 et 49 (indices 47 et 48) : catégorie d'attaque et étiquette binaire.
IDX_ATTACK_CAT = 47
IDX_LABEL = 48
OFFICIAL_TOTAL = 2_540_044


def read_feature_names(path: Path) -> list[str]:
    """Retourne les noms de colonnes tels qu'écrits dans le fichier features."""
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    return [row[1] for row in rows[1:]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    names = read_feature_names(args.raw_dir / FEATURES_NAME)
    print(f"Fichier features : {len(names)} noms")
    for i, n in enumerate(names, 1):
        if n != n.strip() or " " in n:
            print(f"  nom suspect (espace) en position {i} : {n!r}")

    total = 0
    widths: Counter = Counter()
    cat_raw: Counter = Counter()
    cat_label: Counter = Counter()
    label_raw: Counter = Counter()
    for name in CSV_NAMES:
        n_file = 0
        # utf-8-sig : le fichier 1 commence par un BOM qui polluerait srcip.
        with (args.raw_dir / name).open(newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                n_file += 1
                widths[len(row)] += 1
                cat_raw[row[IDX_ATTACK_CAT]] += 1
                label_raw[row[IDX_LABEL]] += 1
                cat_label[(row[IDX_ATTACK_CAT], row[IDX_LABEL])] += 1
        print(f"{name} : {n_file} enregistrements")
        total += n_file

    print(f"\nTotal : {total} (officiel : {OFFICIAL_TOTAL}, écart : {total - OFFICIAL_TOTAL:+d})")
    print(f"Largeurs de ligne (colonnes: lignes) : {dict(widths)}")
    print(f"Label (valeurs brutes) : {dict(label_raw)}")

    print("\nattack_cat, valeurs brutes (repr) avec effectif, puis répartition par Label :")
    for cat, n in sorted(cat_raw.items()):
        by_label = {lb: c for (ct, lb), c in cat_label.items() if ct == cat}
        print(f"  {cat!r}: {n}  Label={dict(sorted(by_label.items()))}")

    normalized = Counter()
    for cat, n in cat_raw.items():
        normalized[cat.strip().lower()] += n
    print("\nAprès strip().lower() :")
    for cat, n in sorted(normalized.items()):
        print(f"  {cat!r}: {n}")
    print(f"Variantes brutes : {len(cat_raw)}, après normalisation : {len(normalized)}")


if __name__ == "__main__":
    main()
