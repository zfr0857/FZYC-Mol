from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import canonicalize_smiles


RDLogger.DisableLog("rdApp.*")

OUT_DIR = ROOT / "reports" / "tdc_literature_alignment"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
TABLE16_PATH = TABLE_DIR / "table16_tdc_roughness_literature_alignment.csv"
PERFORMANCE_TABLE = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"


def load_task_metadata() -> pd.DataFrame:
    from tdc.metadata import admet_benchmark, admet_metrics, admet_splits

    rows = []
    for family, names in admet_benchmark.items():
        for name in names:
            metric = admet_metrics[name]
            rows.append(
                {
                    "dataset": name,
                    "family": family,
                    "tdc_name": name,
                    "task_type": "classification" if metric in {"roc-auc", "pr-auc"} else "regression",
                    "official_metric": metric,
                    "official_split": admet_splits.get(name, "scaffold"),
                }
            )
    return pd.DataFrame(rows)


def normalize(raw: pd.DataFrame, task_type: str) -> pd.DataFrame:
    smiles_col = "Drug" if "Drug" in raw.columns else "smiles"
    target_col = "Y" if "Y" in raw.columns else "y"
    frame = raw[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"}).copy()
    frame["smiles"] = frame["smiles"].map(canonicalize_smiles)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    if task_type == "classification":
        frame["y"] = frame["y"].astype(int)
        frame = frame[frame["y"].isin([0, 1])].reset_index(drop=True)
    return frame


def load_split(family: str, name: str, cache_dir: Path, split_method: str, seed: int):
    from tdc.single_pred import ADME, Tox

    loader = ADME if family == "ADME" else Tox
    data = loader(name=name, path=str(cache_dir))
    return data.get_split(method=split_method, seed=seed)


def deterministic_sample(frame: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    if max_rows <= 0 or len(frame) <= max_rows:
        return frame.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    indices = rng.choice(frame.index.to_numpy(), size=max_rows, replace=False)
    return frame.loc[np.sort(indices)].reset_index(drop=True)


def stratified_reference_sample(frame: pd.DataFrame, task_type: str, max_rows: int, seed: int) -> pd.DataFrame:
    if max_rows <= 0 or len(frame) <= max_rows:
        return frame.reset_index(drop=True)
    if task_type != "classification" or frame["y"].nunique() < 2:
        return deterministic_sample(frame, max_rows, seed)
    rng = np.random.default_rng(seed)
    parts = []
    for label, group in frame.groupby("y", sort=True):
        take = max(1, int(round(max_rows * len(group) / len(frame))))
        take = min(take, len(group))
        parts.append(group.loc[rng.choice(group.index.to_numpy(), size=take, replace=False)])
    sampled = pd.concat(parts, ignore_index=True)
    if len(sampled) > max_rows:
        sampled = sampled.loc[rng.choice(sampled.index.to_numpy(), size=max_rows, replace=False)]
    return sampled.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def fingerprint(smiles: str, generator) -> object | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return generator.GetFingerprint(mol)


def fingerprint_frame(frame: pd.DataFrame, n_bits: int, radius: int) -> tuple[pd.DataFrame, list]:
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    keep_rows = []
    fps = []
    for _, row in frame.iterrows():
        fp = fingerprint(str(row["smiles"]), generator)
        if fp is None:
            continue
        keep_rows.append(row)
        fps.append(fp)
    if not keep_rows:
        return frame.iloc[0:0].copy(), []
    return pd.DataFrame(keep_rows).reset_index(drop=True), fps


def target_iqr(values: np.ndarray) -> float:
    q1, q3 = np.nanquantile(values.astype(float), [0.25, 0.75])
    iqr = float(q3 - q1)
    if not math.isfinite(iqr) or iqr <= 1e-12:
        std = float(np.nanstd(values.astype(float)))
        return std if std > 1e-12 else 1.0
    return iqr


def high_similarity_rate(values: np.ndarray, mask: np.ndarray) -> float:
    if not bool(mask.any()):
        return np.nan
    return float(np.nanmean(values[mask]))


def nearest_neighbor_diagnostics(
    task: pd.Series,
    split_method: str,
    seed: int,
    cache_dir: Path,
    max_reference: int,
    max_query: int,
    n_bits: int,
    radius: int,
    high_similarity_threshold: float,
    regression_delta_threshold: float,
) -> dict[str, object]:
    split = load_split(str(task.family), str(task.tdc_name), cache_dir, split_method, seed)
    train = normalize(split["train"], str(task.task_type))
    valid = normalize(split["valid"], str(task.task_type))
    test = normalize(split["test"], str(task.task_type))
    reference = pd.concat([train, valid], ignore_index=True).drop_duplicates("smiles").reset_index(drop=True)

    sample_seed = seed * 1009 + sum(ord(ch) for ch in str(task.dataset))
    reference_sample = stratified_reference_sample(reference, str(task.task_type), max_reference, sample_seed)
    query_sample = deterministic_sample(test, max_query, sample_seed + 17)
    reference_sample, reference_fps = fingerprint_frame(reference_sample, n_bits, radius)
    query_sample, query_fps = fingerprint_frame(query_sample, n_bits, radius)

    if not reference_fps or not query_fps:
        raise RuntimeError(f"No valid fingerprints for {task.dataset} seed={seed}.")

    reference_y = reference_sample["y"].to_numpy()
    query_y = query_sample["y"].to_numpy()
    nn_similarity = np.zeros(len(query_fps), dtype=float)
    nn_index = np.zeros(len(query_fps), dtype=int)
    for i, query_fp in enumerate(query_fps):
        sims = np.asarray(DataStructs.BulkTanimotoSimilarity(query_fp, reference_fps), dtype=float)
        best = int(np.argmax(sims))
        nn_index[i] = best
        nn_similarity[i] = float(sims[best])

    neighbor_y = reference_y[nn_index]
    high_mask = nn_similarity >= high_similarity_threshold
    if str(task.task_type) == "classification":
        delta = (query_y.astype(int) != neighbor_y.astype(int)).astype(float)
        normalized_delta = delta
        high_conflict = high_similarity_rate(delta, high_mask)
        high_large_delta = np.nan
        target_scale = np.nan
    else:
        target_scale = target_iqr(reference_y)
        delta = np.abs(query_y.astype(float) - neighbor_y.astype(float))
        normalized_delta = np.clip(delta / target_scale, 0.0, 5.0)
        high_conflict = np.nan
        high_large_delta = high_similarity_rate((normalized_delta >= regression_delta_threshold).astype(float), high_mask)

    roughness_proxy = float(np.nanmean(normalized_delta * nn_similarity))
    conflict_or_large_delta_rate = high_conflict
    if not math.isfinite(conflict_or_large_delta_rate):
        conflict_or_large_delta_rate = high_large_delta

    return {
        "dataset": str(task.dataset),
        "family": str(task.family),
        "tdc_name": str(task.tdc_name),
        "task_type": str(task.task_type),
        "official_metric": str(task.official_metric),
        "split_method": split_method,
        "seed": seed,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test_total": len(test),
        "n_reference_total": len(reference),
        "n_reference_sampled": len(reference_sample),
        "n_query_sampled": len(query_sample),
        "morgan_radius": radius,
        "morgan_bits": n_bits,
        "high_similarity_threshold": high_similarity_threshold,
        "nn_tanimoto_mean": float(np.nanmean(nn_similarity)),
        "nn_tanimoto_median": float(np.nanmedian(nn_similarity)),
        "nn_tanimoto_p10": float(np.nanquantile(nn_similarity, 0.10)),
        "nn_tanimoto_p90": float(np.nanquantile(nn_similarity, 0.90)),
        "high_similarity_fraction": float(np.nanmean(high_mask.astype(float))),
        "neighbor_delta_mean": float(np.nanmean(delta)),
        "neighbor_delta_norm_mean": float(np.nanmean(normalized_delta)),
        "high_similarity_discordance_rate": high_conflict,
        "high_similarity_large_delta_rate": high_large_delta,
        "neighbor_conflict_or_large_delta_rate": conflict_or_large_delta_rate,
        "roughness_proxy": roughness_proxy,
        "target_iqr_reference": target_scale,
        "reference_positive_rate": float(np.nanmean(reference_y)) if str(task.task_type) == "classification" else np.nan,
        "query_positive_rate": float(np.nanmean(query_y)) if str(task.task_type) == "classification" else np.nan,
    }


def metric_mean(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return np.nan
    value = frame[column].mean()
    return float(value) if pd.notna(value) else np.nan


def metric_std(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return np.nan
    value = frame[column].std()
    return float(value) if pd.notna(value) else np.nan


def challenge_band(values: pd.Series) -> pd.Series:
    finite = pd.to_numeric(values, errors="coerce").dropna()
    if finite.empty or finite.nunique() == 1:
        return pd.Series(["medium"] * len(values), index=values.index)
    low = float(finite.quantile(1.0 / 3.0))
    high = float(finite.quantile(2.0 / 3.0))

    def label(value: object) -> str:
        if pd.isna(value):
            return "unknown"
        value = float(value)
        if value >= high:
            return "high"
        if value <= low:
            return "low"
        return "medium"

    return values.map(label)


def add_recommendation(row: pd.Series) -> str:
    pieces = []
    high_sim = float(row.get("high_similarity_fraction_mean", np.nan))
    roughness = str(row.get("roughness_band", "unknown"))
    delta = row.get("performance_delta_vs_previous", np.nan)
    retained = str(row.get("retained_source", "unknown"))
    task_type = str(row.get("task_type", ""))
    if math.isfinite(high_sim) and high_sim < 0.20:
        pieces.append("emphasize AD/OOD gating")
    if roughness == "high":
        pieces.append("inspect local cliffs/noisy neighborhoods")
    if math.isfinite(float(delta)) and float(delta) > 0.0:
        pieces.append("cite performance-mode ensemble gain")
    elif retained == "previous_table14":
        pieces.append("keep retained-best result")
    if task_type == "classification":
        pos = row.get("reference_positive_rate_mean", np.nan)
        if pd.notna(pos) and min(float(pos), 1.0 - float(pos)) < 0.15:
            pieces.append("report PR-AUC/undersampling diagnostics")
    if not pieces:
        pieces.append("use as medium-risk appendix evidence")
    return "; ".join(dict.fromkeys(pieces))


def summarize(seed_metrics: pd.DataFrame, performance_table: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for dataset, group in seed_metrics.groupby("dataset", dropna=False):
        first = group.iloc[0]
        rows.append(
            {
                "dataset": dataset,
                "family": first["family"],
                "task_type": first["task_type"],
                "official_metric": first["official_metric"],
                "split_method": first["split_method"],
                "n_seeds": int(group["seed"].nunique()),
                "n_reference_sampled_mean": metric_mean(group, "n_reference_sampled"),
                "n_query_sampled_mean": metric_mean(group, "n_query_sampled"),
                "nn_tanimoto_mean": metric_mean(group, "nn_tanimoto_mean"),
                "nn_tanimoto_std": metric_std(group, "nn_tanimoto_mean"),
                "high_similarity_fraction_mean": metric_mean(group, "high_similarity_fraction"),
                "neighbor_delta_norm_mean": metric_mean(group, "neighbor_delta_norm_mean"),
                "neighbor_conflict_or_large_delta_rate_mean": metric_mean(
                    group, "neighbor_conflict_or_large_delta_rate"
                ),
                "roughness_proxy_mean": metric_mean(group, "roughness_proxy"),
                "roughness_proxy_std": metric_std(group, "roughness_proxy"),
                "reference_positive_rate_mean": metric_mean(group, "reference_positive_rate"),
                "query_positive_rate_mean": metric_mean(group, "query_positive_rate"),
            }
        )
    summary = pd.DataFrame(rows).sort_values(["family", "dataset"]).reset_index(drop=True)
    summary["roughness_band"] = challenge_band(summary["roughness_proxy_mean"])
    summary["ood_band"] = challenge_band(1.0 - summary["nn_tanimoto_mean"])

    table16 = summary.copy()
    if performance_table.exists():
        perf = pd.read_csv(performance_table)
        keep = [
            "dataset",
            "primary_direction",
            "previous_primary_mean",
            "performance_primary_mean",
            "performance_delta_vs_previous",
            "retained_source",
            "retained_primary_mean",
            "retained_model",
        ]
        table16 = table16.merge(perf[[c for c in keep if c in perf.columns]], on="dataset", how="left")
    table16["manuscript_use"] = table16.apply(add_recommendation, axis=1)
    return summary, table16


def write_report(output_dir: Path, table16: pd.DataFrame, seed_metrics: pd.DataFrame) -> None:
    improved = table16[pd.to_numeric(table16.get("performance_delta_vs_previous"), errors="coerce") > 0.0]
    high_rough = table16[table16["roughness_band"].eq("high")].sort_values(
        "roughness_proxy_mean", ascending=False
    )
    low_similarity = table16.sort_values("nn_tanimoto_mean").head(6)

    lines = [
        "# TDC Roughness And Literature-Alignment Diagnostic",
        "",
        "Date: 2026-05-31",
        "",
        "This appendix diagnostic was added after reviewing recent ADMET and molecular property",
        "prediction benchmarks that emphasize TabPFN/tree baselines, OOD reliability, class",
        "imbalance, activity cliffs, and lightweight molecular-property roughness diagnostics.",
        "",
        "The diagnostic is intentionally lightweight: for each official PyTDC scaffold split,",
        "each sampled test molecule is paired with its nearest train+valid Morgan-fingerprint",
        "neighbor. Classification endpoints record high-similarity label discordance; regression",
        "endpoints record high-similarity large normalized target jumps. The roughness proxy is",
        "not claimed as a new benchmark metric; it is an explanatory appendix signal.",
        "",
        "## Outputs",
        "",
        f"- Seed metrics: `{(output_dir / 'tdc_roughness_seed_metrics.csv').resolve().relative_to(ROOT)}`",
        f"- Endpoint summary: `{(output_dir / 'tdc_roughness_summary.csv').resolve().relative_to(ROOT)}`",
        f"- Roughness/performance figure: `{(output_dir / 'fig_tdc_roughness_vs_performance_delta.png').resolve().relative_to(ROOT)}`",
        "- Manuscript table: `reports/manuscript_tables/table16_tdc_roughness_literature_alignment.csv`",
        "",
        "## Strongest Signals",
        "",
        f"- Completed endpoint coverage: {table16['dataset'].nunique()}/22 endpoints; seed rows: {len(seed_metrics)}.",
        f"- Performance-mode retained-best improved {len(improved)} endpoints over Table 14 and is now cross-referenced against roughness/OOD diagnostics.",
        f"- High roughness endpoints: {', '.join(high_rough['dataset'].head(6).astype(str).tolist())}.",
        f"- Lowest nearest-neighbor similarity endpoints: {', '.join(low_similarity['dataset'].astype(str).tolist())}.",
        "",
        "## How To Use In The Paper",
        "",
        "- In the main text, state that recent ADMET reliability work motivated a low-cost roughness/nearest-neighbor appendix diagnostic.",
        "- Keep Table 16 in the supplement because it is explanatory and uses endpoint-specific native labels rather than a unified primary metric.",
        "- Use high-roughness rows to discuss why validation-only ensembles and target transforms help some ADME regression endpoints but do not erase activity-cliff-style local discontinuities.",
        "- Use low-similarity rows to support the existing applicability-domain and conformal/reliability framing.",
        "- Describe motif and nearest-neighbor evidence as associative interpretability, not mechanistic causality.",
        "",
    ]
    (output_dir / "roughness_vs_performance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_roughness_figure(output_dir: Path, table16: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (output_dir / "figure_generation_skipped.txt").write_text(
            f"Matplotlib import failed: {exc}\n", encoding="utf-8"
        )
        return

    frame = table16.copy()
    frame["performance_delta_vs_previous"] = pd.to_numeric(
        frame.get("performance_delta_vs_previous"), errors="coerce"
    )
    frame["roughness_proxy_mean"] = pd.to_numeric(frame["roughness_proxy_mean"], errors="coerce")
    frame = frame.dropna(subset=["roughness_proxy_mean", "performance_delta_vs_previous"])
    if frame.empty:
        return

    colors = {"regression": "#2f6f9f", "classification": "#b76e2b"}
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for task_type, group in frame.groupby("task_type", dropna=False):
        ax.scatter(
            group["roughness_proxy_mean"],
            group["performance_delta_vs_previous"],
            s=54,
            alpha=0.82,
            label=str(task_type),
            color=colors.get(str(task_type), "#555555"),
            edgecolor="white",
            linewidth=0.7,
        )
    ax.axhline(0.0, color="#444444", linewidth=1.0, linestyle="--")
    ax.set_xlabel("Nearest-neighbor roughness proxy")
    ax.set_ylabel("Performance-mode gain vs Table 14")
    ax.set_title("TDC roughness diagnostic vs retained-best gain")
    ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.75)
    ax.legend(frameon=False)

    label_candidates = pd.concat(
        [
            frame.sort_values("roughness_proxy_mean", ascending=False).head(5),
            frame.sort_values("performance_delta_vs_previous", ascending=False).head(5),
        ],
        ignore_index=True,
    ).drop_duplicates("dataset")
    for _, row in label_candidates.iterrows():
        ax.annotate(
            str(row["dataset"]),
            (float(row["roughness_proxy_mean"]), float(row["performance_delta_vs_previous"])),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7.5,
        )
    fig.tight_layout()
    fig.savefig(output_dir / "fig_tdc_roughness_vs_performance_delta.png", dpi=220)
    fig.savefig(output_dir / "fig_tdc_roughness_vs_performance_delta.svg")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a lightweight TDC roughness/OOD diagnostic aligned with recent ADMET literature."
    )
    parser.add_argument("--datasets", nargs="*", default=None)
    parser.add_argument("--split-method", default="scaffold")
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--tdc-cache-dir", default=str(ROOT / "data" / "tdc"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--max-reference", type=int, default=1500)
    parser.add_argument("--max-query", type=int, default=400)
    parser.add_argument("--morgan-bits", type=int, default=2048)
    parser.add_argument("--morgan-radius", type=int, default=2)
    parser.add_argument("--high-similarity-threshold", type=float, default=0.70)
    parser.add_argument("--regression-delta-threshold", type=float, default=0.50)
    parser.add_argument("--performance-table", default=str(PERFORMANCE_TABLE))
    parser.add_argument("--skip-errors", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    tasks = load_task_metadata()
    if args.datasets:
        requested = set(args.datasets)
        tasks = tasks[tasks["dataset"].isin(requested)].reset_index(drop=True)
        missing = sorted(requested - set(tasks["dataset"]))
        if missing:
            raise ValueError(f"Unknown datasets: {missing}")

    rows = []
    errors = []
    for _, task in tasks.iterrows():
        for seed in args.seeds:
            try:
                row = nearest_neighbor_diagnostics(
                    task=task,
                    split_method=args.split_method,
                    seed=seed,
                    cache_dir=Path(args.tdc_cache_dir),
                    max_reference=args.max_reference,
                    max_query=args.max_query,
                    n_bits=args.morgan_bits,
                    radius=args.morgan_radius,
                    high_similarity_threshold=args.high_similarity_threshold,
                    regression_delta_threshold=args.regression_delta_threshold,
                )
                rows.append(row)
                print(
                    f"[ok] {task.dataset} seed={seed} nn={row['nn_tanimoto_mean']:.3f} "
                    f"rough={row['roughness_proxy']:.3f}"
                )
            except Exception as exc:
                error = {"dataset": str(task.dataset), "seed": seed, "error": repr(exc)}
                errors.append(error)
                print(f"[error] {task.dataset} seed={seed}: {exc}")
                if not args.skip_errors:
                    raise

    seed_metrics = pd.DataFrame(rows)
    seed_metrics.to_csv(output_dir / "tdc_roughness_seed_metrics.csv", index=False)
    if errors:
        pd.DataFrame(errors).to_csv(output_dir / "tdc_roughness_errors.csv", index=False)
    if seed_metrics.empty:
        raise RuntimeError("No roughness rows were generated.")

    summary, table16 = summarize(seed_metrics, Path(args.performance_table))
    summary.to_csv(output_dir / "tdc_roughness_summary.csv", index=False)
    table16.to_csv(TABLE16_PATH, index=False)
    write_roughness_figure(output_dir, table16)
    write_report(output_dir, table16, seed_metrics)
    print(f"Wrote {output_dir / 'tdc_roughness_seed_metrics.csv'}")
    print(f"Wrote {output_dir / 'tdc_roughness_summary.csv'}")
    print(f"Wrote {TABLE16_PATH}")


if __name__ == "__main__":
    main()
