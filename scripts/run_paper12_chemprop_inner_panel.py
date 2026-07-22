from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, mean_squared_error, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_shared_split_multiview_nested_20260624 as shared

OUT = ROOT / "output" / "小论文-12_严格补实验"
WORK = OUT / "_chemprop_inner_work"
CHEMPROP = Path(os.environ.get("CHEMPROP_EXECUTABLE", "chemprop"))
TASKS = ["esol", "bace", "clintox"]
SEEDS = [11, 23, 37, 53, 71]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=TASKS)
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--outer-folds", type=int, default=3)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def write_split(frame: pd.DataFrame, idx: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.iloc[idx][["smiles", "y"]].to_csv(path, index=False)


def train_cmd(train: Path, valid: Path, test: Path, run_dir: Path, task_type: str, args: argparse.Namespace) -> list[str]:
    metric = "rmse" if task_type == "regression" else "roc"
    cmd = [
        str(CHEMPROP),
        "train",
        "-i",
        str(train),
        str(valid),
        str(test),
        "-s",
        "smiles",
        "--target-columns",
        "y",
        "-t",
        task_type,
        "--metrics",
        metric,
        "--tracking-metric",
        metric,
        "--ensemble-size",
        "1",
        "--epochs",
        str(args.epochs),
        "--warmup-epochs",
        "0",
        "--patience",
        "2",
        "--batch-size",
        str(args.batch_size),
        "--num-workers",
        "0",
        "--accelerator",
        "cpu",
        "--devices",
        "1",
        "--message-hidden-dim",
        "64",
        "--depth",
        "3",
        "--ffn-hidden-dim",
        "64",
        "--ffn-num-layers",
        "2",
        "--output-dir",
        str(run_dir),
    ]
    if task_type == "classification":
        cmd.append("--class-balance")
    return cmd


def predict_cmd(input_csv: Path, out_csv: Path, run_dir: Path, args: argparse.Namespace) -> list[str]:
    smiles_only = input_csv.with_name(input_csv.stem + "_smiles.csv")
    pd.read_csv(input_csv)[["smiles"]].to_csv(smiles_only, index=False)
    return [
        str(CHEMPROP),
        "predict",
        "-i",
        str(smiles_only),
        "-o",
        str(out_csv),
        "-s",
        "smiles",
        "--model-paths",
        str(run_dir),
        "--batch-size",
        str(args.batch_size),
        "--num-workers",
        "0",
        "--accelerator",
        "cpu",
        "--devices",
        "1",
    ]


def run(cmd: list[str], log: Path) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"failed {proc.returncode}; see {log}")


def read_pred(path: Path) -> np.ndarray:
    df = pd.read_csv(path)
    cols = [c for c in df.columns if c.lower() not in {"smiles", "name"}]
    return pd.to_numeric(df[cols[-1]], errors="coerce").to_numpy(float)


def score(task_type: str, y: np.ndarray, pred: np.ndarray) -> tuple[float, dict[str, float]]:
    if np.any(~np.isfinite(pred)):
        pred = pred.copy()
        pred[~np.isfinite(pred)] = float(np.nanmean(pred[np.isfinite(pred)])) if np.any(np.isfinite(pred)) else 0.0
    if task_type == "classification":
        roc = float(roc_auc_score(y, pred)) if len(np.unique(y)) == 2 else np.nan
        pr = float(average_precision_score(y, pred)) if len(np.unique(y)) == 2 else np.nan
        return roc, {"roc_auc": roc, "pr_auc": pr, "rmse": np.nan}
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    return -rmse, {"roc_auc": np.nan, "pr_auc": np.nan, "rmse": rmse}


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not CHEMPROP.exists():
        raise SystemExit(f"missing {CHEMPROP}")
    registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    rows = []
    pred_rows = []
    for task in args.tasks:
        frame, task_type = shared.load_task(task, registry)
        _, groups, keep = shared.featurize(frame["smiles"])
        frame = frame.loc[keep].reset_index(drop=True)
        y = frame["y"].to_numpy()
        for seed in args.seeds:
            outer_splits, outer_split_type = shared.make_splits(y, groups, task_type, args.outer_folds, seed)
            for outer_fold, (outer_train, _) in enumerate(outer_splits, start=1):
                inner_splits, inner_split_type = shared.make_splits(
                    y[outer_train], groups[outer_train], task_type, args.inner_folds, seed + outer_fold
                )
                for inner_fold, (train_local, valid_local) in enumerate(inner_splits, start=1):
                    train_idx = outer_train[train_local]
                    valid_idx = outer_train[valid_local]
                    run_dir = WORK / task / f"seed_{seed}" / f"outer_{outer_fold}" / f"inner_{inner_fold}" / "train"
                    pred_csv = OUT / f"chemprop_{task}_seed{seed}_outer{outer_fold}_inner{inner_fold}_valid_predictions.csv"
                    start = time.perf_counter()
                    if not (pred_csv.exists() and not args.force):
                        split_dir = WORK / task / f"seed_{seed}" / f"outer_{outer_fold}" / f"inner_{inner_fold}" / "splits"
                        train_csv = split_dir / "train.csv"
                        valid_csv = split_dir / "valid.csv"
                        write_split(frame, train_idx, train_csv)
                        write_split(frame, valid_idx, valid_csv)
                        run(train_cmd(train_csv, valid_csv, valid_csv, run_dir, task_type, args), run_dir / "train.log")
                        raw_pred = WORK / task / f"seed_{seed}" / f"outer_{outer_fold}" / f"inner_{inner_fold}" / "raw_valid_predictions.csv"
                        run(predict_cmd(valid_csv, raw_pred, run_dir, args), run_dir / "predict.log")
                        pred = read_pred(raw_pred)
                        pd.DataFrame(
                            {
                                "task": task,
                                "task_type": task_type,
                                "seed": seed,
                                "outer_fold": outer_fold,
                                "inner_fold": inner_fold,
                                "sample_index": valid_idx,
                                "smiles": frame.iloc[valid_idx]["smiles"].to_numpy(),
                                "y_true": y[valid_idx],
                                "candidate": "chemprop_dmpnn",
                                "family": "chemprop_dmpnn",
                                "y_pred": pred,
                            }
                        ).to_csv(pred_csv, index=False)
                    pred_table = pd.read_csv(pred_csv)
                    pred = pd.to_numeric(pred_table["y_pred"], errors="coerce").to_numpy(float)
                    utility, metric_cols = score(task_type, y[valid_idx], pred)
                    elapsed = time.perf_counter() - start
                    rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "seed": seed,
                            "outer_fold": outer_fold,
                            "inner_fold": inner_fold,
                            "outer_split_type": outer_split_type,
                            "inner_split_type": inner_split_type,
                            "candidate": "chemprop_dmpnn",
                            "family": "chemprop_dmpnn",
                            "inner_utility": utility,
                            "fit_predict_seconds": elapsed,
                            **metric_cols,
                        }
                    )
                    pred_rows.append(pred_table)
                    print(f"chemprop-inner {task} seed={seed} outer={outer_fold}/{args.outer_folds} inner={inner_fold}/{args.inner_folds}", flush=True)
    inner = pd.DataFrame(rows)
    inner.to_csv(OUT / "chemprop_inner_scores.csv", index=False)
    pd.concat(pred_rows, ignore_index=True).to_csv(OUT / "chemprop_inner_predictions.csv", index=False)
    summary = inner.groupby(["task", "task_type", "candidate"], as_index=False).agg(
        n_inner_units=("inner_utility", "size"),
        inner_utility_mean=("inner_utility", "mean"),
        roc_auc_mean=("roc_auc", "mean"),
        pr_auc_mean=("pr_auc", "mean"),
        rmse_mean=("rmse", "mean"),
    )
    summary.to_csv(OUT / "chemprop_inner_summary.csv", index=False)
    audit = {
        "tasks": args.tasks,
        "seeds": args.seeds,
        "outer_folds": args.outer_folds,
        "inner_folds": args.inner_folds,
        "epochs": args.epochs,
        "inner_rows": int(len(inner)),
        "prediction_rows": int(sum(len(x) for x in pred_rows)),
        "passed": len(inner) == len(args.tasks) * len(args.seeds) * args.outer_folds * args.inner_folds,
    }
    (OUT / "chemprop_inner_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not audit["passed"]:
        raise SystemExit(json.dumps(audit, ensure_ascii=False, indent=2))
    print(OUT / "chemprop_inner_summary.csv")


if __name__ == "__main__":
    main()
