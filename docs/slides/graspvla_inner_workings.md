---
marp: true
paginate: true
theme: default
---

# GraspVLA Inner Workings

Zihao Lu benchmark notes

- Goal: explain how GraspVLA works to the benchmark team
- Scope: public release pieces plus what we have actually run on `em14`

---

## Why This Paper Matters

- GraspVLA is a grasping VLA pretrained on synthetic grasp data instead of large real robot logs.
- The paper claims strong zero-shot sim-to-real transfer for open-vocabulary grasping.
- For our benchmark, it is the clearest end-to-end baseline against modular pipelines such as AnyGrasp and Contact-GraspNet.
- The public release is deployment-oriented: model server, simulation playground, and Franka real-world controller.

---

## What The Public Release Contains

- `GraspVLA/`: model server and offline test entrypoints.
- `GraspVLA-playground/`: simulation playground, LIBERO evaluation, and `validate_server.py`.
- `GraspVLA-real-world-controller/`: Franka plus dual-camera real-world client.
- The full training stack and SynGrasp-1B dataset are not publicly released yet, so our work focuses on deployment and benchmarking.

---

## Server API In Practice

- Input request keys: `front_view_image`, `side_view_image`, `proprio_array`, `text`.
- `text` is wrapped into a chain-of-thought style prompt:
  `In: What action should the robot take to {instruction}?`
- `serve.py` warms up the model, opens a ZeroMQ server, and handles one request at a time.
- The server returns:
  `result` for action deltas, plus `debug` fields such as `bbox` and `pose`.

---

## How The Model Produces A Grasp

- The token pattern is `text_ids -> bbox -> hist_proprio -> cur_proprio -> goal -> eos`.
- First stage: autoregressive generation predicts visual reasoning tokens such as `bbox` and `goal`.
- Second stage: flow matching generates the continuous action trajectory conditioned on the prefix cache and proprio.
- The final action is detokenized back to `xyz + rpy + gripper`.

---

## Important Code Paths

- Prompt wrapper:
  `vla_network/data_preprocessing/prompt.py`
- Token layout for CoT plus action:
  `vla_network/data_preprocessing/token_pattern.py`
- Main generation path:
  `vla_network/model/vla/__init__.py`
- Flow-matching action head:
  `vla_network/model/vla/flow_matching.py`
- Deployment server:
  `vla_network/scripts/serve.py`

---

## Why The Deployment Stack Looks Different From Modular Pipelines

- GraspVLA consumes two fixed RGB views and recent proprio, then emits action deltas directly.
- It does not call a separate detector, segmenter, or motion planner at inference time.
- The server still exposes intermediate reasoning artifacts through `debug.bbox` and `debug.pose`.
- In the benchmark, this means we can compare:
  direct action generation vs staged language-grounding plus grasp-proposal pipelines.

---

## What We Have Running Right Now

- Official model server is running on `em14:6666`.
- Official validation path works through the public `validate_server.py`.
- Official `offline_test.py` also succeeds and exports a visualization artifact.
- Benchmark smoke results:
  `GraspVLA` success `1/1`, about `377 ms`.
- `Contact-GraspNet` success `1/1`, but much slower, about `405.6 s`.
- `AnyGrasp` is blocked only by license, not by repo setup anymore.

---

## What To Tell The Benchmark Team

- GraspVLA is best understood as:
  language-conditioned perception tokens plus flow-matching action generation.
- The public release is strong enough for deployment benchmarking even without the full training code.
- Our benchmark wrapper already normalizes outputs to the same `ee_delta[6] + gripper` interface as the modular baselines.
- The next useful comparison is a small Track A batch once the AnyGrasp license arrives.
