# Changed: provide a safe placeholder runner for W&B configuration experiments.
# Why: W&B can be used later without changing the submission solver or mixing data splits.

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-data", default="/dl2026/dataset")
    args = parser.parse_args()
    print(
        "Optional sweep hook only. "
        f"Use public train/dev data from {args.public_data}; do not use leaderboard/test labels."
    )


if __name__ == "__main__":
    main()
