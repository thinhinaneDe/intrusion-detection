"""Qualité des 41 features retenues : valeurs vides, non numériques, catégories.

Pour chaque colonne conservée comme feature (les 47 moins srcip, dstip, sport,
dsport, Stime, Ltime), compte les valeurs vides ou blanches et les valeurs non
numériques ; pour les trois colonnes nominales, liste les catégories par côté
du découpage (jour 2 = entraînement, jour 1 = test). Sert à décider du
nettoyage avant `prepare.py`, sans rien supposer.

Usage : python src/inspect_columns.py [--raw-dir data/raw] [--day2-start 2015-02-18]
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from inspect_duplicates import IDENT_TIME, IDX_ATTACK_CAT, IDX_STIME, N_COLS, read_rows

FEATURES_NAME = "NUSW-NB15_features.csv"
NOMINAL = {"proto", "state", "service"}


def feature_names(path: Path) -> list[str]:
    """Noms du fichier features, espaces retirés (ex. `ct_src_ ltm` -> `ct_src_ltm`)."""
    import csv
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        return [row[1].replace(" ", "") for row in list(csv.reader(f))[1:]]


def is_number(s: str) -> bool:
    """Vrai si s se lit comme un nombre décimal."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--day2-start", default="2015-02-18")
    args = parser.parse_args()
    day2_ts = datetime.strptime(args.day2_start, "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()

    names = feature_names(args.raw_dir / FEATURES_NAME)
    kept = [i for i in range(IDX_ATTACK_CAT) if i not in IDENT_TIME]
    blank = {i: Counter() for i in kept}
    junk = {i: Counter() for i in kept}
    lo: dict[int, float] = {}
    hi: dict[int, float] = {}
    values = {i: Counter() for i in kept if names[i] in NOMINAL or names[i] in
              ("is_ftp_login", "is_sm_ips_ports", "ct_flw_http_mthd", "ct_ftp_cmd")}
    cat_by_side = {i: {1: Counter(), 2: Counter()} for i in kept if names[i] in NOMINAL}

    # Nature des blancs : ils sont propres au jour 2 ; sur quels services, et
    # comment les lignes non vides de ce jour se répartissent-elles ?
    blank_cols = [i for i in kept if names[i] in ("ct_flw_http_mthd", "is_ftp_login", "ct_ftp_cmd")]
    idx_service = names.index("service")
    blank_service = {i: Counter() for i in blank_cols}
    filled_service = {i: Counter() for i in blank_cols}
    filled_values = {i: {1: Counter(), 2: Counter()} for i in blank_cols}
    blank_together = Counter()

    for row in read_rows(args.raw_dir):
        day = 2 if int(row[IDX_STIME]) >= day2_ts else 1
        svc = row[idx_service].decode("latin-1")
        blank_together[(day, tuple(row[i].strip() == b"" for i in blank_cols))] += 1
        for i in blank_cols:
            if row[i].strip() == b"":
                blank_service[i][svc] += 1
            else:
                filled_service[i][svc] += 1
                filled_values[i][day][row[i].decode("latin-1")] += 1
        for i in kept:
            v = row[i].decode("latin-1")
            if v.strip() == "":
                blank[i][day] += 1
                if i in values:
                    values[i][repr(v)] += 1
                continue
            if names[i] in NOMINAL:
                cat_by_side[i][day][v] += 1
            elif not is_number(v):
                junk[i][v] += 1
            else:
                x = float(v)
                lo[i] = min(lo.get(i, x), x)
                hi[i] = max(hi.get(i, x), x)
                if i in values:
                    values[i][v] += 1

    print("Colonne : vides jour 2 / jour 1 ; non numériques ; min ; max")
    for i in kept:
        if names[i] in NOMINAL:
            continue
        print(f"  {i + 1:2d} {names[i]:18s} vides {blank[i][2]:7d} / {blank[i][1]:7d} ;"
              f" non numériques {sum(junk[i].values()):3d} {dict(junk[i].most_common(3))}"
              f" ; [{lo.get(i)} ; {hi.get(i)}]")
    print("\nValeurs discrètes de colonnes à petit domaine :")
    for i, c in values.items():
        if names[i] not in NOMINAL:
            print(f"  {names[i]} : {dict(c.most_common(12))}")
    print("\nColonnes nominales : nombre de catégories par côté, non vues à l'entraînement")
    for i, sides in cat_by_side.items():
        train, test = sides[2], sides[1]
        unseen = {c: n for c, n in test.items() if c not in train}
        print(f"  {names[i]} : {len(train)} au jour 2, {len(test)} au jour 1, "
              f"{len(unseen)} du jour 1 absentes du jour 2 "
              f"({sum(unseen.values())} lignes de test)")
        print(f"    jour 2, les plus fréquentes : {dict(train.most_common(8))}")
        print(f"    absentes de l'entraînement : {dict(sorted(unseen.items(), key=lambda kv: -kv[1])[:8])}")
        print(f"    blancs (jour 2 / jour 1) : {blank[i][2]} / {blank[i][1]}")
    print("\nBlancs des trois colonnes (ordre :", [names[i] for i in blank_cols], ")")
    print("  combinaisons (jour, [blanc?, blanc?, blanc?]) :")
    for k, n in sorted(blank_together.items()):
        print(f"    {k} : {n}")
    for i in blank_cols:
        print(f"  {names[i]}")
        print(f"    service quand vide     : {dict(blank_service[i].most_common(6))}")
        print(f"    service quand renseigné : {dict(filled_service[i].most_common(6))}")
        print(f"    valeurs renseignées jour 2 : {dict(filled_values[i][2].most_common(6))}")
        print(f"    valeurs renseignées jour 1 : {dict(filled_values[i][1].most_common(6))}")
    print(f"\nColonnes lues : {N_COLS} ; features retenues : {len(kept)}")


if __name__ == "__main__":
    main()
