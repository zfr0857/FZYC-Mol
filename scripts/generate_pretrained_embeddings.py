from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset


def safe_model_id(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("_")


def mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp_min(1.0)
    return summed / counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate frozen pretrained SMILES encoder embeddings, e.g. ChemBERTa/MolFormer."
    )
    parser.add_argument("--model-name", default="DeepChem/ChemBERTa-77M-MTR")
    parser.add_argument("--datasets", nargs="*", default=list(DATASETS))
    parser.add_argument("--output-root", default=str(ROOT / "data" / "processed" / "pretrained_embeddings"))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    try:
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Missing optional dependency 'transformers'. Install it first, then rerun this script."
        ) from exc

    encoder_id = safe_model_id(args.model_name)
    output_dir = Path(args.output_root) / encoder_id
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name,
        local_files_only=args.local_files_only,
        trust_remote_code=True,
    )
    model = AutoModel.from_pretrained(
        args.model_name,
        local_files_only=args.local_files_only,
        trust_remote_code=True,
    ).to(args.device)
    model.eval()

    metadata = {
        "model_name": args.model_name,
        "encoder_id": encoder_id,
        "pooling": "attention_masked_mean_last_hidden_state",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    for dataset in args.datasets:
        frame, _spec = load_dataset(dataset, data_dir=ROOT / "data")
        smiles = frame["smiles"].tolist()
        embeddings: list[np.ndarray] = []
        with torch.no_grad():
            for start in tqdm(range(0, len(smiles), args.batch_size), desc=f"embed:{dataset}"):
                batch_smiles = smiles[start : start + args.batch_size]
                encoded = tokenizer(
                    batch_smiles,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                )
                encoded = {key: value.to(args.device) for key, value in encoded.items()}
                output = model(**encoded)
                pooled = mean_pool(output.last_hidden_state, encoded["attention_mask"])
                embeddings.append(pooled.cpu().numpy().astype(np.float32))
        arr = np.vstack(embeddings)
        np.savez_compressed(
            output_dir / f"{dataset}.npz",
            smiles=np.asarray(smiles, dtype=object),
            embedding=arr,
        )
        print(f"saved dataset={dataset} rows={len(smiles)} dim={arr.shape[1]} path={output_dir / f'{dataset}.npz'}")


if __name__ == "__main__":
    main()
