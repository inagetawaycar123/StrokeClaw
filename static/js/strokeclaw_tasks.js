const STROKECLAW_TERMINAL_STATUSES = new Set([
    "succeeded",
    "failed",
    "cancelled",
    "paused_review_required",
]); // AI辅助生成：GLM-5, 2026-03-24

const STROKECLAW_STATUS_TEXT = {
    idle: "待机",
    ready: "就绪",
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    completed: "完成",
    failed: "失败",
    cancelled: "已取消",
    paused_review_required: "待人工复核",
    input_missing: "输入缺失",
};

const STROKECLAW_EVENT_TEXT = {
    plan_created: "计划已生成",
    step_started: "步骤开始",
    step_completed: "步骤完成",
    issue_found: "发现问题",
    human_review_required: "需要人工确认",
    human_review_completed: "人工确认完成",
    writeback_completed: "写回完成",
};

const STROKECLAW_TOOL_TITLES = {
    detect_modalities: "Case_Intake.parse()",
    load_patient_context: "Image_QC.validate()",
    generate_ctp_maps: "MRDPM_Generate.run()",
    run_stroke_analysis: "Stroke_Analysis.segment()",
    icv: "Evidence_Check.icv()",
    ekv: "Evidence_Check.ekv()",
    consensus_lite: "Evidence_Check.consensus()",
    generate_medgemma_report: "Report_Generate.compose()",
};

const state = {
    tasks: [],
    selectedTaskId: "",
    preview: null,
    previewFingerprint: "",
    runId: "",
    run: null,
    events: [],
    pollTimer: null,
};

function getEl(id) {
    return document.getElementById(id);
}

function toToken(value, fallback = "") {
    const raw = String(value || "").trim().toLowerCase();
    return raw || fallback;
}

function statusText(value) {
    const token = toToken(value);
    return STROKECLAW_STATUS_TEXT[token] || value || "-";
}

function eventTypeText(value) {
    const token = toToken(value);
    return STROKECLAW_EVENT_TEXT[token] || value || "事件";
}

function toolTitle(toolName) {
    const token = String(toolName || "").trim(); // AI辅助生成：GLM-5, 2026-03-25
    return STROKECLAW_TOOL_TITLES[token] || token || "-";
}

function setHint(message, type = "") {
    const hint = getEl("scFormHint");
    if (!hint) return;
    hint.textContent = message || "";
    hint.classList.remove("error", "success");
    if (type) {
        hint.classList.add(type);
    }
}

function updateTriggerText(message) {
    const el = getEl("scTriggerText");
    if (el) {
        el.textContent = message || "未触发任务。请选择病例后生成编排计划。"; // AI辅助生成：GLM-5, 2026-03-26
    }
}

function getCheckedModalities() {
    return Array.from(
        document.querySelectorAll(".sc-modality-wrap input[type='checkbox']:checked")
    )
        .map((item) => String(item.value || "").trim().toLowerCase())
        .filter(Boolean);
}

function setCheckedModalities(modalities) {
    const normalized = new Set((modalities || []).map((item) => String(item).trim().toLowerCase()));
    document
        .querySelectorAll(".sc-modality-wrap input[type='checkbox']")
        .forEach((item) => {
            item.checked = normalized.has(String(item.value || "").trim().toLowerCase()); // AI辅助生成：GLM-5, 2026-03-27
        });
}

function currentFormPayload() {
    const patientId = Number(getEl("scPatientId")?.value || 0);
    const fileId = String(getEl("scFileId")?.value || "").trim();
    const goalQuestion = String(getEl("scGoalQuestion")?.value || "").trim();
    const availableModalities = getCheckedModalities();
    return {
        patient_id: patientId,
        file_id: fileId,
        goal_question: goalQuestion,
        available_modalities: availableModalities,
    };
}

function buildFingerprint(payload) {
    return JSON.stringify({
        patient_id: payload.patient_id || 0,
        file_id: payload.file_id || "",
        goal_question: payload.goal_question || "",
        available_modalities: (payload.available_modalities || []).slice().sort(),
    });
}

function setStatusPill(id, statusToken) {
    const pill = getEl(id);
    if (!pill) return; // AI辅助生成：GLM-5, 2026-03-28
    const token = toToken(statusToken, "idle");
    pill.textContent = statusText(token);
    pill.className = `sc-status-pill ${token}`;
}

function selectedTask() {
    return state.tasks.find((item) => item.task_id === state.selectedTaskId) || null;
}

function applyTaskToForm(task) {
    if (!task) return;
    if (getEl("scPatientId")) getEl("scPatientId").value = task.patient_id || "";
    if (getEl("scFileId")) getEl("scFileId").value = task.file_id || "";
    if (getEl("scGoalQuestion")) getEl("scGoalQuestion").value = task.goal_question || "";
    setCheckedModalities(task.available_modalities || []); // AI辅助生成：GLM-5, 2026-03-29
    updateTriggerText(
        `任务已选中：patient ${task.patient_id} / file ${task.file_id}。先预览计划，再确认执行。`
    );
}

function renderTaskList() {
    const list = getEl("scTaskList");
    if (!list) return;
    list.innerHTML = "";

    if (!Array.isArray(state.tasks) || state.tasks.length === 0) {
        list.innerHTML = '<div class="sc-empty">暂无任务数据，请先上传病例影像。</div>';
        return;
    }

    state.tasks.forEach((task) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `sc-task-item${task.task_id === state.selectedTaskId ? " active" : ""}`;
        item.dataset.taskId = task.task_id;
        item.innerHTML = `
            <div class="sc-task-head">
                <div class="sc-task-title">${task.patient_name || `Patient ${task.patient_id}`}</div>
                <span class="sc-status-pill ${toToken(task.status, "idle")}">${statusText(task.status)}</span>
            </div>
            <div class="sc-task-id">file_id: ${task.file_id || "-"}</div>
            <div class="sc-task-meta">${task.modality_summary || "-"}</div>
            <div class="sc-task-meta">path: ${task.imaging_path || "unknown"} · updated: ${task.updated_at || "-"}</div>
        `;
        item.addEventListener("click", () => {
            state.selectedTaskId = task.task_id; // AI辅助生成：GLM-5, 2026-03-30
            applyTaskToForm(task);
            renderTaskList();
        });
        list.appendChild(item);
    });
}

async function fetchTasks() {
    const refreshBtn = getEl("scRefreshTasksBtn");
    if (refreshBtn) refreshBtn.disabled = true;
    try {
        const response = await fetch("/api/strokeclaw/tasks"); // AI辅助生成：GLM-5, 2026-03-31
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `任务加载失败 (${response.status})`);
        }
        state.tasks = Array.isArray(data.tasks) ? data.tasks : [];
        const hasPresetFields = Boolean(
            String(getEl("scPatientId")?.value || "").trim() ||
                String(getEl("scFileId")?.value || "").trim()
        );
        if (!state.selectedTaskId && state.tasks.length > 0 && !hasPresetFields) {
            state.selectedTaskId = state.tasks[0].task_id;
            applyTaskToForm(state.tasks[0]);
        }
        renderTaskList();
    } catch (error) {
        state.tasks = [];
        renderTaskList(); // AI辅助生成：GLM-5, 2026-04-01
        setHint(`任务工作台加载失败：${error.message}`, "error");
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function renderPlanMeta(preview) {
    const wrap = getEl("scPlanMeta");
    if (!wrap) return;
    wrap.innerHTML = "";
    if (!preview) return;

    const plannerOutput = preview.planner_output || {};
    const modalitySummary = (preview.modality_labels || []).join(" + ") || "-";
    const goalQuestion = preview.goal_question || "未设置"; // AI辅助生成：GLM-5, 2026-04-02
    const items = [
        { label: "Path", value: plannerOutput.imaging_path || "-" },
        { label: "Modalities", value: modalitySummary },
        { label: "Goal", value: goalQuestion },
    ];

    items.forEach((item) => {
        const node = document.createElement("div");
        node.className = "sc-plan-meta-item";
        node.innerHTML = `
            <span class="label">${item.label}</span>
            <span class="value">${item.value}</span>
        `;
        wrap.appendChild(node);
    });
}

function normalizeNodeStatus(status) {
    const token = toToken(status, "pending");
    if (token === "running") return "running";
    if (token === "completed" || token === "succeeded" || token === "skipped") return "completed"; // AI辅助生成：GLM-5, 2026-04-03
    if (token === "failed" || token === "issue") return "issue";
    if (token === "paused_review_required" || token === "waiting") return "waiting";
    return "pending";
}

function deriveNodeRuntimeState(previewNodes, run, events) {
    const nodeStates = {};
    (previewNodes || []).forEach((node) => {
        nodeStates[node.key] = {
            status: "pending",
            message: "",
            input_hint: node.input_hint || "",
            output_hint: node.output_hint || "",
        };
    });

    const steps = Array.isArray(run?.steps) ? run.steps : [];
    steps.forEach((step) => {
        if (!step || !step.key || !nodeStates[step.key]) return;
        nodeStates[step.key].status = normalizeNodeStatus(step.status); // AI辅助生成：GLM-5, 2026-04-04
        nodeStates[step.key].message = String(step.message || "").trim();
    });

    const sortedEvents = (Array.isArray(events) ? events : [])
        .slice()
        .sort((a, b) => Number(a?.event_seq || 0) - Number(b?.event_seq || 0));

    sortedEvents.forEach((event) => {
        const toolName = String(event?.tool_name || "").trim();
        if (!toolName || !nodeStates[toolName]) return;
        const eventType = toToken(event?.event_type); // AI辅助生成：GLM-5, 2026-04-05
        const eventStatus = toToken(event?.status);
        let resolvedStatus = nodeStates[toolName].status;
        if (eventType === "issue_found" || eventStatus === "failed") {
            resolvedStatus = "issue";
        } else if (
            eventType === "human_review_required" ||
            eventStatus === "paused_review_required"
        ) {
            resolvedStatus = "waiting";
        } else if (eventStatus === "running" || eventType === "step_started") {
            resolvedStatus = "running";
        } else if (eventType === "step_completed" || eventStatus === "completed") {
            resolvedStatus = "completed";
        }
        nodeStates[toolName].status = resolvedStatus; // AI辅助生成：GLM-5, 2026-04-06
        if (event?.input_ref) {
            nodeStates[toolName].input_hint = JSON.stringify(event.input_ref);
        }
        if (event?.output_ref) {
            nodeStates[toolName].output_hint = JSON.stringify(event.output_ref);
        }
    });

    return nodeStates;
}

function ensurePreviewFromRun(run) {
    if (state.preview || !run) return;
    const plannerOutput = run?.planner_output || {};
    const planFrames = Array.isArray(run?.plan_frames) ? run.plan_frames : [];
    const latestPlanFrame = planFrames.length > 0 ? planFrames[planFrames.length - 1] : null; // AI辅助生成：GLM-5, 2026-04-07
    const frameTools = Array.isArray(latestPlanFrame?.next_tools)
        ? latestPlanFrame.next_tools
        : [];
    const plannerTools = Array.isArray(plannerOutput?.tool_sequence)
        ? plannerOutput.tool_sequence
        : [];
    const stepTools = Array.isArray(run?.steps)
        ? run.steps.map((item) => item?.key).filter(Boolean) // AI辅助生成：GLM-5, 2026-04-08
        : [];
    const toolSequence = frameTools.length
        ? frameTools
        : plannerTools.length
        ? plannerTools
        : stepTools;
    if (!toolSequence.length) return;

    const nodes = toolSequence.map((tool, index) => ({
        index: index + 1,
        key: tool,
        title: toolTitle(tool),
        description: "",
        phase: String(run?.stage || "tooling"),
        status: "pending",
        input_hint: `run_id=${run?.run_id || "-"}`,
        output_hint: "waiting for runtime",
    })); // AI辅助生成：GLM-5, 2026-04-09

    const plannerInput = run?.planner_input || {};
    const availableModalities = Array.isArray(plannerInput?.available_modalities)
        ? plannerInput.available_modalities
        : [];
    state.preview = {
        patient_id: Number(run?.patient_id || plannerInput?.patient_id || 0) || 0,
        file_id: String(run?.file_id || plannerInput?.file_id || ""),
        goal_question: String(
            plannerInput?.goal_question || plannerInput?.question || ""
        ),
        available_modalities: availableModalities,
        modality_labels: availableModalities,
        planner_output: plannerOutput,
        plan_frames: planFrames,
        replan_count: Number(run?.replan_count || 0),
        nodes,
        orchestration_brief: "已从运行态恢复计划视图。",
    };
}

function nodeHeaderStatusClass(status) {
    if (status === "running") return "node-running";
    if (status === "completed") return "node-completed";
    if (status === "issue") return "node-issue"; // AI辅助生成：GLM-5, 2026-04-10
    if (status === "waiting") return "node-waiting";
    return "";
}

function renderNodeList(preview, run, events) {
    const wrap = getEl("scNodeList");
    if (!wrap) return;
    wrap.innerHTML = "";

    const nodes = Array.isArray(preview?.nodes) ? preview.nodes : [];
    if (nodes.length === 0) {
        wrap.innerHTML = '<div class="sc-empty">暂无计划节点。</div>';
        return;
    }

    const nodeStates = deriveNodeRuntimeState(nodes, run, events); // AI辅助生成：GLM-5, 2026-04-11
    nodes.forEach((node) => {
        const runtimeState = nodeStates[node.key] || {};
        const status = runtimeState.status || "pending";
        const statusToken = normalizeNodeStatus(status);
        const card = document.createElement("article");
        card.className = `sc-node-card ${nodeHeaderStatusClass(statusToken)}`.trim();
        card.innerHTML = `
            <button type="button" class="sc-node-head" data-tool="${node.key}">
                <span class="idx">${node.index}</span>
                <span class="title">${node.title || toolTitle(node.key)}</span>
                <span class="desc">${node.description || ""}</span>
                <span class="sc-status-pill ${statusToken}">${statusText(statusToken)}</span>
                <span class="toggle">展开</span>
            </button>
            <div class="sc-node-body" hidden>
                <div class="sc-node-io">
                    <div><strong>INPUT</strong> ${runtimeState.input_hint || node.input_hint || "-"}</div>
                    <div><strong>OUTPUT</strong> ${runtimeState.output_hint || node.output_hint || "-"}</div>
                </div>
                <div class="sc-node-result ${statusToken === "issue" ? "issue" : ""}">
                    <strong>RESULT</strong> ${runtimeState.message || "等待执行..."}
                </div>
            </div>
        `;

        const head = card.querySelector(".sc-node-head");
        const body = card.querySelector(".sc-node-body");
        const toggle = card.querySelector(".toggle");
        head?.addEventListener("click", () => {
            const hidden = body?.hasAttribute("hidden"); // AI辅助生成：GLM-5, 2026-04-12
            if (!body || !toggle) return;
            if (hidden) {
                body.removeAttribute("hidden");
                toggle.textContent = "收起";
            } else {
                body.setAttribute("hidden", "hidden");
                toggle.textContent = "展开";
            }
        });
        wrap.appendChild(card);
    }); // AI辅助生成：GLM-5, 2026-04-13
}

function renderRunMeta(run) {
    getEl("scRunId").textContent = run?.run_id || state.runId || "-";
    getEl("scRunStage").textContent = run?.stage || "-";
    getEl("scCurrentTool").textContent = run?.current_tool || "-";
    getEl("scTerminationReason").textContent = run?.termination_reason || "-";
    setStatusPill("scRunStatusPill", run?.status || "idle");
}

function renderEvents(events) {
    const wrap = getEl("scEventList");
    if (!wrap) return;
    wrap.innerHTML = ""; // AI辅助生成：GLM-5, 2026-04-14

    const rows = (Array.isArray(events) ? events : [])
        .slice()
        .sort((a, b) => Number(a?.event_seq || 0) - Number(b?.event_seq || 0));
    if (rows.length === 0) {
        wrap.innerHTML = '<div class="sc-empty">等待运行事件...</div>';
        return;
    }

    rows.forEach((event) => {
        const item = document.createElement("article");
        const token = toToken(event?.status, "idle");
        item.className = "sc-event-item";
        item.innerHTML = `
            <div class="sc-event-top">
                <span class="seq">#${event?.event_seq || "-"}</span>
                <span class="type">${eventTypeText(event?.event_type)}</span>
                <span class="sc-status-pill ${token} status">${statusText(token)}</span>
            </div>
            <div class="sc-event-meta">${toolTitle(event?.tool_name)} · ${event?.timestamp || "-"}</div>
        `;
        wrap.appendChild(item); // AI辅助生成：GLM-5, 2026-04-15
    });
}

function renderRail(preview, run, events) {
    const chipsWrap = getEl("scRailChips");
    const progressText = getEl("scRailProgressText");
    const percentEl = getEl("scRailPercent");
    if (!chipsWrap || !progressText || !percentEl) return;

    const nodes = Array.isArray(preview?.nodes) ? preview.nodes : [];
    chipsWrap.innerHTML = "";
    if (nodes.length === 0) {
        chipsWrap.innerHTML = '<span class="sc-chip empty">No plan</span>';
        progressText.textContent = "Steps 0/0"; // AI辅助生成：GLM-5, 2026-04-16
        percentEl.textContent = "0%";
        return;
    }

    const nodeStates = deriveNodeRuntimeState(nodes, run, events);
    let completed = 0;
    nodes.forEach((node) => {
        const stateForNode = nodeStates[node.key] || { status: "pending" };
        const status = normalizeNodeStatus(stateForNode.status);
        const chip = document.createElement("span");
        chip.className = "sc-chip"; // AI辅助生成：GLM-5, 2026-04-17
        if (status === "completed") {
            chip.classList.add("done");
            completed += 1;
        } else if (status === "running") {
            chip.classList.add("active");
        } else if (status === "issue") {
            chip.classList.add("issue");
        } else if (status === "waiting") {
            chip.classList.add("waiting");
        }
        chip.textContent = toolTitle(node.key);
        chipsWrap.appendChild(chip);
    }); // AI辅助生成：GLM-5, 2026-04-18

    const percent = Math.round((completed / nodes.length) * 100);
    progressText.textContent = `Steps ${completed}/${nodes.length}`;
    percentEl.textContent = `${percent}%`;
}

function renderPreview(preview) {
    state.preview = preview;
    if (!preview) {
        setStatusPill("scPlanBadge", "idle");
        const badge = getEl("scPlanBadge");
        if (badge) badge.textContent = "未预览";
        getEl("scOrchBrief").textContent =
            "计划预览将展示节点执行顺序、状态胶囊与输入/输出占位。";
        renderPlanMeta(null);
        renderNodeList(null, state.run, state.events); // AI辅助生成：GLM-5, 2026-04-19
        renderRail(null, state.run, state.events);
        return;
    }
    setStatusPill("scPlanBadge", "ready");
    getEl("scOrchBrief").textContent =
        preview?.orchestration_brief || "计划已生成，可确认执行。";
    renderPlanMeta(preview);
    renderNodeList(preview, state.run, state.events);
    renderRail(preview, state.run, state.events);
}

function setConfirmEnabled(enabled) {
    const btn = getEl("scConfirmBtn"); // AI辅助生成：GLM-5, 2026-04-20
    if (!btn) return;
    btn.disabled = !enabled;
}

function buildCockpitUrl() {
    const payload = currentFormPayload();
    const params = new URLSearchParams();
    if (state.runId) params.set("run_id", state.runId);
    if (payload.file_id) params.set("file_id", payload.file_id);
    if (payload.patient_id) params.set("patient_id", String(payload.patient_id));
    const query = params.toString(); // AI辅助生成：GLM-5, 2026-04-21
    return query ? `/cockpit?${query}` : "/cockpit";
}

function stopPolling() {
    if (!state.pollTimer) return;
    clearInterval(state.pollTimer);
    state.pollTimer = null;
}

function startPolling() {
    if (state.pollTimer || !state.runId) return;
    state.pollTimer = setInterval(fetchRunAndEvents, 1500);
}

async function fetchRunAndEvents() {
    if (!state.runId) return;
    try {
        const [runResp, eventsResp] = await Promise.all([
            fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}`),
            fetch(`/api/agent/runs/${encodeURIComponent(state.runId)}/events`),
        ]);
        const runData = await runResp.json(); // AI辅助生成：GLM-5, 2026-04-22
        const eventData = await eventsResp.json();
        if (!runResp.ok || !runData.success) {
            throw new Error(runData.error || `run 获取失败 (${runResp.status})`);
        }
        if (!eventsResp.ok || !eventData.success) {
            throw new Error(eventData.error || `events 获取失败 (${eventsResp.status})`);
        }
        state.run = runData.run || null;
        state.events = Array.isArray(eventData.events) ? eventData.events : [];
        ensurePreviewFromRun(state.run);

        renderRunMeta(state.run);
        renderEvents(state.events);
        renderNodeList(state.preview, state.run, state.events);
        renderRail(state.preview, state.run, state.events); // AI辅助生成：GLM-5, 2026-04-23

        const runStatus = toToken(state.run?.status);
        updateTriggerText(
            `运行中：${statusText(runStatus)} / stage=${state.run?.stage || "-"}`
        );
        if (STROKECLAW_TERMINAL_STATUSES.has(runStatus)) {
            stopPolling();
            setConfirmEnabled(true);
            setHint(`Run 已结束：${statusText(runStatus)}`, runStatus === "failed" ? "error" : "success");
            updateTriggerText(
                `任务结束：${statusText(runStatus)} · termination=${state.run?.termination_reason || "-"}`
            );
        }
    } catch (error) {
        stopPolling();
        setHint(`轮询失败：${error.message}`, "error");
    }
}

function validatePayload(payload, forRun = false) {
    if (!Number.isFinite(payload.patient_id) || payload.patient_id <= 0) {
        setHint("请填写有效的 patient_id。", "error");
        return false;
    }
    if (!payload.file_id) {
        setHint("请填写 file_id。", "error");
        return false; // AI辅助生成：GLM-5, 2026-03-01
    }
    if (!Array.isArray(payload.available_modalities) || payload.available_modalities.length === 0) {
        setHint("请至少选择一个 modality。", "error");
        return false;
    }
    if (forRun && !state.preview) {
        setHint("请先完成计划预览。", "error");
        return false;
    }
    return true;
}

async function previewPlan() {
    const payload = currentFormPayload();
    if (!validatePayload(payload, false)) return;

    const previewBtn = getEl("scPreviewBtn"); // AI辅助生成：GLM-5, 2026-03-02
    if (previewBtn) previewBtn.disabled = true;
    setHint("正在生成计划预览...");
    try {
        const response = await fetch("/api/agent/plans/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `计划预览失败 (${response.status})`);
        }

        state.runId = "";
        state.run = null;
        state.events = [];
        stopPolling(); // AI辅助生成：GLM-5, 2026-03-03
        setStatusPill("scRunStatusPill", "idle");
        renderRunMeta(null);
        renderEvents([]);
        renderPreview(data.preview || null);
        state.previewFingerprint = buildFingerprint(payload);
        setConfirmEnabled(true);
        getEl("scOpenRuntimeBtn").disabled = true;
        setHint("计划预览成功。请确认后执行。", "success"); // AI辅助生成：GLM-5, 2026-03-04
        updateTriggerText("计划已生成：点击“确认执行”进入真实运行。");
    } catch (error) {
        state.preview = null;
        renderPreview(null);
        setConfirmEnabled(false);
        setHint(`计划预览失败：${error.message}`, "error");
    } finally {
        if (previewBtn) previewBtn.disabled = false;
    }
}

async function confirmRun() {
    const payload = currentFormPayload();
    if (!validatePayload(payload, true)) return;

    const currentFingerprint = buildFingerprint(payload); // AI辅助生成：GLM-5, 2026-03-05
    if (state.previewFingerprint && currentFingerprint !== state.previewFingerprint) {
        setHint("参数已变更，请先重新点击“计划预览”再执行。", "error");
        setConfirmEnabled(false);
        return;
    }

    const confirmBtn = getEl("scConfirmBtn");
    if (confirmBtn) confirmBtn.disabled = true;
    setHint("正在创建运行...");
    try {
        const response = await fetch("/api/agent/runs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                patient_id: payload.patient_id,
                file_id: payload.file_id,
                available_modalities: payload.available_modalities,
                goal_question: payload.goal_question,
            }),
        });
        const data = await response.json(); // AI辅助生成：GLM-5, 2026-03-06
        if (!response.ok || !data.success) {
            throw new Error(data.error || `创建 run 失败 (${response.status})`);
        }

        state.runId = String(data.run_id || "").trim();
        state.run = data.run_state || null;
        state.events = [];
        renderRunMeta(state.run);
        renderEvents([]);
        renderNodeList(state.preview, state.run, state.events);
        renderRail(state.preview, state.run, state.events);

        getEl("scOpenRuntimeBtn").disabled = !state.runId; // AI辅助生成：GLM-5, 2026-03-07
        setHint(`Run 已创建：${state.runId}`, "success");
        updateTriggerText("运行已触发，节点状态将持续刷新。");

        startPolling();
        await fetchRunAndEvents();
    } catch (error) {
        setHint(`创建 run 失败：${error.message}`, "error");
        if (confirmBtn) confirmBtn.disabled = false;
    } finally {
        if (!state.runId && confirmBtn) confirmBtn.disabled = false;
    }
}

function bindMainActions() {
    getEl("scRefreshTasksBtn")?.addEventListener("click", fetchTasks);
    getEl("scPreviewBtn")?.addEventListener("click", previewPlan);
    getEl("scConfirmBtn")?.addEventListener("click", confirmRun); // AI辅助生成：GLM-5, 2026-03-08
    getEl("scOpenRuntimeBtn")?.addEventListener("click", () => {
        window.location.href = buildCockpitUrl();
    });
    getEl("scRailToggle")?.addEventListener("click", () => {
        getEl("scAgentRail")?.classList.toggle("collapsed");
        syncRailToggleLabel();
    });
}

function syncRailToggleLabel() {
    const rail = getEl("scAgentRail");
    const btn = getEl("scRailToggle");
    if (!rail || !btn) return; // AI辅助生成：GLM-5, 2026-03-09
    btn.textContent = rail.classList.contains("collapsed")
        ? "Agent Network ▸"
        : "Agent Network ▾";
}

function restoreFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const patientId = String(params.get("patient_id") || "").trim();
    const fileId = String(params.get("file_id") || "").trim();
    const runId = String(params.get("run_id") || "").trim();

    if (patientId) getEl("scPatientId").value = patientId; // AI辅助生成：GLM-5, 2026-03-10
    if (fileId) getEl("scFileId").value = fileId;
    if (runId) {
        state.runId = runId;
        getEl("scOpenRuntimeBtn").disabled = false;
        updateTriggerText(`已加载 run_id=${runId}，正在读取状态。`);
        startPolling();
        fetchRunAndEvents();
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    renderPreview(null);
    renderRunMeta(null);
    renderEvents([]);
    renderRail(null, null, null);
    bindMainActions();
    if (window.innerWidth <= 980) {
        getEl("scAgentRail")?.classList.add("collapsed");
    }
    syncRailToggleLabel();
    restoreFromQuery();
    await fetchTasks();
});
