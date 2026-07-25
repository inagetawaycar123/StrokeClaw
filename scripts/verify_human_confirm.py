#!/usr/bin/env python3
"""Smoke-test the terminal human_confirm node without full imaging models."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    dinov3 = os.path.join(ROOT, "dinov3")
    required = [
        os.path.join(dinov3, "dinov3权重.pth"),
        os.path.join(dinov3, "ckpt", "dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth"),
        os.path.join(dinov3, "dinov3"),
    ]
    print("== weight / package check ==")
    for path in required:
        ok = os.path.exists(path)
        print(("OK " if ok else "MISS"), path)
        if not ok:
            return 1

    print("\n== import backend.app ==")
    from backend import app as app_module

    for path_name, seq in app_module.AGENT_TOOL_SEQUENCE_MAP.items():
        assert seq[-1] == "human_confirm", path_name
        print(f"OK sequence[{path_name}] ends with human_confirm")
    assert app_module.POST_UPLOAD_SUMMARY_TOOL_SEQUENCE[-1] == "human_confirm"
    print("OK post_upload_summary ends with human_confirm")

    print("\n== pause / complete flow ==")
    run_id = "smoke-human-confirm"
    app_module._create_agent_run(
        run_id=run_id,
        patient_id=1,
        file_id="smoke-file",
        available_modalities=["NCCT"],
    )

    def seed(state):
        state["planner_output"] = {
            "imaging_path": "ncct_only",
            "tool_sequence": ["generate_medgemma_report", "human_confirm"],
            "path_decision": {"imaging_path": "ncct_only", "valid": True},
        }
        state["steps"] = [
            {
                "key": "generate_medgemma_report",
                "title": "generate_medgemma_report",
                "status": "completed",
                "message": "",
                "retryable": False,
                "attempts": 1,
                "started_at": None,
                "ended_at": None,
            },
            {
                "key": "human_confirm",
                "title": "human_confirm",
                "status": "pending",
                "message": "",
                "retryable": False,
                "attempts": 0,
                "started_at": None,
                "ended_at": None,
            },
        ]
        state["tool_results"] = [
            {
                "tool_name": "generate_medgemma_report",
                "status": "completed",
                "structured_output": {
                    "report": "smoke report",
                    "report_payload": {"summary": "smoke"},
                },
                "raw_ref": {"tool_name": "generate_medgemma_report"},
                "latency_ms": 1,
                "attempt": 1,
            }
        ]

    app_module._update_agent_run(run_id, seed)
    ok, result = app_module._execute_agent_tool(run_id, "human_confirm")
    assert ok and result.get("status") == "waiting", result
    paused = app_module._pause_for_human_confirm(
        run_id, tool_name="human_confirm", tool_result=result
    )
    assert paused["status"] == "paused_review_required"
    assert (paused.get("human_checkpoint") or {}).get("required") is True
    print("OK paused at human_confirm")

    review_state = paused.get("review_state") or app_module._review_build_state(paused)
    for section in review_state.get("sections") or []:
        section["review_status"] = "confirmed"
    review_state = app_module._review_recompute_state(review_state)
    assert review_state.get("all_confirmed")

    def attach(state):
        app_module._review_attach_to_run_state(state, review_state)

    app_module._update_agent_run(run_id, attach)
    updated, err = app_module._complete_human_confirm_checkpoint(
        run_id, action="finalize_review"
    )
    assert err is None, err
    assert updated["status"] == "succeeded"
    step = next(s for s in updated["steps"] if s["key"] == "human_confirm")
    assert step["status"] == "completed"
    print("OK human_confirm completed -> succeeded")
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
