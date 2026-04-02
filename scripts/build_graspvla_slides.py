from __future__ import annotations

from pathlib import Path
import sys


SLIDES = [
    (
        "GraspVLA Inner Workings",
        [
            "Goal: explain how GraspVLA works to the benchmark team",
            "Scope: public release plus what we have already run on em14",
        ],
    ),
    (
        "Why This Paper Matters",
        [
            "Synthetic-data pretraining for grasping instead of large real robot logs",
            "Direct end-to-end baseline for our benchmark against modular systems",
            "Public release focuses on deployment: server, simulation, and real-world controller",
        ],
    ),
    (
        "Public Release Pieces",
        [
            "GraspVLA repo: model server and offline test",
            "GraspVLA-playground repo: validation, playground, and LIBERO evaluation",
            "GraspVLA-real-world-controller repo: Franka plus dual-camera client",
            "Full training stack and SynGrasp-1B are not fully public",
        ],
    ),
    (
        "Server API",
        [
            "Inputs: front_view_image, side_view_image, proprio_array, text",
            "Prompt wrapper: In: What action should the robot take to {instruction}?",
            "ZeroMQ service returns action deltas plus debug bbox and pose",
            "serve.py warms up the model before opening the request loop",
        ],
    ),
    (
        "How The Model Produces A Grasp",
        [
            "Token pattern: text_ids, bbox, hist_proprio, cur_proprio, goal, eos",
            "Autoregressive stage predicts bbox and goal tokens",
            "Flow matching stage generates continuous action trajectory",
            "Output is detokenized back to xyz, rpy, and gripper",
        ],
    ),
    (
        "Important Code Paths",
        [
            "prompt.py for the CoT prompt wrapper",
            "token_pattern.py for bbox and goal token layout",
            "model/vla/__init__.py for autoregressive plus flow-matching generation",
            "model/vla/flow_matching.py for the action head",
            "scripts/serve.py for deployment inference",
        ],
    ),
    (
        "Current Lab Status",
        [
            "Official model server is running on em14:6666",
            "Official validate_server.py and offline_test.py both succeeded on em14",
            "Official playground.py and evaluate_libero_tasks.py now run in gb-graspvla-sim",
            "Official complete sim batch is done: playground 8/10, libero_object 482/500, libero_10 325/350, libero_goal 336/350",
            "The 350 denominators are expected: libero_10 exposes 7 tasks and libero_goal skips 3 invalid tasks",
            "GraspVLA smoke success 1/1 at about 377 ms",
            "Contact-GraspNet smoke success 1/1 at about 405.6 s",
            "AnyGrasp is blocked only by license, not by repo setup",
        ],
    ),
    (
        "Next Step For The Team",
        [
            "Use the complete official GraspVLA sim run as the anchor reference",
            "Run a small Track A batch with GraspVLA and Contact-GraspNet",
            "Fetch the AnyGrasp license and complete the third baseline",
            "Collect plots, failure taxonomy, and videos for the benchmark meeting",
        ],
    ),
]


def main() -> None:
    tool_python_dir = Path(r"D:\Program Files (x86)\codex-tools\py")
    if tool_python_dir.exists():
        sys.path.insert(0, str(tool_python_dir))

    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
    except ImportError as exc:
        raise SystemExit(
            "python-pptx is required. Install it first, for example with "
            '`python -m pip install --target "D:\\Program Files (x86)\\codex-tools\\py" python-pptx`.'
        ) from exc

    output_path = Path("D:/codex/grasp-benchmark/docs/slides/graspvla_inner_workings.pptx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)

    for index, (title, bullets) in enumerate(SLIDES):
        if index == 0:
            slide = presentation.slides.add_slide(presentation.slide_layouts[0])
            slide.shapes.title.text = title
            slide.placeholders[1].text = "\n".join(bullets)
            continue

        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = title
        text_frame = slide.placeholders[1].text_frame
        text_frame.clear()
        for bullet_index, bullet in enumerate(bullets):
            paragraph = text_frame.paragraphs[0] if bullet_index == 0 else text_frame.add_paragraph()
            paragraph.text = bullet
            paragraph.level = 0
            paragraph.font.size = Pt(22)

    presentation.save(output_path)
    print(f"Wrote slide deck to {output_path}")


if __name__ == "__main__":
    main()
