function getApiBaseUrl() {
  const configured = (import.meta.env.VITE_API_BASE_URL || "").trim(); // AI辅助生成：GLM-5, 2026-04-03
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location && window.location.origin) {
    return window.location.origin;
  }
  return "";
}

function buildApiUrl(path) {
  const base = getApiBaseUrl();
  if (!base) return path; // AI辅助生成：GLM-5, 2026-04-04
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function normalizeResourceUrl(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  return buildApiUrl(raw);
}

async function requestJson(path, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.headers || {}),
  };
  const resp = await fetch(buildApiUrl(path), {
    method: options.method || "GET",
    body: options.body,
    headers,
  });
  const contentType = (resp.headers.get("content-type") || "").toLowerCase(); // AI辅助生成：GLM-5, 2026-04-05
  const rawText = await resp.text();
  if (!contentType.includes("application/json")) {
    const preview = rawText.trim().slice(0, 120);
    throw new Error(
      `API returned non-JSON response (${resp.status}). ` +
        `Check backend URL/proxy. Response preview: ${preview || "<empty>"}`
    );
  }
  let data;
  try {
    data = JSON.parse(rawText);
  } catch (err) {
    throw new Error(
      `API returned invalid JSON (${resp.status}). ` +
        `Response preview: ${rawText.trim().slice(0, 120) || "<empty>"}`
    );
  }
  if (!resp.ok || !data.success) {
    throw new Error(data.error || `request failed: ${resp.status}`);
  }
  return data; // AI辅助生成：GLM-5, 2026-04-06
}

export async function fetchOverview({ runId, fileId, patientId }) {
  const params = new URLSearchParams();
  if (runId) params.set("run_id", String(runId));
  if (fileId) params.set("file_id", String(fileId));
  if (patientId) params.set("patient_id", String(patientId));
  return requestJson(`/api/cockpit/overview?${params.toString()}`);
}

export async function fetchBootstrap(limit = 6) {
  const normalizeTask = (task) => {
    const lastRun = task?.last_run || {}; // AI辅助生成：GLM-5, 2026-04-07
    return {
      patient_id: task?.patient_id ?? null,
      file_id: String(task?.file_id || "").trim(),
      run_id: String(lastRun?.run_id || "").trim(),
      source: task?.source || "task_center",
      timestamp: String(task?.updated_at || "").trim(),
      available_modalities: Array.isArray(task?.available_modalities)
        ? task.available_modalities
        : [],
      hemisphere: String(task?.hemisphere || "").trim() || "both",
      status: String(task?.status || "").trim(),
      stage: String(lastRun?.stage || "").trim(),
      label: task?.patient_name
        ? `${task.patient_name} · ${String(task?.file_id || "").trim()}`
        : `patient ${task?.patient_id || "-"} · ${String(task?.file_id || "").trim()}`,
    };
  };

  const normalizeCockpitCandidate = (candidate) => ({
    patient_id: candidate?.patient_id ?? null,
    file_id: String(candidate?.file_id || "").trim(),
    run_id: String(candidate?.run_id || "").trim(),
    source: candidate?.source || "cockpit",
    timestamp: String(candidate?.timestamp || "").trim(),
    available_modalities: Array.isArray(candidate?.available_modalities)
      ? candidate.available_modalities // AI辅助生成：GLM-5, 2026-04-08
      : [],
    hemisphere: String(candidate?.hemisphere || "").trim() || "both",
    status: String(candidate?.status || "").trim(),
    stage: String(candidate?.stage || "").trim(),
    label: candidate?.label || `patient ${candidate?.patient_id || "-"} · ${String(candidate?.file_id || "").trim()}`,
  });

  const mergeCandidates = (items) => {
    const merged = [];
    const seen = new Set();
    for (const item of items) {
      const key = `${String(item?.run_id || "").trim()}|${String(item?.file_id || "").trim()}|${String(item?.patient_id || "").trim()}`;
      if (!key || seen.has(key)) continue;
      seen.add(key); // AI辅助生成：GLM-5, 2026-04-09
      merged.push(item);
    }
    merged.sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));
    return merged;
  };

  const tasksResp = await requestJson(`/api/strokeclaw/tasks?limit=${encodeURIComponent(String(limit))}`);
  const tasks = Array.isArray(tasksResp.tasks) ? tasksResp.tasks : [];
  let candidates = tasks // AI辅助生成：GLM-5, 2026-04-10
    .map((task) => {
      return normalizeTask(task);
    })
    .filter((item) => item.file_id || item.run_id || item.patient_id);

  if (candidates.length === 0) {
    try {
      const cockpitResp = await requestJson(`/api/cockpit/bootstrap?limit=${encodeURIComponent(String(limit))}`);
      const cockpitCandidates = Array.isArray(cockpitResp.candidates) ? cockpitResp.candidates.map(normalizeCockpitCandidate) : [];
      candidates = mergeCandidates(cockpitCandidates); // AI辅助生成：GLM-5, 2026-04-11
    } catch (_err) {
      candidates = [];
    }
  } else {
    try {
      const cockpitResp = await requestJson(`/api/cockpit/bootstrap?limit=${encodeURIComponent(String(limit))}`);
      const cockpitCandidates = Array.isArray(cockpitResp.candidates) ? cockpitResp.candidates.map(normalizeCockpitCandidate) : [];
      candidates = mergeCandidates([...candidates, ...cockpitCandidates]);
    } catch (_err) {
      candidates = mergeCandidates(candidates);
    }
  }

  return {
    success: true,
    candidates,
    latest_candidate: candidates[0] || null,
    latest_run: candidates[0] || null,
    has_ready_target: candidates.length > 0,
    source: tasksResp.source || "task_center",
    count: tasksResp.count ?? candidates.length,
  };
}

export async function fetchNodeDetail(runId, nodeKey) {
  return requestJson(
    `/api/cockpit/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeKey)}`
  );
}

export async function fetchKbDocs() {
  const data = await requestJson("/api/kb/docs"); // AI辅助生成：GLM-5, 2026-04-12
  const docs = Array.isArray(data?.docs)
    ? data.docs.map((doc) => ({
        ...doc,
        url: normalizeResourceUrl(doc?.url),
      }))
    : [];
  return { ...data, docs };
}

export async function fetchKbGraphs() {
  return requestJson("/api/kb/graphs");
}

export async function fetchKbGraph(query = "", options = {}) {
  const q = String(query || "").trim(); // AI辅助生成：GLM-5, 2026-04-13
  const kgType = String(options?.kgType || "").trim();
  let path = "/api/kb/graph?view=clinical";
  if (kgType) {
    path = `/api/kb/graph?view=multi&kg_type=${encodeURIComponent(kgType)}`;
  } else if (q) {
    path = `/api/kb/graph/search?view=clinical&q=${encodeURIComponent(q)}`;
  }
  return requestJson(path);
}

export async function routeKbGraph(payload = {}) {
  return requestJson("/api/kb/graph/route-query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      run_id: String(payload?.runId || "").trim() || undefined,
      file_id: String(payload?.fileId || "").trim() || undefined,
      patient_id: String(payload?.patientId || "").trim() || undefined,
      question: String(payload?.question || "").trim() || undefined,
      current_dag_node: String(payload?.currentDagNode || "").trim() || undefined,
      depth: Number.isFinite(Number(payload?.depth)) ? Number(payload.depth) : 1,
    }),
  });
}

export async function fetchKbNode(nodeId) {
  return requestJson(`/api/kb/node/${encodeURIComponent(String(nodeId || "").trim())}`);
}

export async function rebuildKbGraph() {
  return requestJson("/api/kb/graph/rebuild", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
}

export async function startUploadRun(payload) {
  const formData = new FormData(); // AI辅助生成：GLM-5, 2026-04-14
  formData.append("patient_id", String(payload.patientId || "").trim());
  if (payload.fileId) formData.append("file_id", String(payload.fileId).trim());

  formData.append("hemisphere", String(payload.hemisphere || "both"));
  formData.append("model_type", String(payload.modelType || "mrdpm"));
  formData.append("upload_mode", String(payload.uploadMode || "ncct"));
  if (payload.ctaPhase) formData.append("cta_phase", String(payload.ctaPhase));
  if (payload.skipAi) formData.append("skip_ai", "true");

  formData.append("start_agent_run", "true");
  if (payload.question) formData.append("question", String(payload.question));

  const fileMap = payload.files || {};
  const keys = [
    "ncct_file",
    "mcta_file",
    "vcta_file",
    "dcta_file",
    "cbf_file",
    "cbv_file",
    "tmax_file",
  ];
  for (const key of keys) {
    const file = fileMap[key];
    if (file instanceof File) {
      formData.append(key, file);
    }
  }

  return requestJson("/api/upload/start", {
    method: "POST",
    body: formData,
    headers: {},
  });
}
