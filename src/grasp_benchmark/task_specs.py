from __future__ import annotations

from hashlib import sha256
from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_CATALOG: dict[str, list[dict[str, str]]] = {
    "ycb_core": [
        {"id": "red_mug", "label": "red mug"},
        {"id": "mustard_bottle", "label": "mustard bottle"},
        {"id": "banana", "label": "banana"},
        {"id": "ceramic_bowl", "label": "ceramic bowl"},
        {"id": "power_drill", "label": "power drill"},
    ],
    "transparent": [
        {"id": "clear_plastic_cup", "label": "clear plastic cup"},
        {"id": "glass_bottle", "label": "glass bottle"},
        {"id": "wine_glass", "label": "wine glass"},
        {"id": "acrylic_box", "label": "acrylic box"},
    ],
}


@dataclass(frozen=True, slots=True)
class TrialSpec:
    track: str
    task: str
    scene_id: str
    scene_recipe_id: str
    object_id: str
    object_label: str
    object_group: str
    condition: str
    instruction: str
    attempts_per_trial: int
    replicate_index: int = 1
    seed: int = 0

    def to_task_spec(self) -> dict[str, Any]:
        return asdict(self)


def _catalog_by_id(task_config: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    raw_catalog = task_config.get("catalog") or DEFAULT_CATALOG
    output: dict[str, dict[str, dict[str, str]]] = {}
    for group_name, items in raw_catalog.items():
        output[group_name] = {}
        for item in items:
            item_id = str(item["id"])
            output[group_name][item_id] = {
                "id": item_id,
                "label": str(item.get("label", item_id.replace("_", " "))),
            }
    return output


def _condition_variants(condition: Any, default_variant_count: int) -> tuple[str, int]:
    if isinstance(condition, dict):
        name = str(condition.get("name", "")).strip()
        variant_count = int(condition.get("variant_count", condition.get("replicates", default_variant_count)))
    else:
        name = str(condition).strip()
        variant_count = default_variant_count
    if not name:
        raise ValueError("Task conditions must define a non-empty condition name.")
    return name, max(variant_count, 1)


def _deterministic_seed(*parts: object) -> int:
    payload = "::".join(str(part) for part in parts).encode("utf-8")
    digest = sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="little", signed=False)


def expand_task_set(task_config: dict[str, Any], max_trials: int | None = None) -> list[TrialSpec]:
    track = str(task_config["track"])
    task_name = str(task_config.get("name", track))
    catalog = _catalog_by_id(task_config)
    trials: list[TrialSpec] = []

    for group in task_config.get("task_groups", []):
        group_name = str(group["name"])
        object_group = str(group["object_group"])
        template = str(group["instruction_template"])
        attempts_per_trial = int(group.get("attempts_per_trial", 1))
        default_variant_count = int(group.get("replicates", group.get("variant_count", 1)))
        object_ids = list(group.get("object_ids") or catalog.get(object_group, {}).keys())

        for condition in group.get("conditions", []):
            condition_name, variant_count = _condition_variants(condition, default_variant_count)
            for index, object_id in enumerate(object_ids, start=1):
                object_meta = catalog.get(object_group, {}).get(str(object_id))
                if object_meta is None:
                    object_meta = {
                        "id": str(object_id),
                        "label": str(object_id).replace("_", " "),
                    }
                object_label = object_meta["label"]
                instruction = template.format(object=object_label)
                scene_base = f"{group_name}__{condition_name}__{index:03d}"
                for replicate_index in range(1, variant_count + 1):
                    scene_id = scene_base if variant_count == 1 else f"{scene_base}__r{replicate_index:02d}"
                    trials.append(
                        TrialSpec(
                            track=track,
                            task=group_name,
                            scene_id=scene_id,
                            scene_recipe_id=scene_base,
                            object_id=object_meta["id"],
                            object_label=object_label,
                            object_group=object_group,
                            condition=condition_name,
                            instruction=instruction,
                            attempts_per_trial=attempts_per_trial,
                            replicate_index=replicate_index,
                            seed=_deterministic_seed(task_name, group_name, condition_name, object_meta["id"], replicate_index),
                        )
                    )
                    if max_trials is not None and len(trials) >= max_trials:
                        return trials
    return trials
