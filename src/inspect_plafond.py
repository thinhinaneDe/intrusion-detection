"""Doublons supprimés par côté du découpage temporel, et plafond de performance.

Deux mesures, faites séparément pour chaque côté (jour 2 = entraînement,
jour 1 = test, décisions M05) :

  1. lignes supprimées par la déduplication exacte sur 49 colonnes, appliquée
     APRÈS le découpage (un seul exemplaire conservé par côté) ;
  2. plafond de performance dû aux contradictions : lignes identiques sur les
     41 features retenues (les 47 moins srcip, dstip, sport, dsport, Stime,
     Ltime) mais d'étiquettes différentes. Tout modèle qui est une fonction
     de ces 41 colonnes donne la même sortie à deux lignes identiques ; au
     mieux il en classe correctement la classe majoritaire du groupe. Erreurs
     minimales par groupe = effectif - effectif de la classe majoritaire.

La borne est calculée en connaissant les étiquettes du côté évalué (borne
oracle), pas atteignable par apprentissage ; elle dit seulement ce qu'aucun
modèle ne peut dépasser.

Usage : python src/inspect_plafond.py [--raw-dir data/raw] [--day2-start 2015-02-18]
"""

import argparse
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from inspect_duplicates import (
    CAT_FIX, IDX_ATTACK_CAT, IDX_DSPORT, IDX_DSTIP, IDX_LTIME, IDX_SPORT,
    IDX_SRCIP, IDX_STIME, N_COLS, canon_class, digest, read_rows,
)

EXCLUDED = {IDX_SRCIP, IDX_SPORT, IDX_DSTIP, IDX_DSPORT, IDX_STIME, IDX_LTIME}
SIDES = {2: "jour 2 (entraînement)", 1: "jour 1 (test)"}


def analyse(table: dict, class_names: dict[int, str], normal_id: int, day: int) -> dict:
    """Agrège les groupes d'un côté et calcule effectifs et erreurs minimales.

    `table` : clé = empreinte (features) + 1 octet jour + 1 octet classe.
    """
    items = sorted((k, n) for k, n in table.items() if k[-2] == day)
    r = dict(rows=0, normal=0, attack=0, groups=0, bin_groups=0, bin_rows=0,
             bin_err=0, fp_maj=0, fn_maj=0, tie_groups=0, tie_err=0,
             mc_groups=0, mc_rows=0, mc_err=0, fn_by_class={})
    for _, grp in groupby(items, key=lambda kv: kv[0][:-1]):
        counts = {k[-1]: n for k, n in grp}
        n = sum(counts.values())
        n_norm = counts.get(normal_id, 0)
        n_att = n - n_norm
        r["rows"] += n
        r["normal"] += n_norm
        r["attack"] += n_att
        r["groups"] += 1
        if len(counts) > 1:
            r["mc_groups"] += 1
            r["mc_rows"] += n
            r["mc_err"] += n - max(counts.values())
        if n_norm and n_att:
            r["bin_groups"] += 1
            r["bin_rows"] += n
            r["bin_err"] += min(n_norm, n_att)
            if n_att > n_norm:
                r["fp_maj"] += n_norm
            elif n_norm > n_att:
                r["fn_maj"] += n_att
                for c, m in counts.items():
                    if c != normal_id:
                        name = class_names[c]
                        r["fn_by_class"][name] = r["fn_by_class"].get(name, 0) + m
            else:
                r["tie_groups"] += 1
                r["tie_err"] += n_norm
    return r


def report(title: str, res: dict) -> None:
    """Affiche les résultats d'un côté."""
    n = res["rows"]
    print(f"  {title}")
    print(f"    lignes : {n} (normal {res['normal']}, attaques {res['attack']})")
    print(f"    combinaisons de features distinctes : {res['groups']}")
    print(f"    combinaisons normal+attaque : {res['bin_groups']} "
          f"(lignes : {res['bin_rows']})")
    print(f"    erreurs binaires minimales : {res['bin_err']} "
          f"-> accuracy binaire maximale {100 * (1 - res['bin_err'] / n):.4f} %")
    print(f"      règle « classe majoritaire » : {res['fp_maj']} faux positifs, "
          f"{res['fn_maj']} faux négatifs, "
          f"{res['tie_groups']} groupes ex aequo ({res['tie_err']} erreurs)")
    if res["normal"]:
        print(f"      taux de faux positifs plancher : "
              f"{100 * res['fp_maj'] / res['normal']:.4f} % des normaux")
    if res["attack"]:
        print(f"      rappel plafond (attaques) : "
              f"{100 * (1 - res['fn_maj'] / res['attack']):.4f} % (hors ex aequo)")
    print(f"      attaques classées normal par la majorité, par famille : "
          f"{dict(sorted(res['fn_by_class'].items()))}")
    print(f"    combinaisons à plusieurs classes (familles comprises) : {res['mc_groups']} "
          f"(lignes : {res['mc_rows']})")
    print(f"    erreurs multiclasses minimales : {res['mc_err']} "
          f"-> accuracy multiclasse maximale {100 * (1 - res['mc_err'] / n):.4f} %")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--day2-start", default="2015-02-18",
                        help="Date UTC (AAAA-MM-JJ) à partir de laquelle commence le jour 2")
    args = parser.parse_args()
    day2_ts = datetime.strptime(args.day2_start, "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()

    class_ids: dict[str, int] = {}
    pre: dict[bytes, int] = {}
    post: dict[bytes, int] = {}
    seen: set[bytes] = set()
    removed: dict[tuple[int, int], int] = {}
    rows_by_side: dict[int, int] = {1: 0, 2: 0}

    for row in read_rows(args.raw_dir):
        if len(row) != N_COLS:
            raise SystemExit(f"ligne à {len(row)} champs")
        day = 2 if int(row[IDX_STIME]) >= day2_ts else 1
        cid = class_ids.setdefault(canon_class(row[IDX_ATTACK_CAT]), len(class_ids))
        rows_by_side[day] += 1
        key = digest([c for i, c in enumerate(row[:IDX_ATTACK_CAT]) if i not in EXCLUDED])
        key += bytes([day, cid])
        pre[key] = pre.get(key, 0) + 1
        k49 = digest(row)
        if k49 in seen:
            removed[(day, cid)] = removed.get((day, cid), 0) + 1
        else:
            seen.add(k49)
            post[key] = post.get(key, 0) + 1

    names = {i: c for c, i in class_ids.items()}
    normal_id = class_ids["(normal)"]

    print(f"Lignes lues (doublons de jonction écartés) : {sum(rows_by_side.values())}")
    print("\n1. Lignes supprimées par la déduplication exacte (49 colonnes), par côté")
    for day, label in SIDES.items():
        rm = {names[c]: n for (d, c), n in removed.items() if d == day}
        total_rm = sum(rm.values())
        print(f"  {label} : {rows_by_side[day]} lignes avant, {total_rm} supprimées, "
              f"{rows_by_side[day] - total_rm} après")
        print(f"    supprimées par classe : {dict(sorted(rm.items()))}")

    for name, table in (("AVANT déduplication", pre), ("APRÈS déduplication", post)):
        print(f"\n2. Plafond dû aux contradictions, 41 features, {name}")
        for day, label in SIDES.items():
            report(label, analyse(table, names, normal_id, day))


if __name__ == "__main__":
    main()
