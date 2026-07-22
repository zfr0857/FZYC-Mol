from __future__ import annotations

import getpass
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.datasets import load_dataset  # noqa: E402
from fzyc_mol.features import morgan_fingerprint  # noqa: E402
from fzyc_mol.reliability.risk_coverage import risk_coverage_audit  # noqa: E402
from fzyc_mol.selection.candidate_pool_audit import audit_candidate_pool  # noqa: E402
from fzyc_mol.splits import make_split, random_split  # noqa: E402


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cold_start(output_dir: Path | str = ROOT / "results" / "cold_start", *, max_rows: int = 400, seed: int = 11) -> dict[str, Path]:
    started = time.perf_counter()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame, _ = load_dataset("esol", data_dir=ROOT / "data", max_rows=max_rows)
    x = np.vstack([morgan_fingerprint(smiles, n_bits=512) for smiles in frame["smiles"]])
    y = frame["y"].to_numpy(dtype=float)
    split = make_split(frame, "scaffold", seed)
    if min(len(split.train), len(split.valid), len(split.test)) == 0:
        split = random_split(frame, seed)
    candidates = {
        "ridge_a0.1": Ridge(alpha=0.1),
        "ridge_a1": Ridge(alpha=1.0),
        "ridge_a10": Ridge(alpha=10.0),
        "rf_40": RandomForestRegressor(n_estimators=40, random_state=seed, n_jobs=-1),
    }
    rows = []
    test_predictions: dict[str, np.ndarray] = {}
    for candidate_id, model in candidates.items():
        model.fit(x[split.train], y[split.train])
        valid = model.predict(x[split.valid])
        test = model.predict(x[split.test])
        test_predictions[candidate_id] = test
        rows.append(
            {
                "candidate_id": candidate_id,
                "inner_fold": 1,
                "val_utility": -float(np.sqrt(mean_squared_error(y[split.valid], valid))),
                "test_utility": -float(np.sqrt(mean_squared_error(y[split.test], test))),
                "fit_seconds": 0.0,
            }
        )
    metrics = pd.DataFrame(rows)
    outer = metrics.set_index("candidate_id")["test_utility"].to_dict()
    audit = audit_candidate_pool(
        metrics,
        outer,
        full_test_utility=outer,
        pool_candidate_ids=list(candidates),
        baseline_id="ridge_a0.1",
        task_type="regression",
    )
    assert audit.decision is not None and audit.ranking is not None and audit.regret is not None
    prediction_matrix = np.column_stack([test_predictions[name] for name in candidates])
    risk = risk_coverage_audit(
        y[split.test],
        test_predictions[audit.decision.candidate_id],
        np.std(prediction_matrix, axis=1),
        task_type="regression",
    )
    paths = {
        "candidate_metrics": output / "esol_candidate_metrics.csv",
        "candidate_audit": output / "candidate_pool_audit.csv",
        "risk_curve": output / "risk_coverage.csv",
        "figure": output / "risk_coverage.png",
        "log": output / "cold_start_log.json",
    }
    metrics.to_csv(paths["candidate_metrics"], index=False)
    pd.DataFrame(
        [
            {
                "endpoint": "esol",
                "status": audit.status,
                "selected_candidate": audit.decision.candidate_id,
                **audit.ranking,
                **audit.regret,
            }
        ]
    ).to_csv(paths["candidate_audit"], index=False)
    risk.curve.to_csv(paths["risk_curve"], index=False)
    plt.figure(figsize=(5.2, 3.5))
    plt.plot(risk.curve["coverage"], risk.curve["risk"], marker="o", label="model risk")
    plt.plot(risk.curve["coverage"], risk.curve["oracle_lower_bound_risk"], linestyle="--", label="oracle lower bound")
    plt.xlabel("Coverage")
    plt.ylabel("RMSE")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(paths["figure"], dpi=180)
    plt.close()
    paths["log"].write_text(
        json.dumps(
            {
                "operator": getpass.getuser(),
                "system": platform.platform(),
                "python": platform.python_version(),
                "dataset": "ESOL",
                "rows": len(frame),
                "seed": seed,
                "elapsed_seconds": time.perf_counter() - started,
                "status": "local_completed_not_third_party",
                "output_hashes": {name: _hash(path) for name, path in paths.items() if name != "log"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return paths


def main() -> None:
    for name, path in run_cold_start().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
