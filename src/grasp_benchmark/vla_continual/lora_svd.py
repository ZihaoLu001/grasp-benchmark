from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_tensor_file(path: Path) -> dict[str, Any]:
    if path.suffix == ".safetensors":
        from safetensors.torch import load_file

        return dict(load_file(str(path), device="cpu"))

    import torch

    payload = torch.load(path, map_location="cpu")
    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        payload = payload["state_dict"]
    if not isinstance(payload, dict):
        return {}
    return payload


def _candidate_weight_files(checkpoint_dir: Path) -> list[Path]:
    names = [
        "adapter_model.safetensors",
        "adapter_model.bin",
        "pytorch_model.bin",
        "model.safetensors",
    ]
    files: list[Path] = []
    for name in names:
        files.extend(sorted(checkpoint_dir.rglob(name)))
    if not files:
        files.extend(sorted(checkpoint_dir.rglob("*.safetensors")))
        files.extend(sorted(checkpoint_dir.rglob("*.bin")))
        files.extend(sorted(checkpoint_dir.rglob("*.pt")))
    return files


def _pair_lora_matrices(state: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    pairs: dict[str, dict[str, Any]] = defaultdict(dict)
    for key, tensor in state.items():
        if "lora_A" in key and key.endswith(".weight"):
            prefix = key.split(".lora_A", 1)[0]
            pairs[prefix]["A"] = tensor
        elif "lora_B" in key and key.endswith(".weight"):
            prefix = key.split(".lora_B", 1)[0]
            pairs[prefix]["B"] = tensor
    return [
        (prefix, item["A"], item["B"])
        for prefix, item in sorted(pairs.items())
        if "A" in item and "B" in item
    ]


def _matrix_stats(name: str, matrix: Any) -> dict[str, Any]:
    import torch

    mat = matrix.detach().float().cpu()
    if mat.ndim > 2:
        mat = mat.reshape(mat.shape[0], -1)
    if mat.numel() == 0:
        singular = torch.zeros(0)
    else:
        singular = torch.linalg.svdvals(mat)
    positive = singular[singular > 1e-12]
    if positive.numel() == 0:
        effective_rank = 0.0
        top1_frac = 0.0
        nonzero_rank = 0
    else:
        probs = positive / positive.sum()
        entropy = -(probs * torch.log(probs)).sum()
        effective_rank = float(torch.exp(entropy).item())
        top1_frac = float((positive.max() / positive.sum()).item())
        nonzero_rank = int(positive.numel())
    return {
        "name": name,
        "shape": list(mat.shape),
        "nonzero_rank": nonzero_rank,
        "effective_rank": effective_rank,
        "nuclear_norm": float(singular.sum().item()) if singular.numel() else 0.0,
        "frobenius_norm": float(torch.linalg.vector_norm(mat).item()) if mat.numel() else 0.0,
        "top1_singular_frac": top1_frac,
        "max_singular": float(singular.max().item()) if singular.numel() else 0.0,
    }


def summarize_lora_effective_rank(checkpoint_dir: Path) -> dict[str, Any]:
    checkpoint_dir = checkpoint_dir.resolve()
    files = _candidate_weight_files(checkpoint_dir)
    layers: list[dict[str, Any]] = []
    loaded_files: list[str] = []

    for path in files:
        state = _load_tensor_file(path)
        pairs = _pair_lora_matrices(state)
        if not pairs:
            continue
        loaded_files.append(str(path))
        for prefix, lora_a, lora_b in pairs:
            try:
                delta = lora_b.detach().float().cpu() @ lora_a.detach().float().cpu()
            except Exception:
                continue
            layers.append(_matrix_stats(prefix, delta))

    def mean(key: str) -> float:
        values = [float(layer[key]) for layer in layers]
        return float(sum(values) / len(values)) if values else 0.0

    effective_ranks = sorted(float(layer["effective_rank"]) for layer in layers)
    if effective_ranks:
        mid = len(effective_ranks) // 2
        median = (
            effective_ranks[mid]
            if len(effective_ranks) % 2
            else 0.5 * (effective_ranks[mid - 1] + effective_ranks[mid])
        )
    else:
        median = 0.0

    return {
        "checkpoint_dir": str(checkpoint_dir),
        "weight_files": loaded_files,
        "num_lora_layers": len(layers),
        "mean_effective_rank": mean("effective_rank"),
        "median_effective_rank": median,
        "mean_nonzero_rank": mean("nonzero_rank"),
        "mean_nuclear_norm": mean("nuclear_norm"),
        "mean_frobenius_norm": mean("frobenius_norm"),
        "mean_top1_singular_frac": mean("top1_singular_frac"),
        "layers": layers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize LoRA update effective rank from a checkpoint.")
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = summarize_lora_effective_rank(Path(args.checkpoint_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "LORA_EFFECTIVE_RANK "
        f"layers={payload['num_lora_layers']} "
        f"mean={payload['mean_effective_rank']:.4f} "
        f"median={payload['median_effective_rank']:.4f}"
    )


if __name__ == "__main__":
    main()
