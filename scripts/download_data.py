"""Fetch the raw inputs. Run from the project root.

    python scripts/download_data.py --seed ../go-station-scorecard/data/raw
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reverse.download import download_all  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=None, help="copy files from this data/raw folder first")
    args = parser.parse_args()
    download_all(args.seed.resolve() if args.seed else None)
