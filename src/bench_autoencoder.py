"""Coût d'un autoencodeur sur cette machine (CPU, 8 Go de RAM) : mesure de temps.

Ne cherche pas la meilleure architecture et ne touche à aucune attaque ni au
test. Mesure, sur les normaux du jour 2 (jeu `unsup`, préprocesseur `unsup`) :

  1. le temps d'une epoch sur 80 % des normaux (la taille d'entraînement d'un
     bloc de la calibration en 5 blocs, M16) pour chaque architecture et taille
     de lot ;
  2. le temps de notation de tous les normaux ;
  3. l'ACP de référence : erreur de reconstruction du même bloc de validation par
     l'analyse en composantes principales (l'autoencodeur linéaire équivalent),
     qui indique aussi combien de composantes portent la variance des normaux ;
  4. une courbe de convergence courte : perte d'entraînement et de validation
     par epoch, la validation étant le dernier bloc de temps (20 %). Le
     préprocesseur `unsup` a vu ce bloc ; la fuite ne concerne que le scaler et
     sert un banc de vitesse, pas la calibration finale.

Autoencodeur : perceptron symétrique, ReLU, perte MSE moyenne par ligne, Adam.

Usage : python src/bench_autoencoder.py [--config config.toml]
"""

import argparse
import json
import resource
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from models.autoencoder import build, row_errors, train_epoch
from prepare import load_config

ARCHS = {"petit": [32, 16, 8], "moyen": [128, 64, 16], "large": [256, 128, 32]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--archs", nargs="*", default=list(ARCHS), choices=list(ARCHS),
                        help="Architectures dont on mesure le temps d'une epoch")
    parser.add_argument("--threads", type=int, default=None,
                        help="Nombre de threads de PyTorch (défaut de la bibliothèque si absent)")
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[256, 1024, 4096])
    parser.add_argument("--curve-archs", nargs="*", default=["petit", "moyen"], choices=list(ARCHS))
    parser.add_argument("--pca-components", type=int, nargs="*", default=[8, 16, 32],
                        help="Nombres de composantes de l'ACP de référence (modèle linéaire équivalent)")
    parser.add_argument("--curve-batch", type=int, default=1024)
    parser.add_argument("--curve-epochs", type=int, default=15)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.threads:
        torch.set_num_threads(args.threads)
    out = Path(cfg["data"]["processed_dir"])
    cols = json.loads((out / "manifest.json").read_text())["feature_columns"]

    train = pd.read_parquet(out / "train_unsup.parquet")
    pre = joblib.load(out / "preprocessor_unsup.joblib")
    x = torch.from_numpy(pre.transform(train[cols]).astype(np.float32))
    del train
    n, d = x.shape
    n_fit = int(0.8 * n)
    x_fit, x_val = x[:n_fit], x[n_fit:]
    print(f"torch {torch.__version__}, {torch.get_num_threads()} threads, CPU ; "
          f"X : {n} lignes x {d} colonnes ; entraînement de bloc : {n_fit} lignes")

    print("\n1. Temps d'une epoch sur 80 % des normaux, et de la notation de tous les normaux")
    for name in args.archs:
        dims = ARCHS[name]
        for batch in args.batch_sizes:
            torch.manual_seed(args.seed)
            model = build(d, dims)
            n_par = sum(p.numel() for p in model.parameters())
            opt = torch.optim.Adam(model.parameters(), lr=args.lr)
            t = time.perf_counter()
            loss = train_epoch(model, opt, x_fit, batch, torch.Generator().manual_seed(args.seed))
            t_epoch = time.perf_counter() - t
            t = time.perf_counter()
            row_errors(model, x)
            t_score = time.perf_counter() - t
            print(f"  {name:6s} {dims} ({n_par} paramètres), lot {batch:5d} : "
                  f"{t_epoch:6.2f} s par epoch, {(n_fit + batch - 1) // batch} pas ; "
                  f"notation de {n} lignes : {t_score:.2f} s ; perte après 1 epoch {loss:.4f}")

    print(f"\n2. Convergence (lot {args.curve_batch}, Adam, lr {args.lr}) : perte d'entraînement, "
          "erreur de validation (moyenne, médiane, quantile 99 % des lignes du dernier bloc de temps)")
    for name in args.curve_archs:
        torch.manual_seed(args.seed)
        model = build(d, ARCHS[name])
        opt = torch.optim.Adam(model.parameters(), lr=args.lr)
        gen = torch.Generator().manual_seed(args.seed)
        print(f"  {name} {ARCHS[name]}")
        t0 = time.perf_counter()
        for epoch in range(1, args.curve_epochs + 1):
            loss = train_epoch(model, opt, x_fit, args.curve_batch, gen)
            e = row_errors(model, x_val)
            print(f"    epoch {epoch:2d} ({time.perf_counter() - t0:6.1f} s) : entraînement "
                  f"{loss:.4f} ; validation moyenne {e.mean():.4f}, médiane {np.median(e):.5f}, "
                  f"q99 {np.quantile(e, 0.99):.4f}", flush=True)

    print("\n3. ACP de référence, ajustée sur 80 % des normaux (mêmes lignes que l'entraînement "
          "d'un bloc), erreur de reconstruction du dernier bloc de temps")
    if args.pca_components:
        from sklearn.decomposition import PCA
        xf, xv = x_fit.numpy(), x_val.numpy()
        full = PCA(svd_solver="covariance_eigh").fit(xf)
        cum = np.cumsum(full.explained_variance_ratio_)
        print("  variance expliquée cumulée : " + ", ".join(
            f"{k} composantes {100 * cum[k - 1]:.2f} %" for k in (4, 8, 12, 16, 24, 32, 48) if k <= d))
        for k in args.pca_components:
            pca = PCA(n_components=k, svd_solver="covariance_eigh").fit(xf)
            e = ((pca.inverse_transform(pca.transform(xv)) - xv) ** 2).mean(1)
            print(f"  ACP {k:2d} composantes : validation moyenne {e.mean():.4f}, médiane "
                  f"{np.median(e):.5f}, q99 {np.quantile(e, 0.99):.4f}")

    print(f"\nPic de mémoire du processus : {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} Mo")


if __name__ == "__main__":
    main()
