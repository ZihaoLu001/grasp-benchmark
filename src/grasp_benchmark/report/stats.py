from __future__ import annotations

import math
import random
from statistics import mean
from typing import Iterable, Sequence


def wilson_ci(successes: int, trials: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 0.0)
    p_hat = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p_hat + z2 / (2.0 * trials)) / denominator
    margin = z * math.sqrt((p_hat * (1.0 - p_hat) + z2 / (4.0 * trials)) / trials) / denominator
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (round(low, 4), round(high, 4))


def exact_mcnemar(n_01: int, n_10: int) -> float:
    total = int(n_01) + int(n_10)
    if total <= 0:
        return 1.0
    tail = 0.0
    cutoff = min(int(n_01), int(n_10))
    for value in range(cutoff + 1):
        tail += math.comb(total, value) * (0.5**total)
    return round(min(1.0, 2.0 * tail), 6)


def paired_bootstrap_delta(
    pairs: Sequence[tuple[float, float]],
    *,
    iterations: int = 10_000,
    seed: int = 0,
) -> tuple[float, float]:
    if not pairs:
        return (0.0, 0.0)
    if len(pairs) == 1:
        delta = float(pairs[0][1]) - float(pairs[0][0])
        return (round(delta, 4), round(delta, 4))
    rng = random.Random(seed)
    pair_list = [(float(a), float(b)) for a, b in pairs]
    sample_count = len(pair_list)
    deltas: list[float] = []
    for _ in range(max(int(iterations), 1)):
        sampled = [pair_list[rng.randrange(sample_count)] for _ in range(sample_count)]
        deltas.append(mean(b - a for a, b in sampled))
    deltas.sort()
    low_index = max(0, int(0.025 * (len(deltas) - 1)))
    high_index = min(len(deltas) - 1, int(0.975 * (len(deltas) - 1)))
    return (round(deltas[low_index], 4), round(deltas[high_index], 4))


def build_pair_matrix(
    rows: Iterable[dict[str, object]],
    *,
    method_a: str,
    method_b: str,
    key_fields: Sequence[str] = ("scene_recipe_id",),
) -> dict[str, object]:
    grouped: dict[tuple[str, ...], dict[str, int]] = {}
    for row in rows:
        method = str(row.get("method_tier", "")).strip()
        if method not in {method_a, method_b}:
            continue
        key = tuple(str(row.get(field, "")).strip() for field in key_fields)
        if not any(key):
            continue
        entry = grouped.setdefault(key, {})
        if method in entry:
            raise ValueError(f"Duplicate paired coverage for method={method} key={key}.")
        entry[method] = int(row.get("success", 0))

    keys_a = {key for key, values in grouped.items() if method_a in values}
    keys_b = {key for key, values in grouped.items() if method_b in values}
    paired_keys = sorted(keys_a & keys_b)
    pairs = [(grouped[key][method_a], grouped[key][method_b]) for key in paired_keys]
    return {
        "method_a": method_a,
        "method_b": method_b,
        "paired_keys": paired_keys,
        "pairs": pairs,
        "missing_for_a": sorted(keys_b - keys_a),
        "missing_for_b": sorted(keys_a - keys_b),
    }

