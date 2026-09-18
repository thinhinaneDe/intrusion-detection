"""Autoencodeur sur le jeu non supervisé : erreur de reconstruction comme score d'anomalie.

Entraînement sur les seuls flux normaux du jour 2 (jeu `unsup`), jamais sur une
attaque. Perceptron symétrique, ReLU, perte MSE sans écrêtage, Adam, nombre
d'epochs fixe, identique pour les blocs de calibration et le modèle final.

Deux architectures déclarées d'avance (M19), rapportées sur le même pied :
« moyen » (principale) et « petit ». Aucun choix entre elles après lecture des
résultats. Le score d'un flux est l'erreur quadratique moyenne de reconstruction
sur les colonnes préparées (plus grand = plus suspect). Le seuil est calibré sur
des scores hors échantillon, en blocs de temps contigus (voir `calibration.py`),
comme pour l'Isolation Forest.

Usage : python src/models/autoencoder.py [--config config.toml] [--arch moyen petit]
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Exécuté depuis src/models/ ou importé depuis src/ (banc de mesure) : on ajoute
# src/ (prepare, evaluate) et src/models/ (calibration) au chemin d'import.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import torch
from torch import nn

from calibration import out_of_fold_scores, report_and_save
from prepare import load_config, load_set


def build(d_in: int, dims: list[int]) -> nn.Sequential:
    """Autoencodeur symétrique : d_in -> dims -> ... -> dims[-1] (goulot) -> ... -> d_in."""
    sizes = [d_in, *dims]
    layers: list[nn.Module] = []
    for a, b in zip(sizes[:-1], sizes[1:]):
        layers += [nn.Linear(a, b), nn.ReLU()]
    rev = sizes[::-1]
    for i, (a, b) in enumerate(zip(rev[:-1], rev[1:])):
        layers.append(nn.Linear(a, b))
        if i < len(rev) - 2:
            layers.append(nn.ReLU())
    return nn.Sequential(*layers)


def train_epoch(model, opt, x: torch.Tensor, batch: int, gen: torch.Generator) -> float:
    """Une epoch (ordre mélangé) ; retourne la perte MSE moyenne."""
    perm = torch.randperm(len(x), generator=gen)
    total = 0.0
    for i in range(0, len(x), batch):
        xb = x[perm[i:i + batch]]
        loss = ((model(xb) - xb) ** 2).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        total += loss.item() * len(xb)
    return total / len(x)


@torch.no_grad()
def row_errors(model, x: torch.Tensor, chunk: int = 65536) -> np.ndarray:
    """Erreur de reconstruction (MSE moyen sur les colonnes) de chaque ligne."""
    return np.concatenate([((model(x[i:i + chunk]) - x[i:i + chunk]) ** 2).mean(1).numpy()
                           for i in range(0, len(x), chunk)])


def fit(x_fit: np.ndarray, dims: list[int], acfg: dict) -> tuple[nn.Sequential, list[float]]:
    """Entraîne un autoencodeur sur `x_fit` ; retourne le modèle et la perte de chaque epoch."""
    torch.manual_seed(acfg["seed"])
    x = torch.from_numpy(x_fit)
    model = build(x.shape[1], dims)
    opt = torch.optim.Adam(model.parameters(), lr=acfg["learning_rate"])
    gen = torch.Generator().manual_seed(acfg["seed"])
    losses = [train_epoch(model, opt, x, acfg["batch_size"], gen) for _ in range(acfg["epochs"])]
    return model, losses


def run(arch: str, dims: list[int], cfg: dict, out: Path, train_raw: pd.DataFrame,
        feature_cols: list[str]) -> dict:
    """Calibration hors échantillon, modèle final, évaluation et rapport d'une architecture."""
    acfg = cfg["autoencoder"]
    t0 = time.time()
    print(f"\n{'=' * 78}\nAutoencodeur « {arch} » {dims} : {acfg['epochs']} epochs, lot "
          f"{acfg['batch_size']}, {acfg['cv_folds']} blocs de temps\n{'=' * 78}", flush=True)

    def fit_score(x_fit: np.ndarray, x_held: np.ndarray) -> np.ndarray:
        model, losses = fit(x_fit, dims, acfg)
        print(f"    perte d'entraînement, dernière epoch : {losses[-1]:.5f}", flush=True)
        return row_errors(model, torch.from_numpy(x_held))

    oof = out_of_fold_scores(train_raw, feature_cols, cfg, acfg["cv_folds"], fit_score)
    print(f"Scores hors échantillon calculés ({time.time() - t0:.0f} s)", flush=True)

    x_train, _, _, x_test, _, _ = load_set("unsup", out)
    model, losses = fit(x_train, dims, acfg)
    print("Modèle final, perte d'entraînement par epoch : " + ", ".join(
        f"{e}: {losses[e - 1]:.5f}" for e in sorted({1, 5, 10, 15, 20, 25, len(losses)})
        if e <= len(losses)), flush=True)
    s_train = row_errors(model, torch.from_numpy(x_train))
    s_test = row_errors(model, torch.from_numpy(x_test))
    print(f"Modèle final entraîné et test noté ({time.time() - t0:.0f} s)", flush=True)

    print(f"\nErreur de reconstruction des normaux d'entraînement hors échantillon : moyenne "
          f"{oof.mean():.5f}, médiane {np.median(oof):.5f}, quantile 99 % {np.quantile(oof, 0.99):.5f}")
    res = report_and_save(
        f"autoencoder_{arch}", cfg, {**acfg, "architecture": dims}, oof, s_train, s_test, out,
        extra={"oof_error": {"mean": float(oof.mean()), "median": float(np.median(oof)),
                             "q99": float(np.quantile(oof, 0.99))},
               "final_train_loss": losses[-1], "seconds": time.time() - t0})
    print(f"({time.time() - t0:.0f} s au total pour « {arch} »)")
    return res


def print_comparison(cfg: dict, out: Path) -> None:
    """Compare sur le même pied les architectures dont les résultats sont écrits, et l'Isolation Forest."""
    rows = {}
    ref = out / "results" / "isolation_forest.json"
    if ref.exists():
        rows["isolation_forest (référence)"] = json.loads(ref.read_text())
    for arch in cfg["autoencoder"]["architectures"]:
        path = out / "results" / f"autoencoder_{arch}.json"
        if path.exists():
            rows[f"autoencodeur {arch}"] = json.loads(path.read_text())
    budgets = cfg["evaluation"]["fpr_budgets"]
    print(f"\n{'=' * 78}\nComparaison sur le même pied (rappel au seuil calibré / lu au même taux "
          f"sur le test)\n{'=' * 78}")
    print(f"{'modèle':30s} {'AUC-PR':>7s}  " + "   ".join(f"budget {100 * b:g} %" for b in budgets))
    for name, p in rows.items():
        ev = p["evaluation"]
        cells = "   ".join(f"{100 * v['recall']:5.2f} / {100 * v['matched']['recall']:5.2f}   "
                           for v in ev["budgets"].values())
        print(f"{name:30s} {ev['average_precision']:7.4f}  {cells}")
    print("\nTaux de faux positifs observé sur le test (visé : " + ", ".join(
        f"{100 * b:g} %" for b in budgets) + ") :")
    for name, p in rows.items():
        print(f"  {name:30s} " + ", ".join(
            f"{100 * v['fpr_test']:.4f} %" for v in p["evaluation"]["budgets"].values()))
    print("\nErreur de reconstruction des normaux hors échantillon (moyenne, médiane, quantile 99 %) :")
    for name, p in rows.items():
        if "oof_error" in p:
            e = p["oof_error"]
            print(f"  {name:30s} {e['mean']:.5f}, {e['median']:.5f}, {e['q99']:.5f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--arch", nargs="+", default=None,
                        help="Architectures à exécuter (défaut : toutes celles de la configuration)")
    parser.add_argument("--compare-only", action="store_true",
                        help="N'entraîne rien : compare les résultats déjà écrits")
    args = parser.parse_args()
    cfg = load_config(args.config)
    acfg = cfg["autoencoder"]
    torch.set_num_threads(acfg["threads"])
    out = Path(cfg["data"]["processed_dir"])
    if args.compare_only:
        print_comparison(cfg, out)
        return
    feature_cols = json.loads((out / "manifest.json").read_text())["feature_columns"]
    archs = args.arch or list(acfg["architectures"])

    train_raw = pd.read_parquet(out / "train_unsup.parquet")
    if not train_raw["Stime"].is_monotonic_increasing:
        raise SystemExit("train_unsup n'est pas trié par Stime : les blocs ne seraient pas contigus")
    print(f"Jeu unsup : {len(train_raw)} normaux ; {torch.get_num_threads()} threads")
    for a in archs:
        run(a, acfg["architectures"][a], cfg, out, train_raw, feature_cols)

    print_comparison(cfg, out)


if __name__ == "__main__":
    main()
