from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.train import run_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume one strict-core experiment cell.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    args = parser.parse_args()

    config = {
        "datasets": [args.dataset],
        "models": [args.model],
        "split": "scaffold",
        "seeds": [args.seed],
        "epochs": 60,
        "batch_size": 64,
        "hidden_dim": 192,
        "layers": 5,
        "lr": 0.001,
        "weight_decay": 0.00001,
        "contrastive_weight": 0.1,
        "patience": 12,
        "max_rows": None,
        "num_workers": 0,
        "resume": True,
        "cache_graphs": True,
        "output_dir": str(ROOT / "reports" / "strict_core"),
    }
    metrics = run_config(config, data_dir=args.data_dir)
    done = metrics[
        (metrics["dataset"].astype(str) == args.dataset)
        & (metrics["model"].astype(str) == args.model)
        & (metrics["seed"].astype(int) == args.seed)
    ]
    if done.empty:
        raise SystemExit(f"Run did not produce row for {args.dataset}/{args.model}/seed{args.seed}")
    row = done.tail(1).iloc[0]
    primary = "rmse" if row["task_type"] == "regression" else "roc_auc"
    print(
        f"single_complete dataset={args.dataset} model={args.model} seed={args.seed} "
        f"{primary}={row.get(primary)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
