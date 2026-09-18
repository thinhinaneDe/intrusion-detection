"""Répartition temporelle des enregistrements UNSW-NB15 par fichier CSV.

Stime (colonne 29) est un horodatage Unix en secondes, converti en UTC. Sert à
vérifier comment les 4 CSV se répartissent entre les deux jours de simulation
(22-1-2015 et 17-2-2015) avant de choisir un découpage temporel.

Usage : python src/inspect_time.py [--raw-dir data/raw]
"""

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CSV_NAMES = [f"UNSW-NB15_{i}.csv" for i in range(1, 5)]
IDX_STIME = 28
IDX_ATTACK_CAT = 47
IDX_LABEL = 48


def utc(ts: int) -> str:
    """Formate un horodatage Unix en date-heure UTC lisible."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    day_total: Counter = Counter()
    day_cat: Counter = Counter()
    for name in CSV_NAMES:
        per_day: Counter = Counter()
        lo, hi, monotone, prev = None, None, True, None
        with (args.raw_dir / name).open(newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                ts = int(row[IDX_STIME])
                lo = ts if lo is None else min(lo, ts)
                hi = ts if hi is None else max(hi, ts)
                if prev is not None and ts < prev:
                    monotone = False
                prev = ts
                day = utc(ts)[:10]
                per_day[day] += 1
                day_total[day] += 1
                day_cat[(day, row[IDX_ATTACK_CAT].strip() or "(normal)")] += 1
        print(f"{name} : Stime min {utc(lo)}, max {utc(hi)} UTC ; "
              f"trié par Stime : {monotone}")
        for day, n in sorted(per_day.items()):
            print(f"    {day} : {n}")

    print("\nTotal par jour (UTC) :")
    for day, n in sorted(day_total.items()):
        print(f"  {day} : {n}")
    print("\nPar jour et par catégorie (strip appliqué) :")
    for (day, cat), n in sorted(day_cat.items()):
        print(f"  {day}  {cat!r}: {n}")


if __name__ == "__main__":
    main()
