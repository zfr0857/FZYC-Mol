from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def build_run_id(
    *,
    config: Mapping[str, Any],
    data_hash: str,
    split_hash: str,
    seed: int,
    code_hash: str,
    prediction_hash: str,
) -> str:
    """Return a content identity; runtime and final metric are intentionally absent."""

    payload = {
        "config": config,
        "data_hash": data_hash,
        "split_hash": split_hash,
        "seed": int(seed),
        "code_hash": code_hash,
        "prediction_hash": prediction_hash,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
