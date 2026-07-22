"""Lightweight Agent Cockpit demo server.

This launcher intentionally does not import ``backend.app`` so the real Cockpit
UI can be verified without Torch, model weights, CUDA, Supabase, or the model
runtime.  It serves the production Jinja template/static assets and exposes a
small in-memory subset of the existing mock-run API contract.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, redirect, render_template, request, url_for


ROOT = Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(ROOT / "static"),
    static_url_path="/static",
    template_folder=str(ROOT / "backend" / "templates"),
)

MOCK_RUNS: dict[str, dict] = {}
MOCK_EVENTS: dict[str, list[dict]] = {}
DEFAULT_RUN_ID = "cockpit_demo_standard"


NODE_SPECS = [
    {
        "tool_name": "detect_modalities",
        "node_name": "模态识别",
        "agent_name": "Case Intake Agent",
        "skill_id": "SKILL_MODALITY_DETECT",
        "skill_name": "影像模态识别 Skill",
        "stage": "triage",
        "input_summary": "读取病例 demo_case_001 的影像序列元数据。",
        "output_summary": "识别到 NCCT 与 mCTA，可进入卒中分析路径。",
        "confidence_score": 0.97,
        "confidence_method": "metadata_rule_and_classifier",
        "evidence_refs": ["DICOM:SeriesDescription", "DICOM:Modality"],
        "conflict_status": "no_conflict",
        "latency_ms": 84,
    },
    {
        "tool_name": "run_ncct_classification",
        "node_name": "NCCT 三分类",
        "agent_name": "Imaging Triage Agent",
        "skill_id": "SKILL_NCCT_CLASSIFY",
        "skill_name": "NCCT 三分类 Skill",
        "stage": "tooling",
        "input_summary": "NCCT 轴位序列，已完成窗宽窗位标准化。",
        "output_summary": "缺血倾向，未见明确颅内出血征象。",
        "confidence_score": 0.92,
        "confidence_method": "mock_calibrated_probability",
        "evidence_refs": [{"source": "NCCT", "slice": 18, "finding": "左侧低密度灶"}],
        "conflict_status": "no_conflict",
        "latency_ms": 126,
    },
    {
        "tool_name": "run_vessel_occlusion_classification",
        "node_name": "血管闭塞三分类",
        "agent_name": "Vessel Analysis Agent",
        "skill_id": "SKILL_VESSEL_OCCLUSION",
        "skill_name": "血管闭塞识别 Skill",
        "stage": "tooling",
        "input_summary": "mCTA 多期血管影像。",
        "output_summary": "提示左侧大血管闭塞风险。",
        "confidence_score": 0.81,
        "confidence_method": "mock_calibrated_probability",
        "evidence_refs": ["mCTA:arterial-phase:left-M1"],
        "conflict_status": "no_conflict",
        "latency_ms": 141,
    },
    {
        "tool_name": "generate_ctp_maps",
        "node_name": "类 CTP 生成",
        "agent_name": "Perfusion Agent",
        "skill_id": "SKILL_MRDPM_CTP",
        "skill_name": "MRDPM 类 CTP 生成 Skill",
        "stage": "tooling",
        "input_summary": "NCCT 与 mCTA 配准后的演示输入。",
        "output_summary": "生成演示用 CBF、CBV、Tmax 引用。",
        "confidence_score": 0.74,
        "confidence_method": "mock_quality_score",
        "evidence_refs": ["artifact:demo/cbf", "artifact:demo/cbv", "artifact:demo/tmax"],
        "conflict_status": "no_conflict",
        "latency_ms": 203,
    },
    {
        "tool_name": "run_stroke_analysis",
        "node_name": "卒中自动分析",
        "agent_name": "Stroke Quantification Agent",
        "skill_id": "SKILL_STROKE_ANALYSIS",
        "skill_name": "卒中定量分析 Skill",
        "stage": "tooling",
        "input_summary": "CBF、CBV、Tmax 演示图与 NCCT 上下文。",
        "output_summary": "核心梗死 18.4 ml，半暗带 46.2 ml，mismatch 2.51。",
        "confidence_score": 0.78,
        "confidence_method": "mock_ensemble_calibration",
        "evidence_refs": [{"metric": "core_infarct_volume", "value": 18.4, "unit": "ml"}],
        "conflict_status": "no_conflict",
        "latency_ms": 188,
    },
    {
        "tool_name": "icv",
        "node_name": "内在一致性校验",
        "agent_name": "Consistency Review Agent",
        "skill_id": "SKILL_ICV",
        "skill_name": "内部一致性校验 Skill",
        "stage": "icv",
        "input_summary": "汇总影像结论与卒中定量指标。",
        "output_summary": "主要定量指标之间未发现内部矛盾。",
        "confidence_score": 0.83,
        "confidence_method": "rule_coverage_ratio",
        "evidence_refs": ["rule:ICV-CORE-PENUMBRA-001"],
        "conflict_status": "no_conflict",
        "latency_ms": 42,
    },
    {
        "tool_name": "ekv",
        "node_name": "外部证据校验",
        "agent_name": "Evidence Verification Agent",
        "skill_id": "SKILL_EKV",
        "skill_name": "外部知识校验 Skill",
        "stage": "ekv",
        "input_summary": "闭塞风险、灌注指标与演示指南证据。",
        "output_summary": "模型结论与一条指南适用条件存在演示冲突，需裁决。",
        "confidence_score": 0.62,
        "confidence_method": "evidence_coverage_ratio",
        "evidence_refs": [
            {"source": "中国脑卒中防治指导规范", "section": "再灌注治疗评估"},
            "rule:EKV-DEMO-CONFLICT-001",
        ],
        "conflict_status": "conflict",
        "latency_ms": 57,
    },
    {
        "tool_name": "consensus_lite",
        "node_name": "一致性裁决",
        "agent_name": "Consensus Agent",
        "skill_id": "SKILL_CONSENSUS",
        "skill_name": "冲突裁决 Skill",
        "stage": "consensus",
        "input_summary": "ICV 通过结果与 EKV 演示冲突。",
        "output_summary": "保留风险提示并建议医生复核，冲突已进入可解释输出。",
        "confidence_score": 0.89,
        "confidence_method": "mock_consensus_score",
        "evidence_refs": ["event:ekv-conflict", "decision:human-review-advised"],
        "conflict_status": "no_conflict",
        "latency_ms": 36,
    },
    {
        "tool_name": "generate_medgemma_report",
        "node_name": "结构化报告生成",
        "agent_name": "Report Agent",
        "skill_id": "SKILL_REPORT_GEN",
        "skill_name": "结构化报告生成 Skill",
        "stage": "summary",
        "input_summary": "已裁决的结论、定量指标和证据引用。",
        "output_summary": "生成演示结构化报告，包含风险与复核建议。",
        "confidence_score": 0.86,
        "confidence_method": "source_completeness_score",
        "evidence_refs": ["run:cockpit-demo", "section:clinical-summary"],
        "conflict_status": "no_conflict",
        "latency_ms": 73,
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_mock_run(run_id: str, patient_id: int, file_id: str, scenario: str) -> tuple[dict, list[dict]]:
    timestamp = _now()
    steps = []
    events = []
    previous_tool = None

    for index, spec in enumerate(NODE_SPECS, start=1):
        node_info = {
            "node_id": spec["tool_name"],
            "node_name": spec["node_name"],
            "agent_name": spec["agent_name"],
            "skill_id": spec["skill_id"],
            "skill_name": spec["skill_name"],
            "tool_name": spec["tool_name"],
            "input_summary": spec["input_summary"],
            "output_summary": spec["output_summary"],
            "confidence_score": spec["confidence_score"],
            "confidence_method": spec["confidence_method"],
            "evidence_refs": deepcopy(spec["evidence_refs"]),
            "conflict_status": spec["conflict_status"],
        }
        steps.append(
            {
                "key": spec["tool_name"],
                "title": spec["node_name"],
                "phase": spec["stage"],
                "status": "completed",
                "message": spec["output_summary"],
                "attempts": 1,
                "retryable": False,
                "depends_on": [previous_tool] if previous_tool else [],
                "node_info": deepcopy(node_info),
            }
        )
        events.append(
            {
                "event_id": f"{run_id}-event-{index}",
                "event_seq": index,
                "event_type": "step_completed",
                "run_id": run_id,
                "status": "completed",
                "agent_name": spec["agent_name"],
                "tool_name": spec["tool_name"],
                "node_name": spec["node_name"],
                "phase": spec["stage"],
                "timestamp": timestamp,
                "latency_ms": spec["latency_ms"],
                "attempt": 1,
                "retryable": False,
                "message": spec["output_summary"],
                "result_summary": spec["output_summary"],
                "input_ref": {"summary": spec["input_summary"]},
                "output_ref": {"summary": spec["output_summary"]},
                "source_tag": "mock",
                "node_info": deepcopy(node_info),
            }
        )
        previous_tool = spec["tool_name"]

    run = {
        "run_id": run_id,
        "patient_id": patient_id,
        "file_id": file_id,
        "status": "succeeded",
        "stage": "done",
        "current_tool": "",
        "created_at": timestamp,
        "updated_at": timestamp,
        "source": "cockpit_demo_mock",
        "source_tag": "mock",
        "execution_mode": "cockpit_demo",
        "scenario": scenario,
        "planner_input": {
            "patient_id": patient_id,
            "file_id": file_id,
            "available_modalities": ["ncct", "mcta"],
            "hemisphere": "left",
        },
        "planner_output": {
            "imaging_path": "ncct_mcta",
            "tool_sequence": [spec["tool_name"] for spec in NODE_SPECS],
        },
        "steps": steps,
        "tool_results": [],
        "plan_frames": [
            {
                "revision": 1,
                "source": "cockpit_demo_mock",
                "created_at": timestamp,
                "tool_sequence": [spec["tool_name"] for spec in NODE_SPECS],
            }
        ],
        "replan_count": 0,
        "termination_reason": "completed",
        "human_checkpoint": None,
        "finalization": {
            "status": "archived",
            "writeback_status": "completed",
            "signed": False,
            "version": "cockpit-demo-v1",
        },
        "result": {
            "summary": "Cockpit mock run completed without model inference.",
            "scenario": scenario,
            "report_result": {
                "report_payload": {
                    "clinical_summary": "演示病例：左侧缺血性卒中风险，建议结合完整临床资料复核。"
                }
            },
        },
    }
    return run, events


def _store_mock_run(patient_id: int = 10001, file_id: str = "demo_case_001", scenario: str = "happy_path") -> dict:
    run_id = DEFAULT_RUN_ID if not MOCK_RUNS else f"cockpit_demo_{uuid4().hex[:10]}"
    run, events = _build_mock_run(run_id, patient_id, file_id, scenario)
    MOCK_RUNS[run_id] = run
    MOCK_EVENTS[run_id] = events
    return deepcopy(run)


def _run_response(run_id: str):
    run = MOCK_RUNS.get(run_id)
    if not run:
        return jsonify({"success": False, "error": "Mock run not found"}), 404
    return jsonify({"success": True, "run": deepcopy(run), "run_state": deepcopy(run)})


def _events_response(run_id: str):
    if run_id not in MOCK_RUNS:
        return jsonify({"success": False, "error": "Mock run not found"}), 404
    return jsonify({"success": True, "run_id": run_id, "events": deepcopy(MOCK_EVENTS[run_id])})


@app.get("/")
def demo_home():
    return redirect(url_for("cockpit_page", run_id=DEFAULT_RUN_ID, patient_id=10001, file_id="demo_case_001"))


@app.get("/cockpit")
def cockpit_page():
    return render_template("patient/upload/cockpit/index.html")


@app.post("/api/strokeclaw/w0/mock-runs")
def create_mock_run():
    payload = request.get_json(silent=True) or {}
    try:
        patient_id = int(payload.get("patient_id") or 10001)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid patient_id"}), 400
    file_id = str(payload.get("file_id") or "demo_case_001").strip()
    scenario = str(payload.get("scenario") or "happy_path").strip()
    run = _store_mock_run(patient_id=patient_id, file_id=file_id, scenario=scenario)
    run_id = run["run_id"]
    return jsonify(
        {
            "success": True,
            "run_id": run_id,
            "run_state": run,
            "status_url": f"/api/strokeclaw/w0/mock-runs/{run_id}",
            "events_url": f"/api/strokeclaw/w0/mock-runs/{run_id}/events",
        }
    )


@app.post("/api/demo/scenarios/<scenario_id>/start")
def start_demo_scenario(scenario_id: str):
    payload = request.get_json(silent=True) or {}
    payload["scenario"] = {"a": "happy_path", "b": "ctp_path", "c": "issue_path"}.get(
        scenario_id.lower(), scenario_id
    )
    try:
        patient_id = int(payload.get("patient_id") or 10001)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid patient_id"}), 400
    run = _store_mock_run(
        patient_id=patient_id,
        file_id=str(payload.get("file_id") or "demo_case_001"),
        scenario=payload["scenario"],
    )
    run_id = run["run_id"]
    return jsonify(
        {
            "success": True,
            "mode": "mock",
            "source_tag": "mock",
            "run_id": run_id,
            "run_state": run,
            "status_url": f"/api/strokeclaw/w0/mock-runs/{run_id}",
            "events_url": f"/api/strokeclaw/w0/mock-runs/{run_id}/events",
            "result_url": "",
        }
    )


@app.get("/api/strokeclaw/w0/mock-runs/<run_id>")
def get_mock_run(run_id: str):
    return _run_response(run_id)


@app.get("/api/strokeclaw/w0/mock-runs/<run_id>/events")
def get_mock_events(run_id: str):
    return _events_response(run_id)


@app.get("/api/agent/runs/<run_id>")
def get_agent_run_alias(run_id: str):
    return _run_response(run_id)


@app.get("/api/agent/runs/<run_id>/events")
def get_agent_events_alias(run_id: str):
    return _events_response(run_id)


@app.get("/api/agent/runs/<run_id>/result")
def get_agent_result_alias(run_id: str):
    run = MOCK_RUNS.get(run_id)
    if not run:
        return jsonify({"success": False, "error": "Mock run not found"}), 404
    return jsonify({"success": True, "run_id": run_id, "result": deepcopy(run["result"])})


@app.get("/api/validation/context")
def validation_context():
    return jsonify(
        {
            "success": True,
            "meta": {
                "patient_id": request.args.get("patient_id") or 10001,
                "file_id": request.args.get("file_id") or "demo_case_001",
                "source_chain": "cockpit_demo_mock",
            },
            "icv": {"status": "pass", "summary": "演示内部一致性校验通过。"},
            "ekv": {"status": "warn", "summary": "演示外部证据存在一项冲突。"},
            "consensus": {"status": "review_required", "summary": "建议医生复核演示冲突。"},
        }
    )


_store_mock_run()


if __name__ == "__main__":
    print(f"Cockpit demo: http://127.0.0.1:5011/cockpit?run_id={DEFAULT_RUN_ID}")
    app.run(host="127.0.0.1", port=5011, debug=False, threaded=True, use_reloader=False)
