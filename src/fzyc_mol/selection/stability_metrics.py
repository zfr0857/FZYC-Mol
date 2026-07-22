from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence


def mean_pairwise_jaccard(sets: Sequence[set[str]]) -> float:
    if len(sets) < 2:
        return 1.0
    values = []
    for left in range(len(sets)):
        for right in range(left + 1, len(sets)):
            union = sets[left] | sets[right]
            values.append(len(sets[left] & sets[right]) / len(union) if union else 1.0)
    return sum(values) / len(values)


def selection_stability(
    selected_candidates: Sequence[str],
    candidate_family: Mapping[str, str],
    *,
    available_candidates: Sequence[str],
) -> dict[str, float | int | str]:
    selected = [str(value) for value in selected_candidates]
    available = [str(value) for value in available_candidates]
    if not selected or not available:
        raise ValueError("selected and available candidates must be non-empty")
    counts = Counter(selected)
    probabilities = [count / len(selected) for count in counts.values()]
    denominator = math.log(len(available)) if len(available) > 1 else 1.0
    entropy = -sum(value * math.log(value) for value in probabilities) / denominator if len(available) > 1 else 0.0
    family_counts = Counter(candidate_family[candidate] for candidate in selected)
    modal_candidate, modal_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return {
        "n_selections": len(selected),
        "n_selected_candidates": len(counts),
        "modal_candidate": modal_candidate,
        "modal_selection_rate": modal_count / len(selected),
        "normalized_entropy": entropy,
        "family_stability": max(family_counts.values()) / len(selected),
    }
