from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import RDLogger

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")


def write_split_files(frame: pd.DataFrame, split, work_dir: Path) -> dict[str, Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, idx in {"train": split.train, "valid": split.valid, "test": split.test}.items():
        table = frame.iloc[idx][["smiles", "y"]].copy()
        path = work_dir / f"{name}.csv"
        table.to_csv(path, index=False)
        smiles_path = work_dir / f"{name}_smiles.csv"
        table[["smiles"]].to_csv(smiles_path, index=False)
        paths[name] = path
        paths[f"{name}_smiles"] = smiles_path
    return paths


def chemprop_train_command(
    paths: dict[str, Path],
    run_dir: Path,
    task_type: str,
    variant: str,
    ensemble_size: int,
    epochs: int,
    batch_size: int,
) -> list[str]:
    metric = "rmse" if task_type == "regression" else "roc"
    task_arg = "regression" if task_type == "regression" else "classification"
    cmd = [
        "chemprop",
        "train",
        "-i",
        str(paths["train"]),
        str(paths["valid"]),
        str(paths["test"]),
        "-s",
        "smiles",
        "--target-columns",
        "y",
        "-t",
        task_arg,
        "--metrics",
        metric,
        "--tracking-metric",
        metric,
        "--ensemble-size",
        str(ensemble_size),
        "--epochs",
        str(epochs),
        "--warmup-epochs",
        str(1 if epochs > 1 else 0),
        "--patience",
        "6",
        "--batch-size",
        str(batch_size),
        "--num-workers",
        "0",
        "--accelerator",
        "cpu",
        "--devices",
        "1",
        "--message-hidden-dim",
        "128",
        "--depth",
        "3",
        "--ffn-hidden-dim",
        "128",
        "--ffn-num-layers",
        "2",
        "--output-dir",
        str(run_dir),
    ]
    if task_type == "classification":
        cmd.append("--class-balance")
    if variant == "rdkit":
        cmd.extend(["--molecule-featurizers", "rdkit_2d"])
    return cmd


def chemprop_predict_command(
    smiles_path: Path,
    pred_path: Path,
    run_dir: Path,
    variant: str,
    batch_size: int,
) -> list[str]:
    cmd = [
        "chemprop",
        "predict",
        "-i",
        str(smiles_path),
        "-o",
        str(pred_path),
        "-s",
        "smiles",
        "--model-paths",
        str(run_dir),
        "--batch-size",
        str(batch_size),
        "--num-workers",
        "0",
        "--accelerator",
        "cpu",
        "--devices",
        "1",
    ]
    if variant == "rdkit":
        cmd.extend(["--molecule-featurizers", "rdkit_2d"])
    return cmd


def run_command(cmd: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["RICH_FORCE_TERMINAL"] = "0"
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=handle, stderr=subprocess.STDOUT, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {proc.returncode}. See {log_path}")


def read_prediction(pred_path: Path) -> np.ndarray:
    table = pd.read_csv(pred_path)
    pred_cols = [col for col in table.columns if col.lower() not in {"smiles", "name", "drug", "drug_id"}]
    if not pred_cols:
        raise ValueError(f"No prediction column found in {pred_path}")
    return pd.to_numeric(table[pred_cols[-1]], errors="coerce").to_numpy(dtype=float)


def sanitize_prediction(pred: np.ndarray, fallback: float) -> tuple[np.ndarray, int]:
    clean = pred.astype(float, copy=True)
    mask = ~np.isfinite(clean)
    count = int(mask.sum())
    if count:
        clean[mask] = fallback
    return clean, count


def summarize(metrics: pd.DataFrame, output_dir: Path) -> None:
    metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {"dataset", "model", "task_type", "seed", "split"}
    metric_cols = [
        col for col in metrics.columns if col not in id_cols and pd.api.types.is_numeric_dtype(metrics[col])
    ]
    summary = (
        metrics.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official Chemprop D-MPNN baselines.")
    parser.add_argument("--datasets", nargs="*", default=["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--variants", nargs="*", default=["dmpnn", "rdkit"], choices=["dmpnn", "rdkit"])
    parser.add_argument("--ensemble-size", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "chemprop_baseline"))
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    work_root = output_dir / "_chemprop_work"
    rows: list[dict] = []
    imputation_rows: list[dict] = []

    for dataset in args.datasets:
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        for seed in args.seeds:
            split = make_split(frame, "scaffold", seed)
            split_paths = write_split_files(frame, split, work_root / dataset / f"seed{seed}" / "splits")
            y_valid = frame.iloc[split.valid]["y"].to_numpy()
            y_test = frame.iloc[split.test]["y"].to_numpy()
            y_train = frame.iloc[split.train]["y"].to_numpy()
            fallback = float(np.nanmean(y_train))
            if spec.task_type == "classification":
                fallback = float(np.clip(fallback, 1e-6, 1 - 1e-6))
            valid_smiles = frame.iloc[split.valid]["smiles"].to_numpy()
            test_smiles = frame.iloc[split.test]["smiles"].to_numpy()
            for variant in args.variants:
                model_name = f"chemprop_{variant}_ens{args.ensemble_size}"
                run_dir = work_root / dataset / f"seed{seed}" / variant / "train"
                pred_path = output_dir / f"{dataset}_{model_name}_seed{seed}_predictions.csv"
                valid_path = output_dir / f"{dataset}_{model_name}_seed{seed}_valid_predictions.csv"
                if not (args.resume and pred_path.exists() and valid_path.exists()):
                    if not (args.resume and run_dir.exists() and list(run_dir.rglob("*.pt"))):
                        train_cmd = chemprop_train_command(
                            split_paths,
                            run_dir,
                            spec.task_type,
                            variant,
                            args.ensemble_size,
                            args.epochs,
                            args.batch_size,
                        )
                        run_command(train_cmd, run_dir / "train.log")
                    raw_valid_pred = work_root / dataset / f"seed{seed}" / variant / "valid_raw_predictions.csv"
                    raw_test_pred = work_root / dataset / f"seed{seed}" / variant / "test_raw_predictions.csv"
                    run_command(
                        chemprop_predict_command(
                            split_paths["valid_smiles"],
                            raw_valid_pred,
                            run_dir,
                            variant,
                            args.batch_size,
                        ),
                        run_dir / "predict_valid.log",
                    )
                    run_command(
                        chemprop_predict_command(
                            split_paths["test_smiles"],
                            raw_test_pred,
                            run_dir,
                            variant,
                            args.batch_size,
                        ),
                        run_dir / "predict_test.log",
                    )
                    valid_pred = read_prediction(raw_valid_pred)
                    test_pred = read_prediction(raw_test_pred)
                    valid_pred, valid_imputed = sanitize_prediction(valid_pred, fallback)
                    test_pred, test_imputed = sanitize_prediction(test_pred, fallback)
                    pd.DataFrame(
                        {"smiles": valid_smiles, "y_true": y_valid, "y_pred": valid_pred}
                    ).to_csv(valid_path, index=False)
                    pd.DataFrame(
                        {"smiles": test_smiles, "y_true": y_test, "y_pred": test_pred}
                    ).to_csv(pred_path, index=False)
                    for split_name, count in {"valid": valid_imputed, "test": test_imputed}.items():
                        if count:
                            imputation_rows.append(
                                {
                                    "dataset": dataset,
                                    "model": model_name,
                                    "seed": seed,
                                    "split": split_name,
                                    "fallback": fallback,
                                    "n_imputed": count,
                                }
                            )
                else:
                    for path, split_name in [(valid_path, "valid"), (pred_path, "test")]:
                        table = pd.read_csv(path)
                        pred, count = sanitize_prediction(pd.to_numeric(table["y_pred"], errors="coerce").to_numpy(), fallback)
                        if count:
                            table["y_pred"] = pred
                            table.to_csv(path, index=False)
                            imputation_rows.append(
                                {
                                    "dataset": dataset,
                                    "model": model_name,
                                    "seed": seed,
                                    "split": split_name,
                                    "fallback": fallback,
                                    "n_imputed": count,
                                }
                            )
                pred_frame = pd.read_csv(pred_path)
                rows.append(
                    {
                        "dataset": dataset,
                        "model": model_name,
                        "seed": seed,
                        "split": "scaffold",
                        "task_type": spec.task_type,
                        **compute_metrics(
                            spec.task_type,
                            pred_frame["y_true"].to_numpy(),
                            pred_frame["y_pred"].to_numpy(),
                        ),
                    }
                )
                summarize(pd.DataFrame(rows), output_dir)
                if imputation_rows:
                    pd.DataFrame(imputation_rows).drop_duplicates().to_csv(
                        output_dir / "nan_imputation_log.csv", index=False
                    )

    metrics = pd.DataFrame(rows)
    summarize(metrics, output_dir)
    if imputation_rows:
        pd.DataFrame(imputation_rows).drop_duplicates().to_csv(output_dir / "nan_imputation_log.csv", index=False)
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
