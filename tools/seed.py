"""Seed the local DB with the prototype's mock data.

Reads ``DATABASE_URL`` and ``FIELD_NOTES_KEY`` from the environment (``.env`` is
loaded via ``python-dotenv`` if present). For each of the four seed projects we
either:

- create the project + all its cells via the public HTTP API, OR
- skip the project entirely if one with the same ``name`` already exists.

The script is idempotent: re-running it against a DB that already has the seed
projects is a no-op. It uses the public REST API (rather than direct DB writes)
so the actual code path an agent would exercise gets tested.

Entrypoint
----------

* ``python -m tools.seed`` — talk to a running API at ``FIELD_NOTES_API_URL``
  (default ``http://localhost:8000``).
* ``seed(client, ...)`` — call from tests against an in-process ASGI app via
  ``httpx.ASGITransport`` (see ``tests/test_seed.py``).
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import httpx

try:  # python-dotenv is optional at runtime; required when invoking standalone.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only when dotenv missing.

    def load_dotenv(*_a: Any, **_kw: Any) -> bool:
        return False


# ---------------------------------------------------------------------------
# Hand-drawn series for the prototype's two reference charts.
#
# The frontend prototype draws these as SVG path/point lists; the API contract
# stores them as ``visual = {kind: "data", chart: "line"|"sweep", series: [...]}``
# tuples of {step, loss} or {x, y, label}. The numbers below are read directly
# off the prototype curves so the seeded UI matches the design preview.
# ---------------------------------------------------------------------------

LOSS_SERIES: list[dict[str, float]] = [
    {"step": 0, "loss": 0.395},
    {"step": 20_000, "loss": 0.340},
    {"step": 40_000, "loss": 0.232},
    {"step": 60_000, "loss": 0.150},
    {"step": 90_000, "loss": 0.087},
    {"step": 120_000, "loss": 0.055},
    {"step": 150_000, "loss": 0.044},
    {"step": 180_000, "loss": 0.038},
]

SWEEP_SERIES: list[dict[str, Any]] = [
    {"x": 0.2, "y": 0.71, "label": "0.2"},
    {"x": 0.4, "y": 0.78, "label": "0.4"},
    {"x": 0.6, "y": 0.82, "label": "0.6"},
    {"x": 0.8, "y": 0.77, "label": "0.8"},
    {"x": 1.0, "y": 0.69, "label": "1.0"},
]


# ---------------------------------------------------------------------------
# Mock data — verbatim transcription of the prototype's SEED_CELLS / VLA_CELLS
# / SIM2REAL_CELLS / DATA_CELLS / SEED_PROJECTS from
# ``ai-notebook/project/app.jsx``. Cells are ordered as in the prototype.
# ---------------------------------------------------------------------------


def _seed_cells() -> list[dict[str, Any]]:
    return [
        {
            "id": "md-intro",
            "kind": "markdown",
            "body": (
                "# Week 19 — manipulation\n\n"
                "Rolling notebook for the **TSC-WS** push. Goal: ship a checkpoint that beats run 3 "
                "on held-out objects and passes the new reflective-objects bench. Threads below are "
                "ordered narratively, not chronologically — see the *failure mode review* near the "
                "bottom before you sign off on anything.\n\n"
                "> open questions: gripper compliance delta, whether v3 mix is truly locked."
            ),
        },
        {
            "id": "c-001",
            "title": "pi0.5 TSC WS task — training run 4",
            "agent": "agent-orca-7",
            "status": "verified",
            "conclusion": (
                "Run 4 converges ~22% faster than run 3 after enabling the residual head warm-start. "
                "Final success rate on held-out objects holds at 0.74 ± 0.03 across 3 seeds. "
                "Recommend promoting this checkpoint to the eval queue."
            ),
            "metrics": [
                {"k": "success@k", "v": "0.74", "d": "+0.09 vs run 3"},
                {"k": "steps", "v": "180k", "d": "early stop"},
                {"k": "wall time", "v": "11h 22m"},
                {"k": "loss", "v": "0.038", "d": "-31%"},
            ],
            "chart": "loss",
            "verdict": {
                "state": "accept",
                "note": "Promote. Re-run on the new fingertip set before locking.",
            },
            "deep": {
                "hparams": {
                    "lr": "3e-4 → 1e-4 (cosine)",
                    "batch": "256",
                    "seeds": "[7, 13, 42]",
                    "optimizer": "AdamW (β1=0.9, β2=0.95)",
                    "warmup": "2k steps",
                    "residual_head": "true (warm-start from run 2)",
                },
                "files": [
                    "configs/pi0_5_tsc_ws_v4.yaml",
                    "training/launch_run4.sh",
                    "data/manifest_2026_05_12.jsonl",
                ],
                "runs": [
                    {"name": "tsc-ws-r4-s7", "url": "wandb://orca/tsc-ws/r4-s7"},
                    {"name": "tsc-ws-r4-s13", "url": "wandb://orca/tsc-ws/r4-s13"},
                    {"name": "tsc-ws-r4-s42", "url": "wandb://orca/tsc-ws/r4-s42"},
                ],
                "logs": (
                    "[180432] eval/success_at_k = 0.741\n"
                    "[180432] eval/success_at_k_std = 0.031\n"
                    "[180432] train/loss = 0.0381\n"
                    "[180432] saving checkpoint to ckpt/r4/180432.pt\n"
                    "[180432] early stop triggered: val plateau (12 evals)"
                ),
            },
        },
        {
            "id": "c-002",
            "title": "Reward shaping ablation — sparse vs dense (kitchen-pick)",
            "agent": "agent-orca-7",
            "status": "rejected",
            "conclusion": (
                "Dense reward outperforms sparse by 18% on kitchen-pick. Recommend switching the "
                "WS curriculum to dense shaping for all manipulation tasks."
            ),
            "metrics": [
                {"k": "sparse", "v": "0.41"},
                {"k": "dense", "v": "0.59", "d": "+18%"},
                {"k": "seeds", "v": "2"},
            ],
            "verdict": {
                "state": "reject",
                "note": (
                    "n=2 seeds is not enough to claim 18%. Variance on sparse alone is ~12% across "
                    "5 seeds historically. Re-run with 5 seeds and a paired test before generalizing "
                    "to all tasks."
                ),
            },
            "deep": {
                "hparams": {
                    "env": "kitchen-pick-v3",
                    "seeds": "[7, 13]",
                    "episodes": "2k each",
                    "shaping": "{sparse: terminal-only, dense: pos+grasp+lift}",
                },
                "files": ["envs/kitchen_pick_v3.py", "rewards/dense_shaping.py", "scripts/ablate_rewards.py"],
                "runs": [
                    {"name": "shape-sparse-s7", "url": "wandb://orca/shaping/sparse-s7"},
                    {"name": "shape-dense-s7", "url": "wandb://orca/shaping/dense-s7"},
                    {"name": "shape-sparse-s13", "url": "wandb://orca/shaping/sparse-s13"},
                    {"name": "shape-dense-s13", "url": "wandb://orca/shaping/dense-s13"},
                ],
                "logs": (
                    "[ep 2000] sparse/s7 success=0.39\n"
                    "[ep 2000] sparse/s13 success=0.43\n"
                    "[ep 2000] dense/s7 success=0.61\n"
                    "[ep 2000] dense/s13 success=0.57\n"
                    "[summary] mean_dense=0.59 mean_sparse=0.41 delta=0.18"
                ),
            },
        },
        {
            "id": "c-003",
            "title": "Camera calibration drift — cell 2 left wrist",
            "agent": "agent-orca-3",
            "status": "in_progress",
            "conclusion": (
                "Investigating ~3.2px reprojection error that appeared after last night's gripper "
                "swap. Running checkerboard sweep across 60 poses; ~22/60 complete. Drift pattern "
                "looks radial, suggests mount torque not intrinsics. Will compare to last week's "
                "calibration when sweep finishes (~45m)."
            ),
            "metrics": [
                {"k": "poses", "v": "22 / 60", "d": "in progress"},
                {"k": "reproj err", "v": "3.2 px", "d": "target < 0.8"},
            ],
            "verdict": None,
            "deep": {
                "hparams": {
                    "board": "11x8 @ 24mm",
                    "camera": "wrist-left (cell 2)",
                    "previous_calib": "2026-05-08 16:11",
                },
                "files": ["calib/sweep_v2.py", "calib/board_11x8.yaml"],
                "runs": [{"name": "calib-cell2-wl-2026-05-15", "url": "wandb://orca/calib/cell2-wl-15"}],
                "logs": (
                    "[pose 22] reproj_err_px=3.18\n"
                    "[pose 21] reproj_err_px=3.22\n"
                    "[pose 20] reproj_err_px=3.17\n"
                    "[pose 19] reproj_err_px=3.41\n"
                    "[pose 18] reproj_err_px=3.05"
                ),
            },
        },
        {
            "id": "c-004",
            "title": "Domain randomization sweep — lighting intensity",
            "agent": "agent-orca-7",
            "status": "open",
            "conclusion": (
                "Swept lighting intensity randomization across [0.2, 0.4, 0.6, 0.8, 1.0] on the "
                "sim2real eval bench. Sweet spot at 0.6 — wider than that hurts grasp precision "
                "(-7%), narrower fails the dark-shelf eval. Recommend setting default to 0.6 in the "
                "sim config."
            ),
            "metrics": [
                {"k": "best", "v": "0.6", "d": "82% success"},
                {"k": "δ vs current", "v": "+5.4%"},
                {"k": "sim2real gap", "v": "11%", "d": "-3pp"},
            ],
            "chart": "sweep",
            "verdict": None,
            "deep": {
                "hparams": {
                    "sweep": "[0.2, 0.4, 0.6, 0.8, 1.0]",
                    "seeds": "[7, 13, 42]",
                    "eval": "sim2real-bench-v2 (480 eps)",
                },
                "files": ["sim/randomizers/lighting.py", "configs/dr_lighting_sweep.yaml"],
                "runs": [
                    {"name": "dr-light-02", "url": "wandb://orca/dr/light-02"},
                    {"name": "dr-light-04", "url": "wandb://orca/dr/light-04"},
                    {"name": "dr-light-06", "url": "wandb://orca/dr/light-06"},
                    {"name": "dr-light-08", "url": "wandb://orca/dr/light-08"},
                    {"name": "dr-light-10", "url": "wandb://orca/dr/light-10"},
                ],
                "logs": (
                    "[final] 0.2 -> 0.71 ± 0.04\n"
                    "[final] 0.4 -> 0.78 ± 0.03\n"
                    "[final] 0.6 -> 0.82 ± 0.02\n"
                    "[final] 0.8 -> 0.77 ± 0.04\n"
                    "[final] 1.0 -> 0.69 ± 0.05"
                ),
            },
        },
        {
            "id": "md-section-failures",
            "kind": "markdown",
            "body": (
                "## Failure analysis\n\n"
                "Before locking anything, look at how the policy *fails* — the slip mode below is "
                "the dominant failure type this week and likely also drives part of the sim2real gap."
            ),
        },
        {
            "id": "c-005",
            "title": "Failure mode: gripper slip on cylindrical objects",
            "agent": "agent-orca-3",
            "status": "open",
            "conclusion": (
                "Reviewed 142 failure clips from the last week. 31% are gripper slip, of which 73% "
                "involve cylinders with diameter 35–55mm. The policy commits to a top grasp before "
                "contact and doesn't re-plan when the object rolls. Two repro videos attached — "
                "both show the same signature."
            ),
            "video": {"duration": "0:14", "label": "slip-repro · cylinder-42mm"},
            "metrics": [
                {"k": "slip rate", "v": "31%", "d": "of all failures"},
                {"k": "in band 35–55mm", "v": "73%"},
            ],
            "verdict": None,
            "deep": {
                "hparams": {"window": "2026-05-08 → 2026-05-15", "objects": "all cylindrical SKUs"},
                "files": ["analysis/failure_review_2026_05_15.ipynb", "data/failures_week_19.parquet"],
                "runs": [],
                "logs": (
                    "found 142 failure episodes\n"
                    "clustered by failure_type (kmeans, k=6)\n"
                    "cluster 0 (slip): 44 eps\n"
                    "cluster 0 ∩ cylinder: 32 eps\n"
                    "median diameter in cluster 0: 41mm"
                ),
            },
        },
        {
            "id": "md-section-historical",
            "kind": "markdown",
            "body": (
                "## Historical — already locked\n\n"
                "Kept here so the data-mix decision is one click away when the next agent inevitably "
                "proposes re-running this experiment."
            ),
        },
        {
            "id": "c-006",
            "title": "VLA fine-tuning — data mix v3 (15% web, 60% lab, 25% sim)",
            "agent": "agent-orca-7",
            "status": "verified",
            "conclusion": (
                "Mix v3 lifts language-grounded eval from 0.58 to 0.66 while holding manipulation "
                "success flat. Larger web fraction (25%) overfit to caption phrasing in the v3.5 "
                "pilot, so 15% is the soft ceiling. Locking v3 as the production mix."
            ),
            "metrics": [
                {"k": "lang eval", "v": "0.66", "d": "+0.08"},
                {"k": "manip eval", "v": "0.71", "d": "±0.01"},
                {"k": "mix", "v": "15/60/25"},
            ],
            "verdict": {
                "state": "accept",
                "note": "Locked. Flagging in #ml-infra to update the default training config.",
            },
            "lock": True,
            "deep": {
                "hparams": {
                    "base": "vla-7b-ckpt-2026-05-09",
                    "lr": "1e-5",
                    "epochs": "2",
                    "batch": "128",
                    "mix": "web:0.15, lab:0.60, sim:0.25",
                },
                "files": ["data/mixes/v3.yaml", "training/vla_ft.py"],
                "runs": [
                    {"name": "vla-ft-mix-v3", "url": "wandb://orca/vla-ft/mix-v3"},
                    {"name": "vla-ft-mix-v35", "url": "wandb://orca/vla-ft/mix-v35"},
                ],
                "logs": (
                    "[eval] lang_grounded = 0.661\n"
                    "[eval] manip_success = 0.712\n"
                    "[eval] v3.5 lang_grounded = 0.673 (overfit, see caption_diversity)\n"
                    "[eval] caption_diversity v3 = 0.81, v3.5 = 0.62"
                ),
            },
        },
    ]


def _vla_cells() -> list[dict[str, Any]]:
    return [
        {
            "id": "v-001",
            "title": "Caption diversity collapse — mix v3.5 pilot",
            "agent": "agent-orca-7",
            "status": "rejected",
            "conclusion": (
                "Bumping web fraction to 25% lifted language-grounded eval to 0.673 but "
                "caption-diversity score fell from 0.81 to 0.62 — model is parroting common "
                "phrasings. Recommend keeping web at 15%."
            ),
            "metrics": [
                {"k": "lang eval", "v": "0.673", "d": "+0.012"},
                {"k": "caption div", "v": "0.62", "d": "-0.19"},
                {"k": "web frac", "v": "0.25"},
            ],
            "verdict": {
                "state": "reject",
                "note": (
                    "Agreed on the call. But add a paraphrase-augmentation pass before retrying — "
                    "we may still want more web data, just less template-y."
                ),
            },
            "deep": {
                "hparams": {"base": "vla-7b-ckpt-2026-05-09", "mix": "web:0.25, lab:0.55, sim:0.20", "lr": "1e-5"},
                "files": ["data/mixes/v35.yaml", "eval/caption_diversity.py"],
                "runs": [{"name": "vla-ft-mix-v35", "url": "wandb://orca/vla-ft/mix-v35"}],
                "logs": (
                    "[eval] lang_grounded = 0.673\n"
                    "[eval] caption_diversity = 0.617\n"
                    "[eval] top-3 phrasings explain 41% of outputs (vs 18% on v3)"
                ),
            },
        },
        {
            "id": "v-002",
            "title": "Frozen vision encoder ablation",
            "agent": "agent-orca-7",
            "status": "verified",
            "conclusion": (
                "Freezing the vision encoder loses ~3.2pp on manipulation eval but trains 2.1× faster "
                "and uses 38% less VRAM. Acceptable trade for iteration runs; unfreeze for final."
            ),
            "metrics": [
                {"k": "manip eval", "v": "0.68", "d": "-0.032"},
                {"k": "vram", "v": "-38%"},
                {"k": "throughput", "v": "2.1×"},
            ],
            "verdict": {
                "state": "accept",
                "note": "Default for sweeps. Keep unfrozen on final lock runs.",
            },
            "deep": {
                "hparams": {"freeze": "vision_encoder=true", "base": "vla-7b", "batch": "192"},
                "files": ["training/vla_ft.py", "configs/freeze_vision.yaml"],
                "runs": [{"name": "vla-frozen-vision", "url": "wandb://orca/vla-ft/frozen"}],
                "logs": (
                    "[eval] manip_success = 0.680\n"
                    "[profile] step_time = 1.42s (vs 2.98s)\n"
                    "[profile] peak_vram = 41.2 GB (vs 66.8 GB)"
                ),
            },
        },
        {
            "id": "v-003",
            "title": "Long-context tuning — 4k vs 8k window",
            "agent": "agent-orca-9",
            "status": "in_progress",
            "conclusion": (
                "8k window training is at 64% of the way through epoch 1. Loss curves track 4k "
                "baseline tightly so far; the real test is the long-instruction eval at end-of-epoch."
            ),
            "metrics": [
                {"k": "progress", "v": "64%", "d": "epoch 1/2"},
                {"k": "loss", "v": "0.044"},
            ],
            "verdict": None,
            "deep": {
                "hparams": {"ctx": "8192", "lr": "8e-6", "batch": "64"},
                "files": ["training/vla_ft.py", "configs/long_ctx_8k.yaml"],
                "runs": [{"name": "vla-ctx8k-e1", "url": "wandb://orca/vla-ft/ctx8k-e1"}],
                "logs": (
                    "[step 18400/28800] loss=0.0441\n[step 18200/28800] loss=0.0445\n[step 18000/28800] loss=0.0438"
                ),
            },
        },
    ]


def _sim2real_cells() -> list[dict[str, Any]]:
    return [
        {
            "id": "s-001",
            "title": "Bench v2 calibration — 480 episodes across 6 object classes",
            "agent": "agent-orca-3",
            "status": "open",
            "conclusion": (
                "Built the v2 eval bench. 6 object classes (cylinders, boxes, soft, deformable, "
                "transparent, reflective), 80 episodes each. Baseline policy gets 0.61 overall; "
                "reflective is the worst at 0.32."
            ),
            "chart": "sweep",
            "metrics": [
                {"k": "overall", "v": "0.61"},
                {"k": "worst class", "v": "reflective", "d": "0.32"},
                {"k": "best class", "v": "boxes", "d": "0.81"},
            ],
            "verdict": None,
            "deep": {
                "hparams": {"episodes_per_class": "80", "classes": "6", "baseline": "vla-7b-ckpt-2026-05-09"},
                "files": ["eval/bench_v2.py", "eval/classes_v2.yaml", "assets/objects/reflective/"],
                "runs": [{"name": "bench-v2-baseline", "url": "wandb://orca/bench/v2-baseline"}],
                "logs": (
                    "[final] cylinders=0.64\n"
                    "[final] boxes=0.81\n"
                    "[final] soft=0.71\n"
                    "[final] deformable=0.55\n"
                    "[final] transparent=0.61\n"
                    "[final] reflective=0.32"
                ),
            },
        },
        {
            "id": "s-002",
            "title": "Gripper hardware delta — sim vs real",
            "agent": "agent-orca-3",
            "status": "open",
            "conclusion": (
                "Measured contact compliance on the new fingertip set against the sim model. Real "
                "grippers are ~14% stiffer than the sim spec; this likely explains the sim2real gap "
                "on deformables (-19pp). Updating the sim model parameters and re-running."
            ),
            "metrics": [
                {"k": "stiffness Δ", "v": "+14%"},
                {"k": "deformable gap", "v": "-19pp"},
            ],
            "verdict": None,
            "deep": {
                "hparams": {"fingertip": "v2.3", "probe": "compliance_sweep_v1"},
                "files": ["hardware/compliance_probe.py", "sim/grippers/fingertip_v23.urdf"],
                "runs": [{"name": "compliance-probe-v23", "url": "wandb://orca/hw/compliance-v23"}],
                "logs": (
                    "[probe] mean_stiffness_real = 248 N/m\n"
                    "[probe] mean_stiffness_sim  = 217 N/m\n"
                    "[probe] delta = +14.3%"
                ),
            },
        },
    ]


def _data_cells() -> list[dict[str, Any]]:
    return [
        {
            "id": "d-001",
            "title": "Manifest dedup — 2.4M episodes pre-pass",
            "agent": "agent-orca-5",
            "status": "verified",
            "conclusion": (
                "Near-duplicate detection across the lab capture set found 312k episodes (13%) "
                "within 0.04 cosine of another. Removing duplicates didn't change downstream eval; "
                "keep the dedup pass in the default pipeline."
            ),
            "metrics": [
                {"k": "input", "v": "2.40M"},
                {"k": "dropped", "v": "312k", "d": "13%"},
                {"k": "eval Δ", "v": "+0.001", "d": "negligible"},
            ],
            "verdict": {"state": "accept", "note": "Lands as default. CC'd #data-infra."},
            "deep": {
                "hparams": {"threshold": "0.04 cosine", "embedding": "siglip-l", "chunks": "256"},
                "files": ["data/dedup_v2.py", "data/manifests/2026_05_10.jsonl"],
                "runs": [{"name": "dedup-v2-full", "url": "wandb://orca/data/dedup-v2"}],
                "logs": ("[dedup] total_in=2,401,883\n[dedup] dropped=312,441\n[dedup] kept=2,089,442"),
            },
        },
    ]


SEED_PROJECTS: list[dict[str, Any]] = [
    {
        "name": "orca · manipulation",
        "subtitle": "week 19",
        "repo": "orca-research/field-notes",
        "cells": _seed_cells(),
    },
    {
        "name": "pi0.5 · VLA fine-tune",
        "subtitle": "week 18",
        "repo": "orca-research/vla-ft",
        "cells": _vla_cells(),
    },
    {
        "name": "sim2real · bench v2",
        "subtitle": "week 19",
        "repo": "orca-research/sim2real-bench",
        "cells": _sim2real_cells(),
    },
    {
        "name": "data infra · v2",
        "subtitle": "week 17",
        "repo": "orca-research/data-infra",
        "cells": _data_cells(),
    },
]


# ---------------------------------------------------------------------------
# Helpers — map a prototype cell dict to the API's CellCreate / VerdictSet
# payloads.
# ---------------------------------------------------------------------------


def _build_visual(chart: str | None) -> dict[str, Any] | None:
    if chart == "loss":
        return {"kind": "data", "chart": "line", "series": LOSS_SERIES}
    if chart == "sweep":
        return {"kind": "data", "chart": "sweep", "series": SWEEP_SERIES}
    return None


def _cell_create_payload(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("kind") == "markdown":
        return {"kind": "markdown", "body": spec["body"]}
    payload: dict[str, Any] = {
        "kind": "agent",
        "title": spec["title"],
        "agent_id": spec["agent"],
        "status": spec["status"],
        "conclusion": spec["conclusion"],
    }
    if spec.get("metrics") is not None:
        payload["metrics"] = spec["metrics"]
    visual = _build_visual(spec.get("chart"))
    if visual is not None:
        payload["visual"] = visual
    if spec.get("video") is not None:
        payload["video"] = spec["video"]
    if spec.get("deep") is not None:
        payload["deep"] = spec["deep"]
    return payload


# ---------------------------------------------------------------------------
# Seed driver
# ---------------------------------------------------------------------------


async def _ensure_project(client: httpx.AsyncClient, spec: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Return (created, project_json). Idempotent on project name match."""
    r = await client.get("/projects")
    r.raise_for_status()
    for p in r.json():
        if p["name"] == spec["name"]:
            return False, p
    r = await client.post(
        "/projects",
        json={"name": spec["name"], "subtitle": spec.get("subtitle"), "repo": spec.get("repo")},
    )
    r.raise_for_status()
    return True, r.json()


async def _create_cells_for_project(
    client: httpx.AsyncClient,
    project_id: str,
    cell_specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create each cell in order; then apply verdicts; then lock where flagged.

    Returns the list of created cell dicts (post-verdict, post-lock).
    """
    created: list[tuple[dict[str, Any], dict[str, Any]]] = []  # (spec, cell_json)
    for spec in cell_specs:
        body = _cell_create_payload(spec)
        r = await client.post(f"/projects/{project_id}/cells", json=body)
        r.raise_for_status()
        created.append((spec, r.json()))

    # Verdicts are POSTed separately — the server cascades status to verified/rejected.
    for spec, cell in created:
        v = spec.get("verdict")
        if v:
            r = await client.post(f"/cells/{cell['id']}/verdict", json={"state": v["state"], "note": v["note"]})
            r.raise_for_status()

    # Apply locks (only after the verdict is in place; lock requires accept verdict).
    for spec, cell in created:
        if spec.get("lock"):
            r = await client.post(f"/cells/{cell['id']}/lock")
            r.raise_for_status()

    # Re-fetch the final state so callers see verdict + locked flags.
    r = await client.get(f"/projects/{project_id}/cells")
    r.raise_for_status()
    return r.json()


async def seed(client: httpx.AsyncClient) -> dict[str, Any]:
    """Idempotent seed against any AsyncClient. Returns a summary dict.

    The client is expected to be pre-authenticated (X-Field-Notes-Key header
    already set). Used both by ``main()`` (HTTP client) and ``tests/test_seed.py``
    (ASGI in-process transport).
    """
    summary: dict[str, Any] = {"projects": [], "created_count": 0, "skipped_count": 0}
    for spec in SEED_PROJECTS:
        created, project = await _ensure_project(client, spec)
        if not created:
            summary["projects"].append({"name": project["name"], "id": project["id"], "skipped": True})
            summary["skipped_count"] += 1
            continue
        cells = await _create_cells_for_project(client, project["id"], spec["cells"])
        summary["projects"].append(
            {
                "name": project["name"],
                "id": project["id"],
                "skipped": False,
                "cell_count": len(cells),
            }
        )
        summary["created_count"] += 1
    return summary


async def _amain() -> int:
    load_dotenv()
    key = os.environ.get("FIELD_NOTES_KEY")
    if not key:
        print("FIELD_NOTES_KEY is not set — refusing to seed.", file=sys.stderr)
        return 2
    base_url = os.environ.get("FIELD_NOTES_API_URL", "http://localhost:8000")
    async with httpx.AsyncClient(base_url=base_url, headers={"X-Field-Notes-Key": key}, timeout=30.0) as client:
        # Sanity: is the API up?
        try:
            r = await client.get("/healthz")
            r.raise_for_status()
        except Exception as e:
            print(f"API at {base_url} is unreachable: {e}", file=sys.stderr)
            return 3
        summary = await seed(client)
    created = summary["created_count"]
    skipped = summary["skipped_count"]
    print(f"seeded: created={created} skipped={skipped}")
    for p in summary["projects"]:
        if p.get("skipped"):
            print(f"  - [skip] {p['name']}  (already exists)")
        else:
            print(f"  - [new]  {p['name']}  cells={p['cell_count']}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
