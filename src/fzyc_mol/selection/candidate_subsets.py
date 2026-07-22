from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CandidateSubset:
    mode: str
    seed: int
    pool_size: int
    candidate_ids: tuple[str, ...]
    family_counts: tuple[tuple[str, int], ...]


def _family_targets(frame: pd.DataFrame, k: int, forced: tuple[str, ...]) -> dict[str, int]:
    counts = frame["family"].value_counts().sort_index()
    raw = counts * (k / len(frame))
    targets = raw.apply(np.floor).astype(int).to_dict()
    remainder = k - sum(targets.values())
    fractions = (raw - raw.apply(np.floor)).sort_values(ascending=False, kind="stable")
    for family in fractions.index[:remainder]:
        targets[str(family)] += 1

    by_id = frame.set_index("candidate_id")["family"].astype(str).to_dict()
    forced_counts = Counter(by_id[candidate] for candidate in forced)
    for family, required in forced_counts.items():
        while targets[family] < required:
            donors = [name for name in sorted(targets) if targets[name] > forced_counts.get(name, 0)]
            if not donors:
                raise ValueError("forced candidates are incompatible with family targets")
            donor = max(donors, key=lambda name: (targets[name] - forced_counts.get(name, 0), name))
            targets[donor] -= 1
            targets[family] += 1
    return targets


def build_subset(
    registry: pd.DataFrame,
    k: int,
    *,
    mode: str,
    seed: int,
    force_include: tuple[str, ...] = (),
) -> CandidateSubset:
    """Build a reproducible candidate subset without consulting outcome data."""

    required = {"candidate_id", "family", "registry_order"}
    missing = required - set(registry.columns)
    if missing:
        raise ValueError(f"missing registry columns: {sorted(missing)}")
    if mode not in {"random_order", "random_subset", "family_balanced"}:
        raise ValueError(f"unsupported mode: {mode}")
    frame = registry.sort_values("registry_order", kind="stable").copy()
    frame["candidate_id"] = frame["candidate_id"].astype(str)
    if frame["candidate_id"].duplicated().any():
        raise ValueError("candidate_id must be unique")
    if not 1 <= k <= len(frame) or len(force_include) > k:
        raise ValueError("k must be between forced count and registry size")
    ids = set(frame["candidate_id"])
    absent = set(force_include) - ids
    if absent:
        raise KeyError(sorted(absent)[0])

    forced = tuple(dict.fromkeys(str(value) for value in force_include))
    rng = np.random.default_rng(seed)
    remaining = frame[~frame["candidate_id"].isin(forced)]
    if mode == "random_order":
        shuffled = remaining.iloc[rng.permutation(len(remaining))]["candidate_id"].tolist()
        selected = list(forced) + shuffled[: k - len(forced)]
    elif mode == "random_subset":
        chosen = rng.choice(remaining["candidate_id"].to_numpy(), size=k - len(forced), replace=False).tolist()
        selected_set = set(forced) | set(chosen)
        selected = frame[frame["candidate_id"].isin(selected_set)]["candidate_id"].tolist()
    else:
        targets = _family_targets(frame, k, forced)
        by_id = frame.set_index("candidate_id")["family"].astype(str).to_dict()
        selected_set = set(forced)
        for family, target in sorted(targets.items()):
            forced_in_family = sum(by_id[candidate] == family for candidate in forced)
            family_pool = remaining[remaining["family"].astype(str).eq(family)]["candidate_id"].to_numpy()
            need = target - forced_in_family
            if need:
                selected_set.update(rng.choice(family_pool, size=need, replace=False).tolist())
        selected = frame[frame["candidate_id"].isin(selected_set)]["candidate_id"].tolist()

    by_id = frame.set_index("candidate_id")["family"].astype(str).to_dict()
    family_counts = Counter(by_id[candidate] for candidate in selected)
    return CandidateSubset(
        mode=mode,
        seed=int(seed),
        pool_size=k,
        candidate_ids=tuple(selected),
        family_counts=tuple(sorted(family_counts.items())),
    )
