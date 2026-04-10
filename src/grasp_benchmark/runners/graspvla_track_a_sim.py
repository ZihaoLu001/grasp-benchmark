from __future__ import annotations

import json
import math
import os
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grasp_benchmark.adapters import build_adapter
from grasp_benchmark.adapters.base import AdapterExecutionError, AgentAdapter
from grasp_benchmark.adapters.modular_components import method_tier as resolve_method_tier
from grasp_benchmark.config import load_named_config
from grasp_benchmark.paths import PROJECT_ROOT, ensure_dir
from grasp_benchmark.task_specs import TrialSpec
from grasp_benchmark.types import EpisodeResult, Observation


@dataclass(frozen=True, slots=True)
class SceneObject:
    object_id: str
    object_label: str
    category_name: str
    source_family: str
    source_asset: str
    instance_name: str
    region_name: str
    rotation_axis: str
    rotation: tuple[float, float]
    material_override: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SceneRecipe:
    scene_id: str
    task: str
    condition: str
    seed: int
    instruction: str
    scene_properties: dict[str, Any]
    objects: tuple[SceneObject, ...]
    target_instance_names: tuple[str, ...]
    success_instance_names: tuple[str, ...]
    height_offset_cm: float
    max_steps: int
    stabilization_steps: int
    hold_steps: int

    def to_json(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "task": self.task,
            "condition": self.condition,
            "seed": self.seed,
            "instruction": self.instruction,
            "scene_properties": self.scene_properties,
            "objects": [
                {
                    "object_id": obj.object_id,
                    "object_label": obj.object_label,
                    "category_name": obj.category_name,
                    "source_family": obj.source_family,
                    "source_asset": obj.source_asset,
                    "instance_name": obj.instance_name,
                    "region_name": obj.region_name,
                    "rotation_axis": obj.rotation_axis,
                    "rotation": list(obj.rotation),
                    "material_override": obj.material_override or {},
                }
                for obj in self.objects
            ],
            "target_instance_names": list(self.target_instance_names),
            "success_instance_names": list(self.success_instance_names),
            "height_offset_cm": self.height_offset_cm,
            "max_steps": self.max_steps,
            "stabilization_steps": self.stabilization_steps,
            "hold_steps": self.hold_steps,
        }


def _playground_root() -> Path:
    return PROJECT_ROOT / "third_party" / "upstreams" / "GraspVLA-playground"


def _ensure_playground_imports(playground_root: Path) -> None:
    playground_path = str(playground_root)
    robosuite_path = str(playground_root / "third_party" / "robosuite")
    curobo_path = str(PROJECT_ROOT / "third_party" / "upstreams" / "curobo" / "src")
    if curobo_path not in sys.path:
        sys.path.insert(0, curobo_path)
    if robosuite_path not in sys.path:
        sys.path.insert(0, robosuite_path)
    if playground_path not in sys.path:
        sys.path.insert(0, playground_path)
    # Some playground assets are still resolved via cwd-relative paths during import time.
    if playground_root.exists():
        os.chdir(playground_root)


def _load_scene_config(method_config: dict[str, Any], task_config: dict[str, Any] | None = None) -> dict[str, Any]:
    task_name = str((task_config or {}).get("name", ""))
    scene_catalog_overrides = method_config.get("sim", {}).get("scene_catalog_by_task_set", {})
    scene_name = str(
        (task_config or {}).get("scene_catalog")
        or scene_catalog_overrides.get(task_name)
        or method_config.get("sim", {}).get("scene_catalog", "graspvla_track_a_playground_v1")
    )
    return load_named_config("scenes", scene_name)


def _asset_key(object_id: str, task: str, scene_config: dict[str, Any]) -> dict[str, Any]:
    if task == "arbitrary_grasping_transparent":
        return dict(scene_config["transparent_objects"][object_id])
    return dict(scene_config["core_objects"][object_id])


def _seed_for_trial(scene_config: dict[str, Any], trial: TrialSpec, scene_index: int) -> int:
    if trial.task == "arbitrary_grasping_transparent":
        return int(scene_config["seed_base"]["transparent"]) + scene_index
    return int(scene_config["seed_base"][trial.condition]) + scene_index


def _build_core_distractors(scene_config: dict[str, Any], target_object_id: str, count: int) -> list[str]:
    distractors = [item for item in scene_config.get("distractor_priority", []) if item != target_object_id]
    return distractors[:count]


def _build_transparent_scene_objects(scene_config: dict[str, Any], focus_object_id: str) -> tuple[SceneObject, ...]:
    ordered = [focus_object_id] + [
        item for item in scene_config.get("transparent_distractor_priority", []) if item != focus_object_id
    ]
    region_names = ["target_center", "clutter_left", "clutter_right", "clutter_back"]
    objects: list[SceneObject] = []
    for index, object_id in enumerate(ordered):
        spec = _asset_key(object_id, "arbitrary_grasping_transparent", scene_config)
        objects.append(
            SceneObject(
                object_id=object_id,
                object_label=object_id.replace("_", " "),
                category_name=str(spec["category_name"]),
                source_family=str(spec["source_family"]),
                source_asset=str(spec["source_asset"]),
                instance_name=f"{object_id}_1",
                region_name=region_names[index],
                rotation_axis=str(spec["rotation_axis"]),
                rotation=(float(spec["rotation"][0]), float(spec["rotation"][1])),
                material_override=dict(spec.get("material_override") or {}),
            )
        )
    return tuple(objects)


def _build_opaque_scene_objects(scene_config: dict[str, Any], focus_object_id: str) -> tuple[SceneObject, ...]:
    ordered = [focus_object_id] + [
        item for item in scene_config.get("opaque_distractor_priority", scene_config.get("distractor_priority", []))
        if item != focus_object_id
    ]
    ordered = ordered[:4]
    region_names = ["target_center", "clutter_left", "clutter_right", "clutter_back"]
    objects: list[SceneObject] = []
    for index, object_id in enumerate(ordered):
        spec = _asset_key(object_id, "arbitrary_grasping_common_opaque", scene_config)
        objects.append(
            SceneObject(
                object_id=object_id,
                object_label=object_id.replace("_", " "),
                category_name=str(spec["category_name"]),
                source_family=str(spec["source_family"]),
                source_asset=str(spec["source_asset"]),
                instance_name=f"{object_id}_1",
                region_name=region_names[index],
                rotation_axis=str(spec["rotation_axis"]),
                rotation=(float(spec["rotation"][0]), float(spec["rotation"][1])),
                material_override=dict(spec.get("material_override") or {}),
            )
        )
    return tuple(objects)


def build_scene_catalog(task_specs: list[TrialSpec], scene_config: dict[str, Any]) -> dict[str, SceneRecipe]:
    recipes: dict[str, SceneRecipe] = {}
    for index, trial in enumerate(task_specs, start=1):
        if trial.task == "arbitrary_grasping_transparent":
            objects = _build_transparent_scene_objects(scene_config, trial.object_id)
            transparent_scene = scene_config["transparent_scene"]
            recipe = SceneRecipe(
                scene_id=trial.scene_id,
                task=trial.task,
                condition=trial.condition,
                seed=_seed_for_trial(scene_config, trial, index),
                instruction=trial.instruction,
                scene_properties=dict(transparent_scene["scene_properties"]),
                objects=objects,
                target_instance_names=(objects[0].instance_name,),
                success_instance_names=tuple(obj.instance_name for obj in objects),
                height_offset_cm=float(transparent_scene.get("height_offset_cm", 0.0)),
                max_steps=int(scene_config["max_steps"]),
                stabilization_steps=int(scene_config["stabilization_steps"]),
                hold_steps=int(scene_config["hold_steps"]),
            )
        elif trial.task == "arbitrary_grasping_common_opaque":
            objects = _build_opaque_scene_objects(scene_config, trial.object_id)
            opaque_scene = scene_config["opaque_scene"]
            recipe = SceneRecipe(
                scene_id=trial.scene_id,
                task=trial.task,
                condition=trial.condition,
                seed=_seed_for_trial(scene_config, trial, index),
                instruction=trial.instruction,
                scene_properties=dict(opaque_scene["scene_properties"]),
                objects=objects,
                target_instance_names=(objects[0].instance_name,),
                success_instance_names=tuple(obj.instance_name for obj in objects),
                height_offset_cm=float(opaque_scene.get("height_offset_cm", 0.0)),
                max_steps=int(scene_config["max_steps"]),
                stabilization_steps=int(scene_config["stabilization_steps"]),
                hold_steps=int(scene_config["hold_steps"]),
            )
        else:
            condition_cfg = scene_config["conditions"][trial.condition]
            target_spec = _asset_key(trial.object_id, trial.task, scene_config)
            objects = [
                SceneObject(
                    object_id=trial.object_id,
                    object_label=trial.object_label,
                    category_name=str(target_spec["category_name"]),
                    source_family=str(target_spec["source_family"]),
                    source_asset=str(target_spec["source_asset"]),
                    instance_name=f"{trial.object_id}_1",
                    region_name="target_center",
                    rotation_axis=str(target_spec["rotation_axis"]),
                    rotation=(float(target_spec["rotation"][0]), float(target_spec["rotation"][1])),
                    material_override=dict(target_spec.get("material_override") or {}),
                )
            ]
            for distractor_index, distractor_id in enumerate(
                _build_core_distractors(scene_config, trial.object_id, int(condition_cfg.get("distractor_count", 0))),
                start=1,
            ):
                distractor_spec = _asset_key(distractor_id, trial.task, scene_config)
                region_name = ("clutter_left", "clutter_right", "clutter_back")[distractor_index - 1]
                objects.append(
                    SceneObject(
                        object_id=distractor_id,
                        object_label=distractor_id.replace("_", " "),
                        category_name=str(distractor_spec["category_name"]),
                        source_family=str(distractor_spec["source_family"]),
                        source_asset=str(distractor_spec["source_asset"]),
                        instance_name=f"{distractor_id}_1",
                        region_name=region_name,
                        rotation_axis=str(distractor_spec["rotation_axis"]),
                        rotation=(float(distractor_spec["rotation"][0]), float(distractor_spec["rotation"][1])),
                        material_override=dict(distractor_spec.get("material_override") or {}),
                    )
                )
            recipe = SceneRecipe(
                scene_id=trial.scene_id,
                task=trial.task,
                condition=trial.condition,
                seed=_seed_for_trial(scene_config, trial, index),
                instruction=trial.instruction,
                scene_properties=dict(condition_cfg["scene_properties"]),
                objects=tuple(objects),
                target_instance_names=(objects[0].instance_name,),
                success_instance_names=(objects[0].instance_name,),
                height_offset_cm=float(condition_cfg.get("height_offset_cm", 0.0)),
                max_steps=int(scene_config["max_steps"]),
                stabilization_steps=int(scene_config["stabilization_steps"]),
                hold_steps=int(scene_config["hold_steps"]),
            )
        recipes[trial.scene_id] = recipe
    return recipes


def _camel_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def _source_asset_dir(playground_root: Path, source_family: str, source_asset: str) -> Path:
    if source_family == "objaverse":
        return playground_root / "assets" / "playground_assets" / source_asset
    if source_family == "turbosquid":
        return playground_root / "libero" / "libero" / "assets" / "turbosquid_objects" / source_asset
    if source_family == "stable_scanned":
        return playground_root / "libero" / "libero" / "assets" / "stable_scanned_objects" / source_asset
    raise KeyError(f"Unknown source family: {source_family}")


def _patch_materials(xml_path: Path, material_override: dict[str, Any]) -> None:
    if not material_override:
        return
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for material in root.findall(".//material"):
        for key, value in material_override.items():
            if isinstance(value, (list, tuple)):
                material.set(key, " ".join(str(item) for item in value))
            else:
                material.set(key, str(value))
    tree.write(xml_path, encoding="utf-8")


def _register_runtime_category(
    *,
    category_name: str,
    xml_path: Path,
    rotation_axis: str,
    rotation: tuple[float, float],
) -> None:
    from libero.libero.envs.base_object import OBJECTS_DICT, register_object
    from robosuite.models.objects import MujocoXMLObject

    if category_name in OBJECTS_DICT:
        return

    class_name = _camel_case(category_name)

    def __init__(self, name: str = category_name, joints: list[dict[str, str]] | None = None) -> None:
        if joints is None:
            joints = [dict(type="free", damping="0.0005")]
        MujocoXMLObject.__init__(
            self,
            str(xml_path),
            name=name,
            joints=joints,
            obj_type="all",
            duplicate_collision_geoms=False,
        )
        self.category_name = category_name
        self.rotation = rotation
        self.rotation_axis = rotation_axis
        self.object_properties = {"vis_site_names": {}}

    cls = type(class_name, (MujocoXMLObject,), {"__init__": __init__, "__module__": __name__})
    register_object(cls)


def prepare_runtime_assets(
    *,
    playground_root: Path,
    recipes: dict[str, SceneRecipe],
    runtime_root: Path,
) -> dict[str, dict[str, Any]]:
    ensure_dir(runtime_root)
    alias_map: dict[str, dict[str, Any]] = {}
    for recipe in recipes.values():
        for obj in recipe.objects:
            alias_map[obj.object_id] = {
                "category_name": obj.category_name,
                "source_family": obj.source_family,
                "source_asset": obj.source_asset,
            }
            if not obj.material_override:
                continue
            dest_dir = runtime_root / obj.category_name
            if not dest_dir.exists():
                shutil.copytree(_source_asset_dir(playground_root, obj.source_family, obj.source_asset), dest_dir)
                _patch_materials(dest_dir / f"{obj.source_asset}.xml", obj.material_override)
            _register_runtime_category(
                category_name=obj.category_name,
                xml_path=dest_dir / f"{obj.source_asset}.xml",
                rotation_axis=obj.rotation_axis,
                rotation=obj.rotation,
            )
    return alias_map


def build_scene_catalog_metadata(
    *,
    method_config: dict[str, Any],
    task_config: dict[str, Any] | None,
    task_specs: list[TrialSpec],
    runtime_root: Path,
) -> tuple[dict[str, SceneRecipe], dict[str, dict[str, Any]], dict[str, Any]]:
    scene_config = _load_scene_config(method_config, task_config)
    playground_root = _playground_root()
    _ensure_playground_imports(playground_root)
    recipes = build_scene_catalog(task_specs, scene_config)
    alias_map = prepare_runtime_assets(
        playground_root=playground_root,
        recipes=recipes,
        runtime_root=runtime_root,
    )
    metadata = {
        "scene_catalog_name": str(scene_config["name"]),
        "scene_backend": str(scene_config["scene_backend"]),
        "scene_catalog": {scene_id: recipe.to_json() for scene_id, recipe in recipes.items()},
        "alias_map": alias_map,
        "robot_config_path": str(PROJECT_ROOT / str(scene_config["robot_config_relpath"])),
    }
    return recipes, alias_map, metadata


def write_bddl_for_recipe(recipe: SceneRecipe, scene_config: dict[str, Any], destination: Path) -> None:
    region_lines = []
    for region_name, ranges in scene_config["regions"].items():
        ranges_text = "\n".join(
            f"                ({r[0]} {r[1]} {r[2]} {r[3]})" for r in ranges
        )
        region_lines.append(
            "\n".join(
                [
                    f"        ({region_name}",
                    "            (:target floor)",
                    "            (:ranges (",
                    ranges_text,
                    "                )",
                    "            )",
                    "        )",
                ]
            )
        )
    object_lines = [f"    {obj.instance_name} - {obj.category_name}" for obj in recipe.objects]
    init_lines = [f"    (On {obj.instance_name} {obj.region_name})" for obj in recipe.objects]
    interest_lines = [f"        {name}" for name in recipe.target_instance_names]
    goal_target = recipe.target_instance_names[0]
    content = "\n".join(
        [
            "(define (problem LIBERO_Floor_Manipulation)",
            "    (:domain robosuite)",
            f"    (:language {recipe.instruction})",
            "    (:regions",
            *region_lines,
            "    )",
            "",
            "    (:fixtures",
            "        floor - floor",
            "    )",
            "",
            "    (:objects",
            *object_lines,
            "    )",
            "",
            "    (:obj_of_interest",
            *interest_lines,
            "    )",
            "",
            "    (:init",
            *init_lines,
            "    )",
            "",
            "    (:goal",
            f"        (And (Grasped {goal_target}))",
            "    )",
            ")",
            "",
        ]
    )
    destination.write_text(content, encoding="utf-8")


class SharedFrankaKinematics:
    def __init__(self, robot_config_path: Path) -> None:
        import torch
        import transforms3d as transforms3d_module
        import curobo.util_file
        from curobo.types.base import TensorDeviceType
        from curobo.types.math import Pose
        from curobo.wrap.reacher.ik_solver import IKSolver

        self._torch = torch
        self._transforms3d = transforms3d_module
        self._Pose = Pose
        robot_cfg = curobo.util_file.load_yaml(str(robot_config_path))["robot_cfg"]
        self._ik_solver = IKSolver(IKSolver.load_from_robot_config(robot_cfg, None, TensorDeviceType()))

    def solve(self, abs_eef_action: Any, current_joint: Any) -> Any:
        ee_position = self._torch.tensor(abs_eef_action[:3]).cuda().float()
        ee_quat = self._transforms3d.euler.euler2quat(
            float(abs_eef_action[3]),
            float(abs_eef_action[4]),
            float(abs_eef_action[5]),
        )
        ee_quaternion = self._torch.tensor(ee_quat).cuda().float()
        goal = self._Pose(ee_position, ee_quaternion)
        retract_cfg = self._torch.tensor(current_joint).cuda().float()
        seed_cfg = self._torch.tensor(current_joint).float().unsqueeze(0).repeat(64, 1).cuda().unsqueeze(0)
        result = self._ik_solver.solve_single(goal, retract_cfg, seed_cfg)
        if not result.success[0][0]:
            return current_joint
        return result.solution[result.success][0].cpu().numpy()

    def fk(self, current_joint: Any) -> tuple[Any, Any]:
        current_joint_states = self._torch.tensor(current_joint).reshape(1, 7).cuda().float()
        current_eef_states = self._ik_solver.fk(current_joint_states)
        position = current_eef_states.ee_position[0].cpu().numpy()
        quaternion = current_eef_states.ee_quaternion[0].cpu().numpy()
        return position, quaternion


class SharedTrackARemoteAgent:
    PROPRIO_HISTORY_SIZE = 4
    GRIPPER_OPEN = 1.0
    GRIP_TRANSITION_ACTIONS = 4

    def __init__(self, *, instruction: str, host: str, port: int, kinematics: SharedFrankaKinematics) -> None:
        import numpy as np
        import transforms3d as t3d
        import zmq

        self._instruction = instruction
        self._kinematics = kinematics
        self._np = np
        self._t3d = t3d
        self._last_gripper = self.GRIPPER_OPEN
        self._proprio_history: list[np.ndarray] = []
        self._pred_actions: list[tuple[np.ndarray, Any]] = []
        self._request_latencies_ms: list[float] = []
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.setsockopt(zmq.RCVTIMEO, 10000)
        self._socket.setsockopt(zmq.SNDTIMEO, 10000)
        self._socket.connect(f"tcp://{host}:{port}")

    def reset(self, instruction: str | dict[str, Any]) -> None:
        if isinstance(instruction, dict):
            self._instruction = str(instruction.get("instruction", self._instruction))
        else:
            self._instruction = instruction
        self._last_gripper = self.GRIPPER_OPEN
        self._proprio_history = []
        self._pred_actions = []
        self._request_latencies_ms = []

    @property
    def mean_inference_ms(self) -> float:
        if not self._request_latencies_ms:
            return 0.0
        return round(sum(self._request_latencies_ms) / len(self._request_latencies_ms), 4)

    def _current_proprio(self, obs: dict[str, Any]) -> np.ndarray:
        current_joint_pos = self._np.asarray(obs["robot0_joint_pos"], dtype=self._np.float32)
        position, quaternion = self._kinematics.fk(current_joint_pos)
        euler = self._np.asarray(self._t3d.euler.quat2euler(quaternion, axes="sxyz"), dtype=self._np.float32)
        return self._np.concatenate(
            [
                position.astype(self._np.float32),
                euler,
                self._np.array([self._last_gripper], dtype=self._np.float32),
            ]
        )

    def _build_observation(self, obs: dict[str, Any], camera_meta: dict[str, Any]) -> Observation:
        current_proprio = self._current_proprio(obs)
        self._proprio_history.append(current_proprio)
        while len(self._proprio_history) < self.PROPRIO_HISTORY_SIZE:
            self._proprio_history.append(self._proprio_history[-1].copy())
        self._proprio_history = self._proprio_history[-self.PROPRIO_HISTORY_SIZE :]
        rgb_front = self._np.asarray(obs["front_view_image"][::-1]).copy()
        rgb_side = self._np.asarray(obs["side_view_image"][::-1]).copy()
        front_depth_frame = obs.get("front_view_depth")
        side_depth_frame = obs.get("side_view_depth")
        if front_depth_frame is None:
            front_depth = self._np.zeros(rgb_front.shape[:2], dtype=self._np.float32)
        else:
            front_depth = _depth_to_metric(
                self._np.asarray(front_depth_frame[::-1]).squeeze(-1),
                camera_meta,
                self._np,
            )
        if side_depth_frame is None:
            side_depth = self._np.zeros(rgb_side.shape[:2], dtype=self._np.float32)
        else:
            side_depth = _depth_to_metric(
                self._np.asarray(side_depth_frame[::-1]).squeeze(-1),
                camera_meta,
                self._np,
            )
        return Observation(
            rgb_front=rgb_front,
            rgb_side=rgb_side,
            depth_front=front_depth,
            depth_side=side_depth,
            intrinsics_front=dict(camera_meta["intrinsics_front"]),
            intrinsics_side=dict(camera_meta["intrinsics_side"]),
            extrinsics_front=dict(camera_meta["extrinsics_front"]),
            extrinsics_side=dict(camera_meta["extrinsics_side"]),
            proprio={
                "state": self._proprio_history[-1].tolist(),
                "history": [item.tolist() for item in self._proprio_history],
                "gripper": int(self._last_gripper),
                "robot_base_pose_world": camera_meta.get("robot_base_pose_world"),
            },
            instruction=self._instruction,
            timestamp=time.time(),
        )

    def _delta_to_abs(self, delta_action: Any, current_pose: Any) -> Any:
        current_rot = self._t3d.euler.euler2mat(*current_pose[3:6])
        next_rot = self._t3d.euler.euler2mat(*delta_action[3:6]) @ current_rot
        next_trans = current_pose[:3] + delta_action[:3]
        return self._np.concatenate(
            [
                next_trans,
                self._np.asarray(self._t3d.euler.mat2euler(next_rot), dtype=self._np.float32),
                [delta_action[6]],
            ]
        )

    def _post_and_get(self, observation: Observation) -> None:
        request = {
            "front_view_image": [observation.rgb_front],
            "side_view_image": [observation.rgb_side],
            "proprio_array": [
                self._np.asarray(item, dtype=self._np.float32) for item in observation.proprio["history"]
            ],
            "text": observation.instruction,
        }
        start = time.perf_counter()
        self._socket.send_pyobj(request)
        response = self._socket.recv_pyobj()
        self._request_latencies_ms.append((time.perf_counter() - start) * 1000.0)
        if not isinstance(response, dict) or not response.get("result"):
            raise AdapterExecutionError(
                f"Unexpected GraspVLA response: {response!r}",
                failure_stage="policy_execution",
            )
        bbox = response.get("debug", {}).get("bbox")
        last_finger_state = self._last_gripper
        current_pose = self._np.asarray(observation.proprio["history"][-1][:6], dtype=self._np.float32)
        for delta_action in response["result"]:
            delta = self._np.asarray(delta_action, dtype=self._np.float32)
            abs_action = self._delta_to_abs(delta, current_pose)
            current_pose = abs_action[:6]
            if abs_action[6] == 0 or abs_action[6] == last_finger_state:
                self._pred_actions.append((abs_action, bbox))
            else:
                arm_only = self._np.copy(abs_action)
                arm_only[6] = 0
                self._pred_actions.append((arm_only, bbox))
                for _ in range(self.GRIP_TRANSITION_ACTIONS):
                    self._pred_actions.append((self._np.copy(abs_action), bbox))
                self._last_gripper = float(abs_action[6])
            last_finger_state = float(abs_action[6]) if abs_action[6] != 0 else last_finger_state

    def current_open_action(self, obs: dict[str, Any]) -> Any:
        proprio = self._current_proprio(obs)
        action = proprio.copy()
        action[-1] = -1.0
        return action

    def step(self, obs: dict[str, Any], camera_meta: dict[str, Any]) -> tuple[Any, Any, dict[str, Any]]:
        observation = self._build_observation(obs, camera_meta)
        if not self._pred_actions:
            self._post_and_get(observation)
        action, bbox = self._pred_actions.pop(0)
        action = action.copy()
        action[6] = -action[6]
        return action, bbox, {"bbox": bbox, "policy": "graspvla_remote_sequence"}

    def close(self) -> None:
        self._socket.close(linger=0)
        self._context.term()


class SharedTrackAAdapterAgent:
    PROPRIO_HISTORY_SIZE = 4
    GRIPPER_OPEN = 1.0

    def __init__(
        self,
        *,
        adapter: AgentAdapter,
        instruction: str,
        kinematics: SharedFrankaKinematics,
        runtime_config: dict[str, Any],
    ) -> None:
        import numpy as np
        import transforms3d as t3d

        self._adapter = adapter
        self._instruction = instruction
        self._kinematics = kinematics
        self._np = np
        self._t3d = t3d
        self._last_gripper = self.GRIPPER_OPEN
        self._command_pose: np.ndarray | None = None
        self._proprio_history: list[np.ndarray] = []
        self._request_latencies_ms: list[float] = []
        self._adapter.setup(runtime_config)

    def reset(self, task_spec: dict[str, Any]) -> None:
        self._instruction = str(task_spec.get("instruction", self._instruction))
        self._last_gripper = self.GRIPPER_OPEN
        self._command_pose = None
        self._proprio_history = []
        self._request_latencies_ms = []
        self._adapter.reset(task_spec)

    @property
    def mean_inference_ms(self) -> float:
        if not self._request_latencies_ms:
            return 0.0
        return round(sum(self._request_latencies_ms) / len(self._request_latencies_ms), 4)

    def _current_proprio(self, obs: dict[str, Any]) -> np.ndarray:
        current_joint_pos = self._np.asarray(obs["robot0_joint_pos"], dtype=self._np.float32)
        position, quaternion = self._kinematics.fk(current_joint_pos)
        import transforms3d as t3d

        euler = self._np.asarray(t3d.euler.quat2euler(quaternion, axes="sxyz"), dtype=self._np.float32)
        return self._np.concatenate(
            [
                position.astype(self._np.float32),
                euler,
                self._np.array([self._last_gripper], dtype=self._np.float32),
            ]
        )

    def _build_observation(self, obs: dict[str, Any], camera_meta: dict[str, Any]) -> Observation:
        current_proprio = self._current_proprio(obs)
        self._proprio_history.append(current_proprio)
        while len(self._proprio_history) < self.PROPRIO_HISTORY_SIZE:
            self._proprio_history.append(self._proprio_history[-1].copy())
        self._proprio_history = self._proprio_history[-self.PROPRIO_HISTORY_SIZE :]
        rgb_front = self._np.asarray(obs["front_view_image"][::-1]).copy()
        rgb_side = self._np.asarray(obs["side_view_image"][::-1]).copy()
        front_depth_frame = obs.get("front_view_depth")
        side_depth_frame = obs.get("side_view_depth")
        if front_depth_frame is None:
            front_depth = self._np.zeros(rgb_front.shape[:2], dtype=self._np.float32)
        else:
            front_depth = _depth_to_metric(
                self._np.asarray(front_depth_frame[::-1]).squeeze(-1),
                camera_meta,
                self._np,
            )
        if side_depth_frame is None:
            side_depth = self._np.zeros(rgb_side.shape[:2], dtype=self._np.float32)
        else:
            side_depth = _depth_to_metric(
                self._np.asarray(side_depth_frame[::-1]).squeeze(-1),
                camera_meta,
                self._np,
            )
        return Observation(
            rgb_front=rgb_front,
            rgb_side=rgb_side,
            depth_front=front_depth,
            depth_side=side_depth,
            intrinsics_front=dict(camera_meta["intrinsics_front"]),
            intrinsics_side=dict(camera_meta["intrinsics_side"]),
            extrinsics_front=dict(camera_meta["extrinsics_front"]),
            extrinsics_side=dict(camera_meta["extrinsics_side"]),
            proprio={
                "state": self._proprio_history[-1].tolist(),
                "history": [item.tolist() for item in self._proprio_history],
                "gripper": int(self._last_gripper),
                "robot_base_pose_world": camera_meta.get("robot_base_pose_world"),
            },
            instruction=self._instruction,
            timestamp=time.time(),
        )

    def current_open_action(self, obs: dict[str, Any]) -> Any:
        proprio = self._current_proprio(obs)
        action = proprio.copy()
        action[-1] = -1.0
        return action

    def _delta_to_abs(self, delta_action: Any, current_pose: Any) -> Any:
        current_rot = self._t3d.euler.euler2mat(*current_pose[3:6])
        next_rot = self._t3d.euler.euler2mat(*delta_action[3:6]) @ current_rot
        next_trans = current_pose[:3] + delta_action[:3]
        return self._np.concatenate(
            [
                next_trans,
                self._np.asarray(self._t3d.euler.mat2euler(next_rot), dtype=self._np.float32),
                [delta_action[6]],
            ]
        )

    def step(self, obs: dict[str, Any], camera_meta: dict[str, Any]) -> tuple[Any, Any, dict[str, Any]]:
        observation = self._build_observation(obs, camera_meta)
        current_pose = self._np.asarray(observation.proprio["history"][-1][:6], dtype=self._np.float32)
        had_pending_actions = bool(getattr(self._adapter, "_pending_actions", []))
        start = time.perf_counter()
        try:
            action = self._adapter.step(observation)
        finally:
            self._request_latencies_ms.append((time.perf_counter() - start) * 1000.0)
        if not had_pending_actions or self._command_pose is None:
            self._command_pose = current_pose.copy()
        delta_action = self._np.concatenate(
            [self._np.asarray(action.ee_delta, dtype=self._np.float32), [float(action.gripper)]]
        )
        abs_action = self._delta_to_abs(delta_action, self._command_pose)
        self._command_pose = abs_action[:6].copy()
        if abs_action[6] < 0:
            self._last_gripper = -1.0
        elif abs_action[6] > 0:
            self._last_gripper = 1.0
        env_action = abs_action.copy()
        env_action[6] = -env_action[6]
        return env_action, None, {
            "policy": self._adapter.name,
            "gripper_command": int(action.gripper),
            "attempt_complete": self.attempt_complete(),
        }

    def attempt_complete(self) -> bool:
        return bool(self._adapter.attempt_complete())

    def close(self) -> None:
        self._adapter.close()


def _camera_metadata(env: Any, scene_config: dict[str, Any]) -> dict[str, Any]:
    from robosuite.utils.camera_utils import get_camera_extrinsic_matrix, get_camera_intrinsic_matrix

    front_name = str(scene_config["camera_names"]["front"])
    side_name = str(scene_config["camera_names"]["side"])
    height = 256
    width = 256
    front_K = get_camera_intrinsic_matrix(env.sim, front_name, height, width)
    side_K = get_camera_intrinsic_matrix(env.sim, side_name, height, width)
    extent = float(env.sim.model.stat.extent)
    far = float(env.sim.model.vis.map.zfar) * extent
    near = float(env.sim.model.vis.map.znear) * extent
    root_body = env.robots[0].robot_model.root_body
    base_pos = env.sim.data.get_body_xpos(root_body)
    base_rot = env.sim.data.get_body_xmat(root_body).reshape(3, 3)
    base_pose_world = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    for row in range(3):
        for col in range(3):
            base_pose_world[row][col] = float(base_rot[row, col])
        base_pose_world[row][3] = float(base_pos[row])
    return {
        "intrinsics_front": {
            "fx": float(front_K[0, 0]),
            "fy": float(front_K[1, 1]),
            "cx": float(front_K[0, 2]),
            "cy": float(front_K[1, 2]),
            "matrix": front_K.tolist(),
        },
        "intrinsics_side": {
            "fx": float(side_K[0, 0]),
            "fy": float(side_K[1, 1]),
            "cx": float(side_K[0, 2]),
            "cy": float(side_K[1, 2]),
            "matrix": side_K.tolist(),
        },
        "extrinsics_front": {"matrix": get_camera_extrinsic_matrix(env.sim, front_name).tolist()},
        "extrinsics_side": {"matrix": get_camera_extrinsic_matrix(env.sim, side_name).tolist()},
        "robot_base_pose_world": base_pose_world,
        "depth_near_m": near,
        "depth_far_m": far,
    }


def _depth_to_metric(depth_map: Any, camera_meta: dict[str, Any], np_module: Any) -> Any:
    depth = np_module.asarray(depth_map, dtype=np_module.float32).copy()
    if depth.size == 0:
        return depth
    min_depth = float(np_module.min(depth))
    max_depth = float(np_module.max(depth))
    if min_depth < 0.0 or max_depth > 1.0 + 1e-6:
        return depth
    near = float(camera_meta.get("depth_near_m", 0.0))
    far = float(camera_meta.get("depth_far_m", 0.0))
    if near <= 0.0 or far <= near:
        return depth
    return near / (1.0 - depth * (1.0 - near / far))


def _eef_pose_from_obs(obs: dict[str, Any], np_module: Any) -> Any | None:
    eef_pos = obs.get("robot0_eef_pos")
    eef_quat = obs.get("robot0_eef_quat")
    if eef_pos is None or eef_quat is None:
        return None

    position = np_module.asarray(eef_pos, dtype=np_module.float32)
    quaternion = np_module.asarray(eef_quat, dtype=np_module.float32)
    if position.shape[0] != 3 or quaternion.shape[0] != 4:
        return None
    x, y, z, w = [float(value) for value in quaternion]
    t0 = 2.0 * (w * x + y * z)
    t1 = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(t0, t1)
    t2 = 2.0 * (w * y - z * x)
    t2 = max(-1.0, min(1.0, t2))
    pitch = math.asin(t2)
    t3 = 2.0 * (w * z + x * y)
    t4 = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(t3, t4)
    euler = np_module.asarray([roll, pitch, yaw], dtype=np_module.float32)
    return np_module.concatenate([position, euler])


def _refresh_obs(env: Any) -> dict[str, Any]:
    env.sim.forward()
    env.check_success()
    env._post_process()
    env._update_observables(force=True)
    return env.env._get_observations()


def _apply_height_offset(env: Any, instance_name: str, height_offset_cm: float) -> dict[str, Any]:
    if height_offset_cm <= 0:
        return env.env._get_observations()
    joint_name = f"{instance_name}_joint0"
    start, _end = env.sim.model.get_joint_qpos_addr(joint_name)
    env.sim.data.qpos[start + 2] += float(height_offset_cm) / 100.0
    return _refresh_obs(env)


def _stabilize_scene(env: Any, agent: SharedTrackARemoteAgent, obs: dict[str, Any], steps: int) -> dict[str, Any]:
    current_obs = obs
    for _ in range(steps):
        action = agent.current_open_action(current_obs)
        current_obs, _reward, _done, _info = env.step(action)
    return current_obs


def _attempt_payload(
    *,
    trial: TrialSpec,
    recipe: SceneRecipe,
    attempt: int,
    success: bool,
    baseline_z: dict[str, float],
    final_z: dict[str, float],
    lift_cm: float,
    hold_steps_reached: int,
    mean_inference_ms: float,
    video_path: str,
    alias_map: dict[str, dict[str, Any]],
    failure_stage: str = "",
    failure_reason: str = "",
    failure_traceback: str = "",
    step_trace: list[dict[str, Any]] | None = None,
    execution_mode: str = "shared_track_a_sim",
    shared_success_definition: dict[str, Any] | None = None,
    parent_run_id: str = "",
    shard_id: str = "",
    gpu_id: str = "",
    ) -> dict[str, Any]:
    return {
        "scene_id": trial.scene_id,
        "task": trial.task,
        "attempt": attempt,
        "instruction": trial.instruction,
        "success": success,
        "baseline_z": baseline_z,
        "final_z": final_z,
        "lift_cm": lift_cm,
        "hold_steps_reached": hold_steps_reached,
        "mean_inference_ms": mean_inference_ms,
        "video_path": video_path,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "failure_traceback": failure_traceback,
        "scene_recipe": recipe.to_json(),
        "alias_map": alias_map,
        "execution_mode": execution_mode,
        "shared_success_definition": dict(shared_success_definition or {}),
        "parent_run_id": parent_run_id,
        "shard_id": shard_id,
        "gpu_id": gpu_id,
        "step_trace": list(step_trace or []),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        try:
            return _json_safe(value.tolist())
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _target_instance_for_trial(recipe: SceneRecipe, trial: TrialSpec) -> str:
    if trial.task in {"arbitrary_grasping_transparent", "arbitrary_grasping_common_opaque"}:
        return recipe.success_instance_names[0]
    return recipe.target_instance_names[0]


def _build_shared_agent(
    *,
    method_name: str,
    method_config: dict[str, Any],
    sensor_config: dict[str, Any],
    trial: TrialSpec,
    kinematics: SharedFrankaKinematics,
    runtime_config: dict[str, Any],
) -> Any:
    if method_name == "graspvla":
        agent = SharedTrackARemoteAgent(
            instruction=trial.instruction,
            host=str(runtime_config["host"]),
            port=int(runtime_config["port"]),
            kinematics=kinematics,
        )
        agent.reset(trial.to_task_spec())
        return agent

    adapter = build_adapter(method_name, method_config, sensor_config)
    agent = SharedTrackAAdapterAgent(
        adapter=adapter,
        instruction=trial.instruction,
        kinematics=kinematics,
        runtime_config=runtime_config,
    )
    agent.reset(trial.to_task_spec())
    return agent


def _step_trace_entry(
    *,
    step_index: int,
    action: Any,
    bbox: Any,
    debug: dict[str, Any],
    ee_pose: Any,
    target_z: float,
    max_lift_cm: float,
    contact: bool,
    slip: bool,
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "ee_pose": [round(float(value), 6) for value in ee_pose],
        "gripper_command": round(float(action[6]), 6),
        "bbox": _json_safe(bbox),
        "target_z": round(float(target_z), 6),
        "max_lift_cm": round(float(max_lift_cm), 6),
        "contact": bool(contact),
        "slip": bool(slip),
        "debug": _json_safe(dict(debug or {})),
    }


def _run_shared_track_a_suite_once(
    *,
    method_name: str,
    method_config: dict[str, Any],
    task_config: dict[str, Any] | None,
    sensor_config: dict[str, Any],
    task_specs: list[TrialSpec],
    artifact_dir: Path,
    node: str,
    commit: str,
    runtime_config: dict[str, Any],
    execution_mode: str = "shared_track_a_sim",
    parent_run_id: str = "",
    shard_id: str = "",
    gpu_id: str = "",
    robot_config_override: str = "",
    lift_threshold_cm_override: float | None = None,
    hold_steps_override: int | None = None,
    trace_steps: bool = False,
) -> tuple[list[EpisodeResult], dict[str, Any]]:
    import numpy as np

    playground_root = _playground_root()
    _ensure_playground_imports(playground_root)
    previous_cwd = Path.cwd()
    os.chdir(playground_root)
    try:
        from grasp_benchmark.types import EpisodeResult
        from libero.libero.envs import OffScreenRenderEnv
        from misc.logger import VideoLogger

        scene_config = _load_scene_config(method_config, task_config)
        recipes, alias_map, metadata = build_scene_catalog_metadata(
            method_config=method_config,
            task_config=task_config,
            task_specs=task_specs,
            runtime_root=ensure_dir(artifact_dir / "runtime_assets"),
        )
        metadata["execution_mode"] = execution_mode
        metadata["method"] = method_name
        metadata["parent_run_id"] = parent_run_id
        metadata["shard_id"] = shard_id
        metadata["gpu_id"] = gpu_id
        (artifact_dir / "scene_catalog_resolved.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        bddl_root = ensure_dir(artifact_dir / "bddl")
        episodes_dir = ensure_dir(artifact_dir / "episodes")
        videos_dir = ensure_dir(artifact_dir / "videos")
        if robot_config_override:
            robot_config_path = PROJECT_ROOT / robot_config_override
        else:
            robot_config_path = PROJECT_ROOT / str(scene_config["robot_config_relpath"])
        lift_threshold_m = (
            float(lift_threshold_cm_override) / 100.0
            if lift_threshold_cm_override is not None
            else float(sensor_config["success_definition"]["lift_cm_min"]) / 100.0
        )
        hold_steps_required = int(hold_steps_override) if hold_steps_override is not None else int(scene_config["hold_steps"])
        results: list[EpisodeResult] = []
        control_freq = int(method_config.get("sim", {}).get("control_freq", 5))
        benchmark_method_tier = resolve_method_tier(method_config)
        shared_success_definition = {
            "lift_cm_min": round(lift_threshold_m * 100.0, 4),
            "hold_steps": hold_steps_required,
            "hold_s_min": round(hold_steps_required / control_freq, 4),
        }

        for trial in task_specs:
            recipe = recipes[trial.scene_id]
            cycle_start = time.perf_counter()
            result = None

            for attempt in range(1, trial.attempts_per_trial + 1):
                env = None
                agent = None
                video_logger = None
                step_trace: list[dict[str, Any]] = []
                try:
                    bddl_path = bddl_root / f"{trial.scene_id}_attempt{attempt:02d}.bddl"
                    write_bddl_for_recipe(recipe, scene_config, bddl_path)
                    env = OffScreenRenderEnv(
                        bddl_file_name=str(bddl_path),
                        camera_names=[scene_config["camera_names"]["front"], scene_config["camera_names"]["side"]],
                        camera_heights=256,
                        camera_widths=256,
                        camera_depths=True,
                        control_freq=control_freq,
                        controller="IK_POSE",
                        ignore_done=True,
                        scene_properties=recipe.scene_properties,
                    )
                    env.seed(recipe.seed)
                    obs = env.reset()
                    kinematics = SharedFrankaKinematics(robot_config_path)
                    env.robots[0].IK_solver = kinematics
                    camera_meta = _camera_metadata(env, scene_config)
                    agent = _build_shared_agent(
                        method_name=method_name,
                        method_config=method_config,
                        sensor_config=sensor_config,
                        trial=trial,
                        kinematics=kinematics,
                        runtime_config=runtime_config,
                    )
                    obs = _stabilize_scene(env, agent, obs, recipe.stabilization_steps)
                    if recipe.height_offset_cm > 0:
                        obs = _apply_height_offset(env, recipe.target_instance_names[0], recipe.height_offset_cm)
                    baseline_z = {
                        instance_name: float(np.asarray(obs[f"{instance_name}_pos"])[2])
                        for instance_name in recipe.success_instance_names
                    }
                    final_z = dict(baseline_z)
                    target_instance_name = _target_instance_for_trial(recipe, trial)
                    hold_counts = {instance_name: 0 for instance_name in recipe.success_instance_names}
                    video_logger = VideoLogger(str(videos_dir))
                    video_logger.start_recording(
                        trial.task,
                        f"{trial.scene_id}_attempt{attempt:02d}",
                        trial.object_id,
                        recipe.seed,
                    )
                    max_lift_cm_so_far = 0.0
                    attempt_complete_early = False

                    for _step in range(recipe.max_steps):
                        action, bbox, debug = agent.step(obs, camera_meta)
                        obs, _reward, _done, _info = env.step(action)
                        video_logger.log_frame(obs, bbox)
                        winner = ""
                        for instance_name in recipe.success_instance_names:
                            current_z = float(np.asarray(obs[f"{instance_name}_pos"])[2])
                            final_z[instance_name] = current_z
                            if current_z - baseline_z[instance_name] >= lift_threshold_m:
                                hold_counts[instance_name] += 1
                                if hold_counts[instance_name] >= hold_steps_required:
                                    winner = instance_name
                                    break
                            else:
                                hold_counts[instance_name] = 0
                        target_z = float(np.asarray(obs[f"{target_instance_name}_pos"])[2])
                        target_lift_cm = (target_z - baseline_z[target_instance_name]) * 100.0
                        max_lift_cm_so_far = max(max_lift_cm_so_far, target_lift_cm)
                        if trace_steps:
                            eef_pose = _eef_pose_from_obs(obs, np)
                            if eef_pose is None:
                                ee_position, ee_quaternion = kinematics.fk(
                                    np.asarray(obs["robot0_joint_pos"], dtype=np.float32)
                                )
                                import transforms3d as t3d

                                ee_euler = np.asarray(t3d.euler.quat2euler(ee_quaternion, axes="sxyz"), dtype=np.float32)
                                ee_pose = np.concatenate([ee_position, ee_euler])
                            else:
                                ee_pose = eef_pose
                            current_contacts = int(getattr(env.sim.data, "ncon", 0))
                            slip = target_lift_cm + 0.5 < max_lift_cm_so_far
                            step_trace.append(
                                _step_trace_entry(
                                    step_index=_step,
                                    action=action,
                                    bbox=bbox,
                                    debug=debug,
                                    ee_pose=ee_pose,
                                    target_z=target_z,
                                    max_lift_cm=max_lift_cm_so_far,
                                    contact=current_contacts > 0,
                                    slip=slip,
                                )
                            )
                        if winner:
                            video_logger.stop_recording(success=True)
                            video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
                            lift_cm = round((final_z[winner] - baseline_z[winner]) * 100.0, 4)
                            hold_s = round(hold_counts[winner] / control_freq, 4)
                            (episodes_dir / f"{trial.scene_id}_attempt{attempt:02d}.json").write_text(
                                json.dumps(
                                    _attempt_payload(
                                        trial=trial,
                                        recipe=recipe,
                                        attempt=attempt,
                                        success=True,
                                        baseline_z=baseline_z,
                                        final_z=final_z,
                                        lift_cm=lift_cm,
                                        hold_steps_reached=hold_counts[winner],
                                        mean_inference_ms=agent.mean_inference_ms,
                                        video_path=video_path,
                                        alias_map=alias_map,
                                        step_trace=step_trace if trace_steps else None,
                                        execution_mode=execution_mode,
                                        shared_success_definition=shared_success_definition,
                                        parent_run_id=parent_run_id,
                                        shard_id=shard_id,
                                        gpu_id=gpu_id,
                                    ),
                                    indent=2,
                                ),
                                encoding="utf-8",
                            )
                            result = EpisodeResult(
                                method=method_name,
                                method_tier=benchmark_method_tier,
                                track=trial.track,
                                execution_mode=execution_mode,
                                task=trial.task,
                                scene_id=trial.scene_id,
                                object_id=trial.object_id,
                                object_group=trial.object_group,
                                condition=trial.condition,
                                instruction=trial.instruction,
                                sensor_stack=str(sensor_config["sensor_stack"]),
                                attempts=attempt,
                                success=True,
                                lift_cm=lift_cm,
                                hold_s=hold_s,
                                spl=round(1.0 / attempt, 4),
                                inference_ms=agent.mean_inference_ms,
                                cycle_time_s=round(time.perf_counter() - cycle_start, 4),
                                failure_stage="",
                                failure_reason="",
                                collision=False,
                                video_path=video_path,
                                node=node,
                                commit=commit,
                                parent_run_id=parent_run_id,
                                shard_id=shard_id,
                                gpu_id=gpu_id,
                            )
                            break
                        if bool(debug.get("attempt_complete")):
                            attempt_complete_early = True
                            break

                    if result is not None:
                        break

                    video_path = ""
                    if video_logger is not None:
                        video_logger.stop_recording(success=False)
                        video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
                    max_lift_cm = round(
                        max((final_z[name] - baseline_z[name]) * 100.0 for name in recipe.success_instance_names),
                        4,
                    )
                    (episodes_dir / f"{trial.scene_id}_attempt{attempt:02d}.json").write_text(
                        json.dumps(
                            _attempt_payload(
                                trial=trial,
                                recipe=recipe,
                                attempt=attempt,
                                success=False,
                                baseline_z=baseline_z,
                                final_z=final_z,
                                lift_cm=max_lift_cm,
                                hold_steps_reached=max(hold_counts.values(), default=0),
                                mean_inference_ms=0.0 if agent is None else agent.mean_inference_ms,
                                video_path=video_path,
                                alias_map=alias_map,
                                failure_stage="task_failure",
                                failure_reason=(
                                    "Shared modular baseline exhausted its fixed execution plan without meeting the success criterion."
                                    if attempt_complete_early
                                    else "Shared success criterion was not met within the Track A step budget."
                                ),
                                step_trace=step_trace if trace_steps else None,
                                execution_mode=execution_mode,
                                shared_success_definition=shared_success_definition,
                                parent_run_id=parent_run_id,
                                shard_id=shard_id,
                                gpu_id=gpu_id,
                            ),
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    if attempt == trial.attempts_per_trial:
                        result = EpisodeResult(
                            method=method_name,
                            method_tier=benchmark_method_tier,
                            track=trial.track,
                            execution_mode=execution_mode,
                            task=trial.task,
                            scene_id=trial.scene_id,
                            object_id=trial.object_id,
                            object_group=trial.object_group,
                            condition=trial.condition,
                            instruction=trial.instruction,
                            sensor_stack=str(sensor_config["sensor_stack"]),
                            attempts=attempt,
                            success=False,
                            lift_cm=max_lift_cm,
                            hold_s=round(max(hold_counts.values(), default=0) / control_freq, 4),
                            spl=0.0,
                            inference_ms=0.0 if agent is None else agent.mean_inference_ms,
                            cycle_time_s=round(time.perf_counter() - cycle_start, 4),
                            failure_stage="task_failure",
                            failure_reason=(
                                "Shared modular baseline exhausted its fixed execution plan without meeting the success criterion."
                                if attempt_complete_early
                                else "Shared success criterion was not met within the Track A step budget."
                            ),
                            collision=False,
                            video_path=video_path,
                            node=node,
                            commit=commit,
                            parent_run_id=parent_run_id,
                            shard_id=shard_id,
                            gpu_id=gpu_id,
                        )
                except Exception as exc:
                    failure_reason = " ".join(f"{type(exc).__name__}: {exc}".split())[:4000]
                    failure_traceback = traceback.format_exc(limit=50)
                    failure_stage = exc.failure_stage if isinstance(exc, AdapterExecutionError) else "scene_execution"
                    video_path = ""
                    if video_logger is not None:
                        video_logger.stop_recording(success=False)
                        video_path = str(Path(video_logger.new_video_name).relative_to(artifact_dir))
                    (episodes_dir / f"{trial.scene_id}_attempt{attempt:02d}.json").write_text(
                        json.dumps(
                            _attempt_payload(
                                trial=trial,
                                recipe=recipe,
                                attempt=attempt,
                                success=False,
                                baseline_z={},
                                final_z={},
                                lift_cm=0.0,
                                hold_steps_reached=0,
                                mean_inference_ms=0.0 if agent is None else agent.mean_inference_ms,
                                video_path=video_path,
                                alias_map=alias_map,
                                failure_stage=failure_stage,
                                failure_reason=failure_reason,
                                failure_traceback=failure_traceback,
                                execution_mode=execution_mode,
                                shared_success_definition=shared_success_definition,
                                parent_run_id=parent_run_id,
                                shard_id=shard_id,
                                gpu_id=gpu_id,
                            ),
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    if attempt == trial.attempts_per_trial:
                        result = EpisodeResult(
                            method=method_name,
                            method_tier=benchmark_method_tier,
                            track=trial.track,
                            execution_mode=execution_mode,
                            task=trial.task,
                            scene_id=trial.scene_id,
                            object_id=trial.object_id,
                            object_group=trial.object_group,
                            condition=trial.condition,
                            instruction=trial.instruction,
                            sensor_stack=str(sensor_config["sensor_stack"]),
                            attempts=attempt,
                            success=False,
                            lift_cm=0.0,
                            hold_s=0.0,
                            spl=0.0,
                            inference_ms=0.0 if agent is None else agent.mean_inference_ms,
                            cycle_time_s=round(time.perf_counter() - cycle_start, 4),
                            failure_stage=failure_stage,
                            failure_reason=failure_reason,
                            collision=False,
                            video_path=video_path,
                            node=node,
                            commit=commit,
                            parent_run_id=parent_run_id,
                            shard_id=shard_id,
                            gpu_id=gpu_id,
                        )
                finally:
                    if agent is not None:
                        agent.close()
                    if env is not None:
                        env.close()

            if result is None:
                raise RuntimeError(f"Missing final result for Track A scene {trial.scene_id}.")
            results.append(result)

        return results, metadata
    finally:
        os.chdir(previous_cwd)


def run_shared_track_a_suite(
    *,
    method_name: str,
    method_config: dict[str, Any],
    task_config: dict[str, Any] | None,
    sensor_config: dict[str, Any],
    task_specs: list[TrialSpec],
    artifact_dir: Path,
    node: str,
    commit: str,
    runtime_config: dict[str, Any],
    execution_mode: str = "shared_track_a_sim",
    parent_run_id: str = "",
    shard_id: str = "",
    gpu_id: str = "",
    robot_config_override: str = "",
    lift_threshold_cm_override: float | None = None,
    hold_steps_override: int | None = None,
    trace_steps: bool = False,
) -> tuple[list[EpisodeResult], dict[str, Any]]:
    return _run_shared_track_a_suite_once(
        method_name=method_name,
        method_config=method_config,
        task_config=task_config,
        sensor_config=sensor_config,
        task_specs=task_specs,
        artifact_dir=artifact_dir,
        node=node,
        commit=commit,
        runtime_config=runtime_config,
        execution_mode=execution_mode,
        parent_run_id=parent_run_id,
        shard_id=shard_id,
        gpu_id=gpu_id,
        robot_config_override=robot_config_override,
        lift_threshold_cm_override=lift_threshold_cm_override,
        hold_steps_override=hold_steps_override,
        trace_steps=trace_steps,
    )
