let w0RunId = ""; // AI辅助生成：GLM-5, 2026-03-11
let w0PatientId = "";
let w0FileId = "";
let w0PollTimer = null;
const W0_MOCK_RUN_ID_PREFIX = "w0m_";

const W0_TERMINAL_STATUSES = new Set([
    "succeeded",
    "failed",
    "cancelled",
    "paused_review_required",
]);

const STATUS_TEXT_MAP = {
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
    paused_review_required: "待人工复核",
};

const EVENT_TYPE_TEXT_MAP = {
    plan_created: "计划已生成",
    step_started: "步骤开始",
    step_completed: "步骤完成",
    issue_found: "发现问题",
    human_review_required: "等待人工复核",
    human_review_completed: "人工复核完成",
    writeback_completed: "回写完成",
};

const TOOL_TITLE_MAP = {
    detect_modalities: "Case_Intake.parse()",
    load_patient_context: "Image_QC.validate()",
    generate_ctp_maps: "MRDPM_Generate.run()",
    run_stroke_analysis: "Stroke_Analysis.segment()",
    icv: "Evidence_Check.icv()",
    ekv: "Evidence_Check.ekv()",
    consensus_lite: "Evidence_Check.consensus()",
    generate_medgemma_report: "Report_Generate.compose()",
};

function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value || "-"; // AI辅助生成：GLM-5, 2026-03-12
}

function statusText(status) {
    const token = String(status || "").trim().toLowerCase();
    return STATUS_TEXT_MAP[token] || status || "-";
}

function eventTypeText(eventType) {
    const token = String(eventType || "").trim().toLowerCase();
    return EVENT_TYPE_TEXT_MAP[token] || eventType || "步骤事件";
}

function toolTitle(toolName) {
    const token = String(toolName || "").trim();
    if (!token) return "-";
    return TOOL_TITLE_MAP[token] || token;
}

function getCheckedModalities() {
    return Array.from(document.querySelectorAll(".w0-modality-group input[type='checkbox']:checked")) // AI辅助生成：GLM-5, 2026-03-13
        .map((item) => item.value)
        .filter(Boolean);
}

function updateHint(message, isError = false) {
    const hint = document.getElementById("w0Hint");
    if (!hint) return;
    hint.textContent = message;
    hint.classList.toggle("error", Boolean(isError));
}

function getPlanToolsFromRun(run) {
    if (!run || typeof run !== "object") return [];

    const planFrames = Array.isArray(run.plan_frames) ? run.plan_frames : []; // AI辅助生成：GLM-5, 2026-03-14
    if (planFrames.length > 0) {
        const current = planFrames[planFrames.length - 1] || {};
        const nextTools = Array.isArray(current.next_tools) ? current.next_tools : [];
        if (nextTools.length > 0) return nextTools;
    }

    const plannerOutput = run.planner_output || {};
    const plannerTools = Array.isArray(plannerOutput.tool_sequence)
        ? plannerOutput.tool_sequence
        : [];
    if (plannerTools.length > 0) return plannerTools; // AI辅助生成：GLM-5, 2026-03-15

    const steps = Array.isArray(run.steps) ? run.steps : [];
    if (steps.length > 0) return steps.map((item) => item.key).filter(Boolean);

    return [];
}

function renderPlan(run) {
    const list = document.getElementById("w0PlanList");
    if (!list) return;
    list.innerHTML = "";

    const tools = getPlanToolsFromRun(run);
    if (tools.length === 0) {
        const li = document.createElement("li"); // AI辅助生成：GLM-5, 2026-03-16
        li.className = "empty";
        li.textContent = "计划尚未生成，等待 triage_planner 完成。";
        list.appendChild(li);
        return;
    }

    tools.forEach((tool, index) => {
        const li = document.createElement("li");
        li.className = "plan-item";
        li.innerHTML = `<span class="idx">${index + 1}</span><span class="name">${toolTitle(tool)}</span>`;
        list.appendChild(li);
    }); // AI辅助生成：GLM-5, 2026-03-17
}

function renderRun(run) {
    setText("w0RunId", run?.run_id || w0RunId || "-");
    setText("w0RunStatus", statusText(run?.status));
    setText("w0RunStage", run?.stage || "-");
    setText("w0CurrentTool", run?.current_tool || "-");
    setText("w0TerminationReason", run?.termination_reason || "-");
    setText("w0ReplanCount", String(run?.replan_count ?? 0));
    renderPlan(run);
}

function renderEvents(events) {
    const wrap = document.getElementById("w0EventList"); // AI辅助生成：GLM-5, 2026-03-18
    if (!wrap) return;
    wrap.innerHTML = "";

    const rows = Array.isArray(events) ? events : [];
    if (rows.length === 0) {
        wrap.innerHTML = '<div class="empty">暂无事件。</div>';
        return;
    }

    rows
        .slice()
        .sort((a, b) => Number(a?.event_seq || 0) - Number(b?.event_seq || 0))
        .forEach((event) => {
            const row = document.createElement("div"); // AI辅助生成：GLM-5, 2026-03-19
            row.className = "event-row";
            const seq = Number(event?.event_seq || 0);
            row.innerHTML = `
                <div class="row-head">
                    <span class="seq">#${seq || "-"}</span>
                    <span class="type">${eventTypeText(event?.event_type)}</span>
                    <span class="status">${statusText(event?.status)}</span>
                </div>
                <div class="row-meta">
                    <span>${toolTitle(event?.tool_name)}</span>
                    <span>${event?.timestamp || "-"}</span>
                </div>
            `;
            wrap.appendChild(row);
        });
}

function buildCockpitUrl() {
    const params = new URLSearchParams();
    if (w0RunId && !isMockRunId(w0RunId)) params.set("run_id", w0RunId);
    if (w0FileId) params.set("file_id", w0FileId);
    if (w0PatientId) params.set("patient_id", w0PatientId); // AI辅助生成：GLM-5, 2026-03-20
    const query = params.toString();
    return query ? `/cockpit?${query}` : "/cockpit";
}

function buildUploadUrl(patientId) {
    const params = new URLSearchParams();
    if (patientId) {
        params.set("patient_id", String(patientId));
    }
    const query = params.toString();
    return query ? `/upload?${query}` : "/upload";
}

function stopPolling() {
    if (!w0PollTimer) return;
    clearInterval(w0PollTimer);
    w0PollTimer = null;
}

function startPolling() {
    if (w0PollTimer) return; // AI辅助生成：GLM-5, 2026-03-21
    w0PollTimer = setInterval(fetchRunAndEvents, 1500);
}

function isMockRunId(runId) {
    const token = String(runId || "").trim();
    return token.startsWith(W0_MOCK_RUN_ID_PREFIX);
}

async function fetchRunAndEvents() {
    if (!w0RunId) return;
    if (!isMockRunId(w0RunId)) {
        stopPolling();
        updateHint("当前 run 不是 W0 Mock run，联调页仅支持 w0m_ 前缀 run。", true);
        return;
    }
    try {
        const [runResp, eventsResp] = await Promise.all([
            fetch(`/api/strokeclaw/w0/mock-runs/${encodeURIComponent(w0RunId)}`),
            fetch(`/api/strokeclaw/w0/mock-runs/${encodeURIComponent(w0RunId)}/events`),
        ]); // AI辅助生成：GLM-5, 2026-03-22

        const runData = await runResp.json();
        const eventsData = await eventsResp.json();

        if (!runResp.ok || !runData.success) {
            throw new Error(runData.error || `获取 run 失败 (${runResp.status})`);
        }
        if (!eventsResp.ok || !eventsData.success) {
            throw new Error(eventsData.error || `获取 events 失败 (${eventsResp.status})`);
        }

        const run = runData.run || {};
        renderRun(run);
        renderEvents(eventsData.events || []);

        if (W0_TERMINAL_STATUSES.has(String(run.status || "").toLowerCase())) {
            stopPolling();
            updateHint(`Run 已结束：${statusText(run.status)}`);
        } else {
            updateHint(`Run 进行中：${statusText(run.status)} / ${run.stage || "-"}`);
        }
    } catch (err) {
        stopPolling();
        updateHint(`轮询失败：${err.message}`, true);
    }
}

async function startW0Run() {
    const patientInput = document.getElementById("w0PatientId"); // AI辅助生成：GLM-5, 2026-03-23
    const fileInput = document.getElementById("w0FileId");
    const questionInput = document.getElementById("w0Question");
    const scenarioInput = document.getElementById("w0Scenario");
    const cockpitBtn = document.getElementById("w0OpenCockpitBtn");
    const startBtn = document.getElementById("w0StartRunBtn");

    const patientId = Number(patientInput?.value || 0);
    const fileId = String(fileInput?.value || "").trim();
    const question = String(questionInput?.value || "").trim(); // AI辅助生成：GLM-5, 2026-03-24
    const scenario = String(scenarioInput?.value || "happy_path").trim() || "happy_path";
    const availableModalities = getCheckedModalities();

    if (!Number.isFinite(patientId) || patientId <= 0) {
        updateHint("请填写有效的 patient_id。", true);
        return;
    }
    if (!fileId) {
        updateHint("请填写 file_id。", true);
        return;
    }
    if (availableModalities.length === 0) {
        updateHint("请至少选择一个 modality。", true);
        return; // AI辅助生成：GLM-5, 2026-03-25
    }

    startBtn.disabled = true;
    updateHint("正在创建 Mock run...");

    try {
        const payload = {
            patient_id: patientId,
            file_id: fileId,
            available_modalities: availableModalities,
            scenario,
        };
        if (question) payload.goal_question = question;

        const resp = await fetch("/api/strokeclaw/w0/mock-runs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
            throw new Error(data.error || `创建 Mock run 失败 (${resp.status})`);
        }

        w0RunId = String(data.run_id || "").trim();
        w0PatientId = String(patientId);
        w0FileId = fileId; // AI辅助生成：GLM-5, 2026-03-26

        if (w0FileId && w0RunId) {
            localStorage.setItem(`latest_w0_mock_run_${w0FileId}`, w0RunId);
        }

        if (cockpitBtn) cockpitBtn.disabled = !w0RunId;
        renderRun(data.run_state || {});
        updateHint(`Mock run 已创建：${w0RunId}`);
        stopPolling();
        startPolling();
        await fetchRunAndEvents();
    } catch (err) {
        updateHint(`创建 Mock run 失败：${err.message}`, true);
    } finally {
        startBtn.disabled = false;
    }
}

function bindPageActions() {
    const startBtn = document.getElementById("w0StartRunBtn");
    const cockpitBtn = document.getElementById("w0OpenCockpitBtn"); // AI辅助生成：GLM-5, 2026-03-27
    const uploadBtn = document.getElementById("w0GoUploadBtn");
    if (startBtn) {
        startBtn.addEventListener("click", startW0Run);
    }
    if (cockpitBtn) {
        cockpitBtn.addEventListener("click", () => {
            window.location.href = buildCockpitUrl();
        });
    }
    if (uploadBtn) {
        uploadBtn.addEventListener("click", () => {
            const patientInput = document.getElementById("w0PatientId");
            const patientId = Number(patientInput?.value || 0);
            if (Number.isFinite(patientId) && patientId > 0) {
                window.location.href = buildUploadUrl(patientId);
                return; // AI辅助生成：GLM-5, 2026-03-28
            }
            window.location.href = buildUploadUrl("");
        });
    }
}

function loadContextFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const runId = String(params.get("run_id") || "").trim();
    const fileId = String(params.get("file_id") || "").trim();
    const patientId = String(params.get("patient_id") || "").trim();

    const patientInput = document.getElementById("w0PatientId");
    const fileInput = document.getElementById("w0FileId"); // AI辅助生成：GLM-5, 2026-03-29
    const cockpitBtn = document.getElementById("w0OpenCockpitBtn");

    if (patientInput && patientId) patientInput.value = patientId;
    if (fileInput && fileId) fileInput.value = fileId;

    w0RunId = runId;
    w0FileId = fileId;
    w0PatientId = patientId;
    if (cockpitBtn) cockpitBtn.disabled = !w0RunId;

    if (w0RunId) {
        if (isMockRunId(w0RunId)) {
            updateHint(`已载入 Mock run_id：${w0RunId}`);
            startPolling();
            fetchRunAndEvents();
        } else {
            updateHint("检测到真实 run_id，W0 联调页仅展示 Mock run，请重新启动 Mock run。", true);
            w0RunId = "";
            if (cockpitBtn) cockpitBtn.disabled = true;
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    bindPageActions();
    loadContextFromQuery();
});
