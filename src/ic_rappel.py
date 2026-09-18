"""Effectifs par famille après déduplication et intervalle de confiance d'un rappel.

Chaîne identique à M08 : découpage temporel (jour 2 = entraînement, jour 1 =
test), puis déduplication exacte sur 49 colonnes, côté par côté. Sur les
effectifs mesurés, calcule l'intervalle de confiance à 95 % d'un rappel
HYPOTHÉTIQUE (`--recall`, hypothèse de travail, pas une performance mesurée) :

  - Wilson (avec p exactement égal au rappel hypothétique) ;
  - Clopper-Pearson exact, avec k = round(recall * n) succès.

Les deux supposent des lignes indépendantes, ce qui est optimiste : des flux
issus d'un même balayage ou d'une même rafale ne le sont pas.

Usage : python src/ic_rappel.py [--raw-dir data/raw] [--day2-start 2015-02-18]
                                [--recall 0.80] [--alpha 0.05]
"""

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

from evaluate import wilson
from inspect_duplicates import IDX_ATTACK_CAT, IDX_STIME, N_COLS, canon_class, digest, read_rows

SIDES = {2: "jour 2 (entraînement)", 1: "jour 1 (test)"}


def _log_pmf(k: int, n: int, p: float) -> float:
    """Log de la loi binomiale P(X=k), stable pour n de l'ordre de 10^4."""
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def _cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) pour X ~ Binomiale(n, p)."""
    return sum(math.exp(_log_pmf(i, n, p)) for i in range(k + 1))


def clopper_pearson(k: int, n: int, alpha: float) -> tuple[float, float]:
    """Intervalle exact de Clopper-Pearson, par dichotomie sur la fonction de répartition."""
    # P(X >= k | p) croît avec p ; P(X <= k | p) décroît avec p.
    lower = 0.0 if k == 0 else _solve_increasing(lambda p: 1 - _cdf(k - 1, n, p), alpha / 2)
    upper = 1.0 if k == n else _solve_decreasing(lambda p: _cdf(k, n, p), alpha / 2)
    return lower, upper


def _solve_increasing(f, target: float) -> float:
    """Racine de f(p) = target pour f croissante sur [0, 1]."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _solve_decreasing(f, target: float) -> float:
    """Racine de f(p) = target pour f décroissante sur [0, 1]."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--day2-start", default="2015-02-18",
                        help="Date UTC (AAAA-MM-JJ) à partir de laquelle commence le jour 2")
    parser.add_argument("--recall", type=float, default=0.80,
                        help="Rappel hypothétique (hypothèse de travail, non mesurée)")
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()
    day2_ts = datetime.strptime(args.day2_start, "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()

    seen: set[bytes] = set()
    before: dict[tuple[int, str], int] = {}
    after: dict[tuple[int, str], int] = {}
    for row in read_rows(args.raw_dir):
        if len(row) != N_COLS:
            raise SystemExit(f"ligne à {len(row)} champs")
        day = 2 if int(row[IDX_STIME]) >= day2_ts else 1
        cls = canon_class(row[IDX_ATTACK_CAT])
        before[(day, cls)] = before.get((day, cls), 0) + 1
        k49 = digest(row)
        if k49 not in seen:
            seen.add(k49)
            after[(day, cls)] = after.get((day, cls), 0) + 1

    print("Taux de copies exactes (49 colonnes) par famille et par côté :")
    for day, label in SIDES.items():
        print(f"  {label}")
        for cls in sorted({c for d, c in before if d == day}):
            b, a = before[(day, cls)], after.get((day, cls), 0)
            print(f"    {cls:15s} avant {b:8d}  après {a:8d}  copies {b - a:8d}"
                  f"  ({100 * (b - a) / b:5.1f} %)")

    print(f"\nIntervalle de confiance à {100 * (1 - args.alpha):.0f} % d'un rappel "
          f"hypothétique de {args.recall:.2f}, effectifs mesurés du test (jour 1, "
          "après déduplication) :")
    fams = sorted((n, c) for (d, c), n in after.items() if d == 1 and c != "(normal)")
    for n, cls in fams:
        lo, hi = wilson(args.recall, n, args.alpha)
        k = round(args.recall * n)
        clo, chi = clopper_pearson(k, n, args.alpha)
        print(f"  {cls:15s} n={n:5d}  Wilson [{lo:.3f} ; {hi:.3f}] "
              f"(demi-largeur {100 * (hi - lo) / 2:4.1f} pts)  "
              f"exact k={k} [{clo:.3f} ; {chi:.3f}]")


if __name__ == "__main__":
    main()
