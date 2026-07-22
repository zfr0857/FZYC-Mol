from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "paper31_expanded_intervention_20260717" / "similarity_composition"
TASKS = ["clintox", "bace", "esol"]
SEEDS = [11, 23, 37, 53, 71]


def patch_similarity_splits():
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_expanded_nested_candidate_pool_20260621 as strict
    import run_shared_split_multiview_nested_20260624 as shared

    original_featurize = shared.featurize
    original_make_model = shared.make_model

    def similarity_featurize(smiles):
        representations, _scaffolds, keep = original_featurize(smiles)
        groups, _similarities = strict.similarity_component_groups(representations["morgan512"], 0.70)
        return representations, groups, keep

    def similarity_splits(y, groups, task_type, n_splits, seed):
        return strict.make_regime_splits(
            y, groups, task_type, n_splits, seed, "similarity_cluster"
        )

    def capped_make_model(task_type, family, seed):
        model = original_make_model(task_type, family, seed)
        params = {key: 2 for key in model.get_params(deep=True) if key.endswith("__n_jobs")}
        if params:
            model.set_params(**params)
        return model

    shared.featurize = similarity_featurize
    shared.make_splits = similarity_splits
    shared.make_model = capped_make_model
    return shared


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["base", "new-candidates", "chemprop-inner", "chemprop-outer"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    shared = patch_similarity_splits()
    common = [
        "paper31-similarity", "--tasks", *TASKS, "--seeds", *map(str, SEEDS),
        "--outer-folds", "3", "--inner-folds", "3",
    ]
    if args.force:
        common.append("--force")

    if args.stage == "base":
        shared.OUT = RESULTS / "base"
        module = shared
    elif args.stage == "new-candidates":
        import run_equal_size_registry_composition_20260716 as module
        module.OUT = RESULTS / "new_candidates"
    elif args.stage == "chemprop-inner":
        import run_paper12_chemprop_inner_panel as module
        module.OUT = RESULTS / "chemprop"
        module.WORK = RESULTS / "chemprop_inner_work"
        common += ["--epochs", "1", "--batch-size", "512"]
    else:
        import run_paper12_chemprop_outer_panel as module
        module.OUT = RESULTS / "chemprop"
        module.WORK = RESULTS / "chemprop_outer_work"
        common += ["--epochs", "1", "--batch-size", "256"]

    sys.argv = common
    module.main()


if __name__ == "__main__":
    main()
