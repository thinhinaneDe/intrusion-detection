"""Doublons exacts et contradictions d'étiquetage dans UNSW-NB15.

Mesures :
  A. vrais doublons : lignes identiques sur les 49 colonnes ;
  B. contradictions : identiques sur les features seules (colonnes 1-47, sans
     attack_cat ni Label), étiquettes différentes. Variante « 45 colonnes »
     sans Stime/Ltime ;
  C. contradictions sur les features comportementales : identifiants et
     horodatages exclus (srcip, dstip, sport, dsport, Stime, Ltime) ;
  C'. comme C, sans stcpb ni dtcpb (numéros de séquence TCP initiaux, tirés au
     hasard à chaque connexion, donc quasi-identifiants).

Les 3 doublons de jonction entre fichiers (première ligne des fichiers 2 à 4)
sont écartés après vérification. Backdoor est fusionné en Backdoors (M05)
avant de comparer les étiquettes.

Usage : python src/inspect_duplicates.py [--raw-dir data/raw] [--day2-start 2015-02-18]
"""

import argparse
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CSV_NAMES = [f"UNSW-NB15_{i}.csv" for i in range(1, 5)]
# Indices 0-based des colonnes du fichier (numéro de colonne - 1).
IDX_SRCIP, IDX_SPORT, IDX_DSTIP, IDX_DSPORT = 0, 1, 2, 3
IDX_STCPB, IDX_DTCPB = 20, 21
IDX_STIME, IDX_LTIME = 28, 29
IDX_ATTACK_CAT = 47
N_COLS = 49
CAT_FIX = {"backdoor": "backdoors"}

IDENT_TIME = {IDX_SRCIP, IDX_SPORT, IDX_DSTIP, IDX_DSPORT, IDX_STIME, IDX_LTIME}
VARIANTS = [
    ("B. 47 colonnes (features seules)", set()),
    ("B'. 45 colonnes (sans Stime ni Ltime)", {IDX_STIME, IDX_LTIME}),
    ("C. 41 colonnes (sans srcip, dstip, sport, dsport, Stime, Ltime)", IDENT_TIME),
    ("C'. 39 colonnes (C, sans stcpb ni dtcpb)", IDENT_TIME | {IDX_STCPB, IDX_DTCPB}),
]

# Table de comptage : mask des classes (16 bits) | n jour 1 (24 bits) | n jour 2 (24 bits)
SH1, SH2 = 16, 40
M16, M24 = 0xFFFF, 0xFFFFFF


def digest(parts: list[bytes]) -> bytes:
    """Empreinte courte (8 octets) d'une liste de champs, pour économiser la mémoire."""
    return hashlib.blake2b(b",".join(parts), digest_size=8).digest()


def canon_class(raw: bytes) -> str:
    """Classe normalisée : strip, minuscules, Backdoor fusionné en Backdoors."""
    c = raw.decode("ascii").strip().lower() or "(normal)"
    return CAT_FIX.get(c, c)


def read_rows(raw_dir: Path):
    """Itère les lignes découpées en champs, en écartant les doublons de jonction."""
    prev_last = None
    for k, name in enumerate(CSV_NAMES, 1):
        with (raw_dir / name).open("rb") as f:
            first = True
            last = None
            for line in f:
                line = line.rstrip(b"\r\n")
                if k == 1 and first:
                    line = line.removeprefix(b"\xef\xbb\xbf")
                if first and prev_last is not None:
                    first = False
                    if line != prev_last:
                        raise SystemExit(f"{name} : la 1re ligne n'est pas le doublon attendu")
                    continue
                first = False
                last = line
                yield line.split(b",")
        prev_last = last


def update(table: dict, key: bytes, bit: int, day: int) -> None:
    """Met à jour masque de classes et compteurs par jour de l'entrée `key`."""
    v = table.get(key, 0)
    v |= bit
    v += 1 << (SH1 if day == 1 else SH2)
    table[key] = v


def n1(v: int) -> int:
    """Effectif du jour 1 encodé dans v."""
    return (v >> SH1) & M24


def n2(v: int) -> int:
    """Effectif du jour 2 encodé dans v."""
    return (v >> SH2) & M24


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--day2-start", default="2015-02-18",
                        help="Date UTC (AAAA-MM-JJ) à partir de laquelle commence le jour 2")
    args = parser.parse_args()
    day2_ts = datetime.strptime(args.day2_start, "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()

    class_ids: dict[str, int] = {}
    exact: dict[bytes, int] = {}
    tables = [dict() for _ in VARIANTS]
    total = 0

    for row in read_rows(args.raw_dir):
        if len(row) != N_COLS:
            raise SystemExit(f"ligne à {len(row)} champs")
        total += 1
        day = 2 if int(row[IDX_STIME]) >= day2_ts else 1
        cls = canon_class(row[IDX_ATTACK_CAT])
        bit = 1 << class_ids.setdefault(cls, len(class_ids))

        update(exact, digest(row), 0, day)
        features = row[:IDX_ATTACK_CAT]
        for table, (_, excluded) in zip(tables, VARIANTS):
            cols = [c for i, c in enumerate(features) if i not in excluded]
            update(table, digest(cols), bit, day)

    print(f"Lignes lues (doublons de jonction écartés) : {total}")
    ids = {i: c for c, i in class_ids.items()}
    normal_bit = 1 << class_ids["(normal)"]

    distinct = len(exact)
    print("\nA. Doublons exacts sur 49 colonnes")
    print(f"  lignes distinctes : {distinct}")
    print(f"  lignes en surplus (à retirer pour ne garder qu'un exemplaire) : {total - distinct}")
    print(f"  lignes distinctes présentes plusieurs fois : "
          f"{sum(1 for v in exact.values() if n1(v) + n2(v) > 1)}")
    print(f"  lignes distinctes présentes à la fois au jour 1 et au jour 2 : "
          f"{sum(1 for v in exact.values() if n1(v) and n2(v))}")

    for (title, excluded), table in zip(VARIANTS, tables):
        multi = sum(1 for v in table.values() if n1(v) + n2(v) > 1)
        contra = [v for v in table.values() if bin(v & M16).count("1") > 1]
        nva = [v for v in contra if v & normal_bit]
        ava = [v for v in contra if not v & normal_bit]
        rows = lambda vs: sum(n1(v) + n2(v) for v in vs)
        cross = [v for v in table.values() if n1(v) and n2(v)]
        cross_contra = [v for v in cross if bin(v & M16).count("1") > 1]
        print(f"\n{title}")
        print(f"  combinaisons distinctes : {len(table)}")
        print(f"  combinaisons présentes plusieurs fois : {multi}")
        print(f"  combinaisons à étiquettes contradictoires : {len(contra)}"
              f" (lignes : {rows(contra)})")
        print(f"    dont normal contre attaque : {len(nva)} (lignes : {rows(nva)})")
        print(f"    dont famille contre famille : {len(ava)} (lignes : {rows(ava)})")
        print(f"  combinaisons présentes aux deux jours : {len(cross)}"
              f" (lignes jour 1 : {sum(n1(v) for v in cross)},"
              f" lignes jour 2 : {sum(n2(v) for v in cross)})")
        print(f"    dont à étiquettes contradictoires : {len(cross_contra)}")
        pairs = Counter()
        for v in contra:
            pairs[tuple(sorted(ids[i] for i in ids if v & (1 << i)))] += 1
        for combo, n in pairs.most_common(10):
            print(f"      {combo} : {n} combinaisons")


if __name__ == "__main__":
    main()
