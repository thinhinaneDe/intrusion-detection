"""Vérification de présence et d'intégrité des fichiers bruts UNSW-NB15.

Ce script ne télécharge rien : la page officielle du jeu renvoie vers un partage
SharePoint qui exige un navigateur (pas d'URL de fichier stable à appeler depuis un
script). Les fichiers sont donc récupérés à la main, puis ce script vérifie que
chacun est présent dans `raw_dir` et que son empreinte SHA-256 est celle des
fichiers qui ont produit toutes les mesures du journal (`[download.sha256]` de la
configuration).

Code de sortie : 0 si les six fichiers sont présents et intègres, 1 sinon.

Usage : python src/download.py [--config config.toml]
"""

import argparse
import hashlib
import sys
from pathlib import Path

from prepare import load_config

CHUNK = 1 << 20


def sha256(path: Path) -> str:
    """Empreinte SHA-256 d'un fichier, lu par blocs de 1 Mo (les CSV pèsent jusqu'à 170 Mo)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def check(raw_dir: Path, expected: dict[str, str]) -> tuple[list[str], list[str]]:
    """Vérifie chaque fichier attendu ; renvoie (noms manquants, noms à l'empreinte différente)."""
    missing, corrupt = [], []
    for name, digest in expected.items():
        path = raw_dir / name
        if not path.is_file():
            print(f"  ABSENT    {name}")
            missing.append(name)
        elif (got := sha256(path)) != digest:
            print(f"  DIFFÉRENT {name}\n            attendu {digest}\n            obtenu  {got}")
            corrupt.append(name)
        else:
            print(f"  OK        {name}")
    return missing, corrupt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    raw_dir = Path(cfg["data"]["raw_dir"])
    expected = cfg["download"]["sha256"]

    print(f"Vérification de {len(expected)} fichiers dans {raw_dir}/")
    missing, corrupt = check(raw_dir, expected)
    if not missing and not corrupt:
        print("Tous les fichiers sont présents et intègres.")
        return

    print()
    if missing:
        print(f"{len(missing)} fichier(s) manquant(s). Le téléchargement est manuel : le lien de la page "
              "officielle mène à un partage SharePoint qui exige un navigateur.")
        print(f"  1. Ouvrir {cfg['download']['page']}")
        print("  2. Suivre le lien de téléchargement du jeu, puis récupérer les fichiers CSV :")
        for name in expected:
            print(f"       {name}{'   <- manquant' if name in missing else ''}")
        print(f"  3. Les placer, sans les renommer, dans {raw_dir}/")
    if corrupt:
        print(f"{len(corrupt)} fichier(s) dont le contenu diffère de celui qui a produit les mesures du journal : "
              "téléchargement incomplet ou version différente. Les retélécharger depuis la page officielle.")
    sys.exit(1)


if __name__ == "__main__":
    main()
