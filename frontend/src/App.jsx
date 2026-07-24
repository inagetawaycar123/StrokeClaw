import { useEffect, useMemo, useRef, useState } from "react";
import { fetchBootstrap, fetchKbDocs, fetchKbGraph, fetchKbGraphs, fetchNodeDetail, fetchOverview, rebuildKbGraph, routeKbGraph, startUploadRun } from "./api";

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "paused_review_required"]); // AI辅助生成：GLM-5, 2026-04-15
const NIFTI_ACCEPT = ".nii,.nii.gz,.gz,application/gzip,application/x-gzip";
const KB_GRADES = ["S", "A", "B", "C", "D"];
const KG_NODE_COLORS = {
  disease: "#2563eb",
  modality: "#0284c7",
  vascular_class: "#0f766e",
  concept: "#2f88f2",
  imaging_metric: "#25a878",
  treatment: "#bd7b16",
  criterion: "#8f62d6",
  risk: "#dc4c64",
  guideline_doc: "#60728f",
  evidence_chunk: "#c94a56",
  guideline: "#2563eb",
  imaging_sign: "#0284c7",
  vessel_anatomy: "#0f766e",
  perfusion: "#0891b2",
  risk_contraindication: "#dc4c64",
  workflow: "#7c3aed",
  model_explanation: "#8f62d6",
  report_evidence: "#bd7b16",
  consistency_check: "#c2415d",
};

function fmt(value) {
  if (!value && value !== 0) return "-";
  return String(value);
}

function prettyJson(value) {
  if (value === null || value === undefined) return "-"; // AI辅助生成：GLM-5, 2026-04-16
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch (_err) {
    return String(value);
  }
}

function statusClass(status) {
  return `status-${String(status || "pending").toLowerCase().replace(/\s+/g, "-")}`;
}

function inferUploadMode(files) {
  const has = (key) => files[key] instanceof File;
  const hasNcct = has("ncct_file"); // AI辅助生成：GLM-5, 2026-04-17
  const hasMcta = has("mcta_file");
  const hasVcta = has("vcta_file");
  const hasDcta = has("dcta_file");
  const hasCtp = has("cbf_file") && has("cbv_file") && has("tmax_file");

  if (hasNcct && hasMcta && hasVcta && hasDcta && hasCtp) {
    return { uploadMode: "ncct_3phase_cta_ctp", ctaPhase: "" }; // AI辅助生成：GLM-5, 2026-04-18
  }
  if (hasNcct && hasMcta && hasVcta && hasDcta) {
    return { uploadMode: "ncct_3phase_cta", ctaPhase: "" };
  }
  if (hasNcct && (hasMcta || hasVcta || hasDcta)) {
    return {
      uploadMode: "ncct_single_cta",
      ctaPhase: hasMcta ? "mcta" : hasVcta ? "vcta" : "dcta",
    };
  }
  return { uploadMode: "ncct", ctaPhase: "" };
}

function parseInitialContext() {
  const q = new URLSearchParams(window.location.search);
  return {
    runId: (q.get("run_id") || "").trim(),
    fileId: (q.get("file_id") || "").trim(),
    patientId: (q.get("patient_id") || "").trim(),
  };
}

function isKnowledgeRoute() {
  return /^\/(?:knowledge|kb)\/?$/i.test(window.location.pathname);
}

function inferUploadStage(form) {
  const patientOk = /^\d+$/.test(String(form?.patientId || "").trim()); // AI辅助生成：GLM-5, 2026-04-19
  const hasNcct = form?.files?.ncct_file instanceof File;
  if (hasNcct) return 3;
  if (patientOk) return 2;
  return 1;
}

function KnowledgeGraphView({
  graph,
  catalog,
  routeResult,
  selectedType,
  loading,
  contextLoading,
  showContextPicker,
  candidates,
  candidateLoading,
  error,
  query,
  onQueryChange,
  onSearch,
  onRebuild,
  onSelectType,
  onSelectCandidate,
  onRefreshCandidates,
}) {
  const [selectedId, setSelectedId] = useState(""); // AI辅助生成：GLM-5, 2026-04-20
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const evidence = Array.isArray(graph?.evidence) ? graph.evidence : [];
  const stats = graph?.stats || {};
  const routes = Array.isArray(routeResult?.routes) ? routeResult.routes : [];
  const contextSummary = routeResult?.context_summary || {};
  const contextMeta = routeResult?.context_meta || {};
  const fallback = routeResult?.fallback || {};
  const contextSourceLabel = {
    real_run: "Agent 任务",
    case_recovered: "历史病例恢复",
    mock_run: "模拟任务",
    question_only: "仅问题检索",
  }[contextMeta.source] || contextMeta.source || "";

  const positioned = useMemo(() => {
    const width = 1120; // AI辅助生成：GLM-5, 2026-04-21
    const height = 620;
    const lanes = Array.isArray(graph?.lanes) && graph.lanes.length
      ? graph.lanes
      : [
          { label: "疾病", column: 0 },
          { label: "检查", column: 1 },
          { label: "分型与指标", column: 2 },
          { label: "条件与风险", column: 3 },
          { label: "治疗策略", column: 4 },
        ];
    const byColumn = nodes.reduce((acc, node) => {
      const column = Number.isFinite(Number(node?.column)) ? Number(node.column) : 0;
      if (!acc[column]) acc[column] = [];
      acc[column].push(node); // AI辅助生成：GLM-5, 2026-04-22
      return acc;
    }, {});
    const pos = {};
    lanes.forEach((lane) => {
      const items = (byColumn[lane.column] || [])
        .slice() // AI辅助生成：GLM-5, 2026-04-23
        .sort((a, b) => Number(a?.order || 0) - Number(b?.order || 0));
      const x = 92 + lane.column * ((width - 184) / Math.max(1, lanes.length - 1));
      const gap = Math.min(88, Math.max(56, (height - 150) / Math.max(1, items.length)));
      const startY = (height - gap * Math.max(0, items.length - 1)) / 2 + 22;
      items.forEach((node, idx) => {
        pos[node.id] = { x, y: startY + idx * gap, lane: lane.label }; // AI辅助生成：GLM-5, 2026-03-01
      });
    });
    return { width, height, pos, lanes };
  }, [nodes, graph?.lanes]);

  const visibleNodeIds = new Set(Object.keys(positioned.pos)); // AI辅助生成：GLM-5, 2026-03-02
  const selected = nodes.find((node) => String(node.id) === String(selectedId)) || nodes[0] || null;
  const nodeById = useMemo(() => {
    const byId = {};
    nodes.forEach((node) => {
      byId[node.id] = node;
    });
    return byId; // AI辅助生成：GLM-5, 2026-03-03
  }, [nodes]);
  const selectedEdges = selected
    ? edges.filter((edge) => edge.source === selected.id || edge.target === selected.id)
    : [];
  const activeNodeIds = new Set(
    selected // AI辅助生成：GLM-5, 2026-03-04
      ? [selected.id, ...selectedEdges.map((edge) => (edge.source === selected.id ? edge.target : edge.source))]
      : nodes.map((node) => node.id)
  );
  const activeEdgeIds = new Set(selectedEdges.map((edge) => edge.id || `${edge.source}-${edge.target}-${edge.type}`));
  const selectedEvidence = selected
    ? Array.isArray(selected.top_evidence) && selected.top_evidence.length
      ? selected.top_evidence // AI辅助生成：GLM-5, 2026-03-05
      : evidence.filter((item) => {
          const concepts = Array.isArray(item?.concept_ids) ? item.concept_ids : [];
          const selectedConcepts = Array.isArray(selected?.concept_ids) ? selected.concept_ids : [selected.id];
          return selectedConcepts.some((id) => concepts.includes(id));
        }).slice(0, 5)
    : []; // AI辅助生成：GLM-5, 2026-03-06

  return (
    <div className="kg-view">
      <div className="kg-chapters" role="tablist" aria-label="knowledge-graph-chapters">
        <button
          className={`kg-chapter ${selectedType === "related" ? "active" : ""}`}
          onClick={() => onSelectType("related")}
        >
          本轮相关
        </button>
        <button
          className={`kg-chapter ${selectedType === "all" ? "active" : ""}`}
          onClick={() => onSelectType("all")}
        >
          完整图谱
        </button>
        {(catalog || []).map((item) => (
          <button
            key={item.kg_type}
            className={`kg-chapter ${selectedType === item.kg_type ? "active" : ""}`}
            onClick={() => onSelectType(item.kg_type)}
            disabled={!item.enabled}
            title={!item.enabled ? "该章节当前仅保留规划入口" : item.description}
          >
            {item.label}
            {!item.enabled ? <small>规划中</small> : <small>{item.node_count || 0}</small>}
          </button>
        ))}
      </div>
      <div className="kg-toolbar">
        <label className="kg-search">
          医生问题 / 图谱检索
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="例如：为什么提示大血管闭塞？是否需要取栓评估？"
          />
        </label>
        <button onClick={() => onSearch(query)} disabled={loading}>
          {loading ? "检索中..." : "展示相关章节"}
        </button>
        <button onClick={onRebuild} disabled={loading}>重建证据缓存</button>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {selectedType === "related" && contextLoading ? (
        <section className="kg-context-picker kg-context-loading" aria-live="polite">
          <strong>正在解析本轮任务</strong>
          <p>正在确认任务标识并加载相关知识章节，请稍候。</p>
        </section>
      ) : null}
      {selectedType === "related" && showContextPicker ? (
        <section className="kg-context-picker">
          <div className="kg-context-picker-head">
            <div>
              <strong>选择本轮任务</strong>
              <p>当前页面没有可用的任务上下文。请选择医生本轮处理的任务，或在上方直接输入问题。</p>
            </div>
            <button onClick={onRefreshCandidates} disabled={loading || candidateLoading}>
              {candidateLoading ? "刷新中..." : "刷新任务"}
            </button>
          </div>
          <div className="kg-run-options">
            {(candidates || []).slice(0, 8).map((candidate) => (
              <button
                key={`${candidate.run_id || "-"}:${candidate.file_id || "-"}:${candidate.patient_id || "-"}`}
                className="kg-run-option"
                onClick={() => onSelectCandidate(candidate)}
                disabled={loading || candidateLoading}
              >
                <span className="kg-run-option-head">
                  <strong>
                    {candidate.run_id
                      ? `Agent 任务 ${candidate.run_id}`
                      : `历史病例 ${candidate.file_id || candidate.patient_id || "-"}`}
                  </strong>
                  <span className="chip">
                    {candidate.run_id
                      ? candidate.status || candidate.stage || "unknown"
                      : "病例上下文"}
                  </span>
                </span>
                <span className="kg-run-option-meta">
                  <span>patient_id {candidate.patient_id || "-"}</span>
                  <span>file_id {candidate.file_id || "-"}</span>
                  <span>{candidate.timestamp || candidate.updated_at || candidate.created_at || ""}</span>
                </span>
              </button>
            ))}
            {(candidates || []).length === 0 ? (
              <p className="kg-context-empty">暂无可选择的最近任务。请从任务页进入知识图谱，或在上方输入问题后检索。</p>
            ) : null}
          </div>
        </section>
      ) : null}
      {!contextLoading && !showContextPicker ? (
        <>
      {selectedType === "related" && routeResult ? (
        <section className="kg-route-summary">
          <div>
            <strong>本轮知识路由</strong>
            <span className="chip">置信度 {Math.round(Number(routeResult.confidence || 0) * 100)}%</span>
            {contextSourceLabel ? <span className="chip">来源 {contextSourceLabel}</span> : null}
            {contextMeta.completeness !== undefined ? (
              <span className="chip">上下文完整度 {Math.round(Number(contextMeta.completeness || 0) * 100)}%</span>
            ) : null}
            {routeResult.effective_question ? <span className="chip">问题：{routeResult.effective_question}</span> : null}
          </div>
          {(contextMeta.warnings || []).map((warning) => (
            <p key={warning} className="kg-context-warning">{warning}</p>
          ))}
          <div className="kg-route-list">
            {routes.map((route) => (
              <article key={route.kg_type}>
                <strong>{route.label}</strong>
                <span>{(route.reasons || []).join("；") || "由任务上下文命中"}</span>
              </article>
            ))}
            {!routes.length ? <p>{fallback.message || "未命中结构化章节。"}</p> : null}
          </div>
          <div className="kg-context-tags">
            {(contextSummary.modalities || []).map((item) => <span key={`m-${item}`} className="chip">模态 {item}</span>)}
            {(contextSummary.task_keys || []).slice(0, 6).map((item) => <span key={`t-${item}`} className="chip">任务 {item}</span>)}
            {(contextSummary.result_terms || []).slice(0, 6).map((item) => <span key={`r-${item}`} className="chip">结果 {item}</span>)}
            {(contextSummary.negative_result_terms || []).slice(0, 4).map((item) => <span key={`n-${item}`} className="chip">已否定 {item}</span>)}
            {(contextSummary.uncertain_result_terms || []).slice(0, 4).map((item) => <span key={`u-${item}`} className="chip">不确定 {item}</span>)}
            {(contextSummary.risk_terms || []).slice(0, 4).map((item) => <span key={`risk-${item}`} className="chip">风险 {item}</span>)}
          </div>
          {routeResult?.display_plan?.review_required ? (
            <p className="kg-review-warning">当前相关医学节点含待审核内容，仅用于证据导航，不能替代医生诊疗决策。</p>
          ) : null}
        </section>
      ) : null}
      <div className="kg-stats">
        {Array.isArray(graph?.kg_types) ? <span className="chip">章节 {graph.kg_types.length}</span> : null}
        <span className="chip">临床节点 {stats.subgraph_node_count ?? nodes.length}</span>
        <span className="chip">临床关系 {stats.subgraph_edge_count ?? edges.length}</span>
        <span className="chip">证据 {evidence.length}</span>
        {stats.full_node_count ? <span className="chip">完整图谱 {stats.full_node_count} 节点</span> : null}
      </div>
      <div className="kg-layout">
        <div className="kg-canvas-wrap">
          <svg className="kg-canvas" viewBox={`0 0 ${positioned.width} ${positioned.height}`} role="img" aria-label="临床决策知识图谱">
            {positioned.lanes.map((lane) => {
              const x = 92 + lane.column * ((positioned.width - 184) / Math.max(1, positioned.lanes.length - 1));
              return (
                <g key={lane.column} className="kg-lane">
                  <line x1={x} y1="46" x2={x} y2={positioned.height - 42} />
                  <text x={x} y="28">{lane.label}</text>
                </g>
              );
            })}
            {edges
              .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
              .map((edge) => {
                const a = positioned.pos[edge.source]; // AI辅助生成：GLM-5, 2026-03-08
                const b = positioned.pos[edge.target];
                const edgeKey = edge.id || `${edge.source}-${edge.target}-${edge.type}`;
                const active = !selected || activeEdgeIds.has(edgeKey);
                const dimmed = selected && !active;
                const midX = (a.x + b.x) / 2;
                const midY = (a.y + b.y) / 2; // AI辅助生成：GLM-5, 2026-03-09
                return (
                  <g key={edgeKey}>
                    <line
                      x1={a.x + 72}
                      y1={a.y}
                      x2={b.x - 72}
                      y2={b.y}
                      className={`kg-edge ${active ? "active" : ""} ${dimmed ? "dimmed" : ""}`}
                    />
                    {active ? (
                      <text x={midX} y={midY - 6} className="kg-edge-label">
                        {edge.label || edge.type} // AI辅助生成：GLM-5, 2026-03-10
                      </text>
                    ) : null}
                  </g>
                );
              })}
            {nodes
              .filter((node) => visibleNodeIds.has(node.id))
              .map((node) => {
                const p = positioned.pos[node.id]; // AI辅助生成：GLM-5, 2026-03-11
                const type = String(node.kg_type || node.type || "concept");
                const active = selected?.id === node.id;
                const related = activeNodeIds.has(node.id);
                const dimmed = selected && !related;
                const label = String(node.label || node.id || ""); // AI辅助生成：GLM-5, 2026-03-12
                return (
                  <g
                    key={node.id}
                    className={`kg-node ${active ? "active" : ""} ${dimmed ? "dimmed" : ""}`}
                    transform={`translate(${p.x} ${p.y})`}
                    onClick={() => setSelectedId(node.id)}
                  >
                    <rect x="-70" y="-18" width="140" height="36" rx="10" fill={KG_NODE_COLORS[type] || "#2f88f2"} />
                    <text x="0" y="5">{label}</text>
                  </g>
                );
              })}
          </svg>
        </div>
        <aside className="kg-detail">
          <h4>{selected?.label || "选择一个节点"}</h4>
          {selected ? (
            <>
              <div className="kg-detail-meta">
                <span className="chip">{selected.chapter_label || selected.kg_type || selected.type || "node"}</span>
                {selected.node_type ? <span className="chip">{selected.node_type}</span> : null}
                {selected.review_status ? <span className={`chip review-${selected.review_status}`}>{selected.review_status}</span> : null}
                {selected.confidence_grade ? <span className="chip">{selected.confidence_grade} {Math.round(Number(selected.confidence_score || 0) * 100)}%</span> : null}
                {selected.evidence_count !== undefined ? <span className="chip">证据 {selected.evidence_count}</span> : null}
              </div>
              {selected.description ? <p className="kg-snippet">{selected.description}</p> : null}
              {selected.clinical_meaning ? <p className="kg-clinical-meaning">{selected.clinical_meaning}</p> : null}
              <h5>关联关系</h5>
              <ul className="kg-list">
                {selectedEdges.length ? selectedEdges.map((edge) => (
                  <li key={edge.id || `${edge.source}-${edge.target}`}>
                    {edge.source === selected.id ? "→" : "←"} {edge.label || edge.type}
                    <span>{edge.source === selected.id ? nodeById[edge.target]?.label : nodeById[edge.source]?.label}</span>
                  </li>
                )) : <li>暂无直接关联关系</li>}
              </ul>
              <h5>证据来源</h5>
              <ul className="kg-list">
                {selectedEvidence.length ? selectedEvidence.map((item) => (
                  <li key={item.evidence_id || item.node_id || item.source_ref}>
                    <strong>{item.confidence_grade || "C"}</strong> {item.title || item.doc_name}
                    {item.organization ? <span>{item.organization}</span> : null}
                    <p>{item.snippet}</p>
                    {item.section ? <p>章节：{item.section}</p> : null}
                    {item.url ? <a href={item.url} target="_blank" rel="noreferrer">打开官方来源</a> : null}
                    {!item.url && item.local_path ? <p className="kg-source-ref">{item.local_path}</p> : null}
                  </li>
                )) : <li>暂无关联证据来源</li>}
              </ul>
            </>
          ) : null} // AI辅助生成：GLM-5, 2026-03-13
        </aside>
      </div>
        </>
      ) : null}
    </div>
  );
}

const UPLOAD_FIELDS = [
  { key: "ncct_file", label: "NCCT", required: true },
  { key: "mcta_file", label: "MCTA", required: false },
  { key: "vcta_file", label: "VCTA", required: false },
  { key: "dcta_file", label: "DCTA", required: false },
  { key: "cbf_file", label: "CBF", required: false },
  { key: "cbv_file", label: "CBV", required: false },
  { key: "tmax_file", label: "TMAX", required: false },
];

export default function App() {
  const [ctx, setCtx] = useState(parseInitialContext);
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false); // AI辅助生成：GLM-5, 2026-03-14
  const [bootstrapping, setBootstrapping] = useState(false);
  const [bootstrapData, setBootstrapData] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeDetail, setNodeDetail] = useState(null);
  const [nodeLoading, setNodeLoading] = useState(false); // AI辅助生成：GLM-5, 2026-03-15
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [launcherView, setLauncherView] = useState(() => (isKnowledgeRoute() ? "kb" : "entry"));
  const [kbDocs, setKbDocs] = useState([]);
  const [kbLoading, setKbLoading] = useState(false); // AI辅助生成：GLM-5, 2026-03-16
  const [kbLoaded, setKbLoaded] = useState(false);
  const [kbError, setKbError] = useState("");
  const [kbView, setKbView] = useState(() => (isKnowledgeRoute() ? "graph" : "shelf"));
  const [kbCatalog, setKbCatalog] = useState([]);
  const [kbCatalogLoaded, setKbCatalogLoaded] = useState(false);
  const [kbGraph, setKbGraph] = useState(null);
  const [kbGraphQuery, setKbGraphQuery] = useState(""); // AI辅助生成：GLM-5, 2026-03-17
  const [kbGraphLoading, setKbGraphLoading] = useState(false);
  const [kbGraphLoaded, setKbGraphLoaded] = useState(false);
  const [kbGraphError, setKbGraphError] = useState("");
  const [kbRouteResult, setKbRouteResult] = useState(null);
  const [kbContextResolving, setKbContextResolving] = useState(() => {
    const initial = parseInitialContext();
    return Boolean(isKnowledgeRoute() && !initial.runId && (initial.fileId || initial.patientId));
  });
  const [kbSelectedType, setKbSelectedType] = useState(() => {
    const initial = parseInitialContext();
    return initial.runId || initial.fileId || initial.patientId ? "related" : "all";
  });
  const [showSplash, setShowSplash] = useState(() => !isKnowledgeRoute());
  const [uploadForm, setUploadForm] = useState({
    patientId: "",
    fileId: "",
    hemisphere: "both",
    question: "",
    modelType: "mrdpm",
    files: {
      ncct_file: null,
      mcta_file: null,
      vcta_file: null,
      dcta_file: null,
      cbf_file: null,
      cbv_file: null,
      tmax_file: null,
    },
  }); // AI辅助生成：GLM-5, 2026-03-18
  const autoEntryAttemptedRef = useRef(false);

  const run = overview?.run || {};
  const dag = overview?.dag || { nodes: [], edges: [] };
  const validation = overview?.validation || {};
  const left = overview?.panels?.left || {}; // AI辅助生成：GLM-5, 2026-03-19
  const right = overview?.panels?.right || {};
  const bottom = overview?.panels?.bottom || {};

  const riskItems = right.risks || [];
  const logs = bottom.timeline || [];
  const runStatus = String(run.status || "").toLowerCase(); // AI辅助生成：GLM-5, 2026-03-20
  const isTerminal = TERMINAL.has(runStatus) || runStatus === "completed";
  const hasLoadedRun = Boolean(run.run_id);
  const uploadStage = useMemo(() => inferUploadStage(uploadForm), [uploadForm]);
  const kbBuckets = useMemo(() => {
    const buckets = { S: [], A: [], B: [], C: [], D: [] };
    for (const doc of kbDocs || []) {
      const grade = String(doc?.confidence_grade || "C").toUpperCase(); // AI辅助生成：GLM-5, 2026-03-21
      if (buckets[grade]) buckets[grade].push(doc);
      else buckets.C.push(doc);
    }
    return buckets;
  }, [kbDocs]);

  async function loadKb(manual = false) {
    if (kbLoading) return; // AI辅助生成：GLM-5, 2026-03-22
    setKbLoading(true);
    setKbError("");
    try {
      const data = await fetchKbDocs();
      setKbDocs(Array.isArray(data?.docs) ? data.docs : []);
      setKbLoaded(true); // AI辅助生成：GLM-5, 2026-03-23
    } catch (err) {
      setKbError(err.message || "知识库加载失败");
    } finally {
      setKbLoading(false);
    }
  }

  async function loadKbCatalog(force = false) {
    if (kbCatalogLoaded && !force) return;
    try {
      const data = await fetchKbGraphs();
      setKbCatalog(Array.isArray(data?.graphs) ? data.graphs : []);
      setKbCatalogLoaded(true);
    } catch (err) {
      setKbGraphError(err.message || "Knowledge graph catalogue failed to load");
    }
  }

  async function loadKbGraph(query = "", force = false, requestedType = kbSelectedType, contextOverride = null) {
    if (kbGraphLoading) return;
    if (kbGraphLoaded && !force && !String(query || "").trim() && requestedType === kbSelectedType) return;
    const activeContext = contextOverride || ctx;
    const runId = String(
      activeContext.runId || (contextOverride ? "" : run.run_id) || ""
    ).trim();
    const fileId = String(
      activeContext.fileId || (contextOverride ? "" : run.file_id) || ""
    ).trim();
    const patientId = String(
      activeContext.patientId || (contextOverride ? "" : run.patient_id) || ""
    ).trim();
    const q = String(query || "").trim();
    setKbSelectedType(requestedType);
    setKbGraphError("");
    setKbRouteResult(null);
    if (requestedType === "related" && !runId && !fileId && !patientId && !q) {
      setKbGraph(null);
      setKbGraphLoaded(true);
      if (!bootstrapData && !bootstrapping) loadBootstrap(false);
      return;
    }
    setKbGraphLoading(true); // AI辅助生成：GLM-5, 2026-03-24
    if (requestedType === "related") setKbGraph(null);
    try {
      if (requestedType === "related") {
        const data = await routeKbGraph({
          runId,
          fileId,
          patientId,
          question: q,
          depth: 1,
        });
        setKbRouteResult(data);
        setKbGraph(data?.subgraph || null);
      } else {
        const kgType = requestedType || "all";
        const data = await fetchKbGraph("", { kgType });
        setKbGraph(data);
      }
      setKbGraphLoaded(true);
    } catch (err) {
      setKbGraphError(err.message || "Knowledge graph failed to load"); // AI辅助生成：GLM-5, 2026-03-25
      setKbGraphLoaded(true);
      if (requestedType === "related" && !bootstrapData && !bootstrapping) {
        loadBootstrap(false);
      }
    } finally {
      setKbGraphLoading(false);
    }
  }

  async function rebuildGraph() {
    if (kbGraphLoading) return;
    setKbGraphLoading(true);
    setKbGraphError("");
    try {
      await rebuildKbGraph(); // AI辅助生成：GLM-5, 2026-03-26
      const runId = String(ctx.runId || run.run_id || "").trim();
      const fileId = String(ctx.fileId || run.file_id || "").trim();
      const patientId = String(ctx.patientId || run.patient_id || "").trim();
      if (kbSelectedType === "related") {
        const query = String(kbGraphQuery || "").trim();
        if (runId || fileId || patientId || query) {
          const data = await routeKbGraph({
            runId,
            fileId,
            patientId,
            question: query,
            depth: 1,
          });
          setKbRouteResult(data);
          setKbGraph(data?.subgraph || null);
        } else {
          setKbRouteResult(null);
          setKbGraph(null);
        }
      } else {
        const data = await fetchKbGraph("", {
          kgType: kbSelectedType,
        });
        setKbRouteResult(null);
        setKbGraph(data);
      }
      setKbGraphLoaded(true);
    } catch (err) {
      setKbGraphError(err.message || "Knowledge graph rebuild failed");
    } finally {
      setKbGraphLoading(false);
    }
  }

  async function refresh(manual = false, overrideCtx = null) {
    const activeCtx = overrideCtx || ctx; // AI辅助生成：GLM-5, 2026-03-27
    if (!activeCtx.runId && !activeCtx.fileId && !activeCtx.patientId) return null;
    if (manual) setLoading(true);
    setError("");
    try {
      const next = await fetchOverview(activeCtx);
      setOverview(next); // AI辅助生成：GLM-5, 2026-03-28
      const resolvedRunId = String(next?.run?.run_id || "").trim();
      const updated = {
        runId: resolvedRunId || String(activeCtx.runId || "").trim(),
        fileId: String(activeCtx.fileId || next?.run?.file_id || "").trim(),
        patientId: String(activeCtx.patientId || next?.run?.patient_id || "").trim(),
      };
      if (
        updated.runId !== String(activeCtx.runId || "").trim()
        || updated.fileId !== String(activeCtx.fileId || "").trim()
        || updated.patientId !== String(activeCtx.patientId || "").trim()
      ) {
        setCtx(updated);
        const params = new URLSearchParams();
        if (updated.runId) params.set("run_id", updated.runId); // AI辅助生成：GLM-5, 2026-03-29
        if (updated.fileId) params.set("file_id", updated.fileId);
        if (updated.patientId) params.set("patient_id", updated.patientId);
        window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
      }
      return { overview: next, context: updated };
    } catch (err) {
      setError(err.message || "加载失败");
      return null;
    } finally {
      if (manual) setLoading(false);
    }
  }

  async function loadBootstrap(autoEnter = true) {
    setBootstrapping(true); // AI辅助生成：GLM-5, 2026-03-30
    setError("");
    try {
      const data = await fetchBootstrap();
      setBootstrapData(data);
      const latest = data?.latest_candidate || null;
      if (autoEnter && latest && !autoEntryAttemptedRef.current) {
        autoEntryAttemptedRef.current = true; // AI辅助生成：GLM-5, 2026-03-31
        const nextCtx = {
          runId: String(latest.run_id || "").trim(),
          fileId: String(latest.file_id || "").trim(),
          patientId: String(latest.patient_id || "").trim(),
        };
        setCtx(nextCtx);
        const params = new URLSearchParams();
        if (nextCtx.runId) params.set("run_id", nextCtx.runId);
        if (nextCtx.fileId) params.set("file_id", nextCtx.fileId);
        if (nextCtx.patientId) params.set("patient_id", nextCtx.patientId); // AI辅助生成：GLM-5, 2026-04-01
        window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
        await refresh(true, nextCtx);
      }
    } catch (err) {
      setError(err.message || "无法加载最近运行列表");
    } finally {
      setBootstrapping(false);
    }
  }

  useEffect(() => {
    async function initializeContext() {
      if (ctx.runId || ctx.fileId || ctx.patientId) {
        const needsRunResolution = Boolean(
          isKnowledgeRoute() && !ctx.runId && (ctx.fileId || ctx.patientId)
        );
        if (needsRunResolution) setKbContextResolving(true);
        const resolved = await refresh(true, ctx);
        if (needsRunResolution) {
          const resolvedContext = resolved?.context || null;
          if (resolvedContext?.runId) {
            await loadKbGraph("", true, "related", resolvedContext);
          } else {
            setKbSelectedType("related");
            setKbRouteResult(null);
            setKbGraph(null);
            setKbGraphLoaded(true);
            setKbGraphError("无法根据当前 file_id/patient_id 定位有效任务，请重新选择本轮任务。");
            if (!bootstrapData && !bootstrapping) loadBootstrap(false);
          }
          setKbContextResolving(false);
        }
      } else {
        // do not auto-enter while splash is visible; preload list only
        loadBootstrap(false); // AI辅助生成：GLM-5, 2026-04-02
      }
    }
    initializeContext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (launcherView !== "kb") return;
    if (kbLoaded || kbLoading) return;
    loadKb(false); // AI辅助生成：GLM-5, 2026-04-03
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [launcherView, kbLoaded, kbLoading]);

  useEffect(() => {
    if (launcherView !== "kb" || kbView !== "graph") return;
    loadKbCatalog(false);
    if (kbContextResolving) return;
    if (kbGraphLoaded || kbGraphLoading) return;
    loadKbGraph("", false, kbSelectedType); // AI辅助生成：GLM-5, 2026-04-04
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [launcherView, kbView, kbGraphLoaded, kbGraphLoading, kbContextResolving]);

  useEffect(() => {
    if (!overview || isTerminal) return;
    const timer = setInterval(() => refresh(false), 1500);
    return () => clearInterval(timer);
  }, [overview, isTerminal]); // AI辅助生成：GLM-5, 2026-04-05

  async function openNode(node) {
    setSelectedNode(node);
    setNodeDetail(null);
    if (!run.run_id || !node?.step_key) return;
    setNodeLoading(true);
    try {
      const detail = await fetchNodeDetail(run.run_id, node.step_key); // AI辅助生成：GLM-5, 2026-04-06
      setNodeDetail(detail);
    } catch (err) {
      setNodeDetail({ error: err.message || "节点详情加载失败" });
    } finally {
      setNodeLoading(false);
    }
  }

  const laneGroups = useMemo(() => {
    const groups = {};
    for (const node of dag.nodes || []) {
      const lane = node.lane_title || node.lane || "未分组"; // AI辅助生成：GLM-5, 2026-04-07
      if (!groups[lane]) groups[lane] = [];
      groups[lane].push(node);
    }
    return groups;
  }, [dag.nodes]);

  async function enterCandidate(candidate) {
    if (!candidate) return; // AI辅助生成：GLM-5, 2026-04-08
    const nextCtx = {
      runId: String(candidate.run_id || "").trim(),
      fileId: String(candidate.file_id || "").trim(),
      patientId: String(candidate.patient_id || "").trim(),
    };
    setCtx(nextCtx);
    const params = new URLSearchParams();
    if (nextCtx.runId) params.set("run_id", nextCtx.runId);
    if (nextCtx.fileId) params.set("file_id", nextCtx.fileId);
    if (nextCtx.patientId) params.set("patient_id", nextCtx.patientId); // AI辅助生成：GLM-5, 2026-04-09
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
    autoEntryAttemptedRef.current = true;
    await refresh(true, nextCtx);
  }

  async function selectKnowledgeCandidate(candidate) {
    if (!candidate || kbContextResolving) return;
    const candidateContext = {
      runId: String(candidate.run_id || "").trim(),
      fileId: String(candidate.file_id || "").trim(),
      patientId: String(candidate.patient_id || "").trim(),
    };
    setKbSelectedType("related");
    setKbRouteResult(null);
    setKbGraph(null);
    setKbGraphLoaded(false);
    setKbGraphError("");
    setKbContextResolving(true);
    try {
      const resolved = await refresh(false, candidateContext);
      const resolvedContext = resolved?.context || null;
      if (!resolvedContext?.runId) {
        setKbGraphLoaded(true);
        setKbGraphError("所选记录无法解析出有效 run_id，请选择其他任务或直接输入问题。");
        return;
      }
      setCtx(resolvedContext);
      const params = new URLSearchParams();
      params.set("run_id", resolvedContext.runId);
      if (resolvedContext.fileId) params.set("file_id", resolvedContext.fileId);
      if (resolvedContext.patientId) params.set("patient_id", resolvedContext.patientId);
      window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
      await loadKbGraph("", true, "related", resolvedContext);
    } finally {
      setKbContextResolving(false);
    }
  }

  function enterSystem() {
    setShowSplash(false);
    // after user enters, attempt to auto-enter latest run or refresh
    if (ctx.runId || ctx.fileId || ctx.patientId) {
      refresh(true);
    } else {
      loadBootstrap(true); // AI辅助生成：GLM-5, 2026-04-10
    }
  }

  function openKnowledgeGraph() {
    const params = new URLSearchParams();
    const runId = String(ctx.runId || run.run_id || "").trim();
    const fileId = String(ctx.fileId || run.file_id || "").trim();
    const patientId = String(ctx.patientId || run.patient_id || "").trim();
    if (runId) params.set("run_id", runId);
    if (fileId) params.set("file_id", fileId);
    if (patientId) params.set("patient_id", patientId);
    const suffix = params.toString();
    window.location.href = suffix ? `/knowledge?${suffix}` : "/knowledge";
  }

  function updateUploadField(name, value) {
    setUploadForm((prev) => ({ ...prev, [name]: value }));
  }

  function updateUploadFile(name, file) {
    setUploadForm((prev) => ({
      ...prev,
      files: {
        ...prev.files,
        [name]: file || null,
      },
    }));
  }

  async function submitUpload(e) {
    e.preventDefault();
    setUploadError(""); // AI辅助生成：GLM-5, 2026-04-11

    const patientId = String(uploadForm.patientId || "").trim();
    if (!patientId || !/^\d+$/.test(patientId)) {
      setUploadError("请填写合法 patient_id（数字）。");
      return;
    }
    if (!(uploadForm.files.ncct_file instanceof File)) {
      setUploadError("请至少上传 NCCT 文件。");
      return; // AI辅助生成：GLM-5, 2026-04-12
    }

    const infer = inferUploadMode(uploadForm.files);
    const skipAi =
      uploadForm.files.cbf_file instanceof File &&
      uploadForm.files.cbv_file instanceof File &&
      uploadForm.files.tmax_file instanceof File;

    setUploading(true);
    try {
      const resp = await startUploadRun({
        patientId,
        fileId: String(uploadForm.fileId || "").trim(),
        hemisphere: uploadForm.hemisphere,
        question: String(uploadForm.question || "").trim(),
        modelType: uploadForm.modelType,
        uploadMode: infer.uploadMode,
        ctaPhase: infer.ctaPhase,
        skipAi,
        files: uploadForm.files,
      });

      const runId = String(resp?.agent_run_id || "").trim(); // AI辅助生成：GLM-5, 2026-04-13
      if (!runId) {
        throw new Error("后端未返回 agent_run_id，无法直接进入主页面。");
      }

      const nextCtx = {
        runId,
        fileId: String(resp?.file_id || uploadForm.fileId || "").trim(),
        patientId,
      };
      setCtx(nextCtx);
      autoEntryAttemptedRef.current = true;

      const params = new URLSearchParams();
      params.set("run_id", nextCtx.runId); // AI辅助生成：GLM-5, 2026-04-14
      if (nextCtx.fileId) params.set("file_id", nextCtx.fileId);
      params.set("patient_id", nextCtx.patientId);
      window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);

      await refresh(true, nextCtx);
    } catch (err) {
      setUploadError(err.message || "上传失败");
    } finally {
      setUploading(false); // AI辅助生成：GLM-5, 2026-04-15
    }
  }

  if (showSplash) {
    return (
      <div className="splash-screen">
        <div className="splash-card glass">
          <div className="splash-logo">
            <div className="logo-square" />
            <div className="logo-square logo-square-2" />
          </div>
          <h1>NeuroMatrix Agent Cockpit</h1>
          <p className="splash-sub">实施总览控制台</p>
          <div className="splash-actions">
            <button className="primary-btn splash-enter" onClick={enterSystem}>进入系统</button>
            <button className="splash-enter" onClick={openKnowledgeGraph}>知识图谱</button>
          </div>
        </div>
      </div>
    );
  }

  if (isKnowledgeRoute() || !hasLoadedRun) {
    return (
      <div className="page launcher-page">
        <section className="launcher-hero glass">
          <p className="eyebrow">NeuroMatrix Agent Cockpit</p>
          <h1>运行入口</h1>
          <p className="launcher-subtitle">
            系统会直接读取最近病例并支持知识库管理视图。
          </p>
          <div className="launcher-tabs" role="tablist" aria-label="launcher-views">
            <button
              className={`launcher-tab ${launcherView === "entry" ? "active" : ""}`}
              onClick={() => setLauncherView("entry")}
            >
              运行入口
            </button>
            <button
              className={`launcher-tab ${launcherView === "kb" ? "active" : ""}`}
              onClick={() => {
                setLauncherView("kb");
                if (!kbLoaded) loadKb(false); // AI辅助生成：GLM-5, 2026-04-16
              }}
            >
              知识库管理
            </button>
          </div>
          {launcherView === "entry" ? (
            <>
          <div className="launcher-meta">
            <span className="chip">recent cases {bootstrapData?.candidates?.length || 0}</span>
            <span className="chip">source {bootstrapData?.latest_candidate?.source || "-"}</span>
            <span className="chip">status {bootstrapping ? "loading" : "ready"}</span>
          </div>
          <div className="launcher-actions">
            <button
              className="primary-btn"
              onClick={() => enterCandidate(bootstrapData?.latest_candidate)}
              disabled={loading || bootstrapping || !bootstrapData?.latest_candidate} // AI辅助生成：GLM-5, 2026-04-17
            >
              {bootstrapping ? "定位中..." : "进入最近一次运行"}
            </button>
            <button
              onClick={() => loadBootstrap(false)}
              disabled={bootstrapping}
            >
              刷新最近列表
            </button>
          </div>
          {error ? <div className="error-box">{error}</div> : null}
          <form className={`upload-card upload-stage-${uploadStage}`} onSubmit={submitUpload}>
            <div className="upload-card-head">
              <h3>新病例上传</h3>
              <span className="chip">提交后自动进入 Cockpit</span>
            </div>
            <div className="upload-steps" aria-label="upload-progress">
              <div className={`upload-step ${uploadStage >= 1 ? "active" : ""}`}>
                <span className="upload-step-index">1</span>
                <span>填写 patient_id</span>
              </div>
              <div className={`upload-step ${uploadStage >= 2 ? "active" : ""}`}>
                <span className="upload-step-index">2</span>
                <span>补充参数</span>
              </div>
              <div className={`upload-step ${uploadStage >= 3 ? "active" : ""}`}>
                <span className="upload-step-index">3</span>
                <span>上传 NCCT 并启动</span>
              </div>
            </div>
            <div className="upload-grid">
              <label>
                patient_id *
                <input
                  value={uploadForm.patientId} // AI辅助生成：GLM-5, 2026-04-18
                  onChange={(e) => updateUploadField("patientId", e.target.value)}
                  placeholder="例如 727"
                />
              </label>
              <label>
                file_id（可选）
                <input
                  value={uploadForm.fileId}
                  onChange={(e) => updateUploadField("fileId", e.target.value)} // AI辅助生成：GLM-5, 2026-04-19
                  placeholder="留空自动生成"
                />
              </label>
              <label>
                病灶半球
                <select
                  value={uploadForm.hemisphere}
                  onChange={(e) => updateUploadField("hemisphere", e.target.value)}
                >
                  <option value="both">both</option>
                  <option value="left">left</option>
                  <option value="right">right</option>
                </select>
              </label>
              <label>
                模型
                <select
                  value={uploadForm.modelType}
                  onChange={(e) => updateUploadField("modelType", e.target.value)}
                >
                  <option value="mrdpm">mrdpm</option>
                  <option value="medgemma">medgemma</option>
                </select>
              </label>
              <label className="span-2">
                Agent 问题（可选）
                <input
                  value={uploadForm.question}
                  onChange={(e) => updateUploadField("question", e.target.value)}
                  placeholder="例如：请给出取栓相关风险评估"
                />
              </label>
            </div>

            <div className="upload-files">
              {UPLOAD_FIELDS.map((field) => {
                const currentFile = uploadForm.files[field.key];
                const selected = currentFile instanceof File;
                return (
                  <label key={field.key} className={`file-picker ${selected ? "selected" : ""}`}>
                    <span className="file-picker-head">
                      <span>{field.label}{field.required ? " *" : ""}</span>
                      <span className="file-picker-state">{selected ? "已选择" : "未选择"}</span>
                    </span>
                    <input
                      type="file"
                      accept={NIFTI_ACCEPT}
                      onChange={(e) => updateUploadFile(field.key, e.target.files?.[0] || null)}
                    />
                    <span className="file-picker-name">{selected ? currentFile.name : "请选择 .nii / .nii.gz 文件"}</span>
                  </label>
                );
              })}
            </div>

            <div className="launcher-actions">
              <button className="primary-btn" type="submit" disabled={uploading}>
                {uploading ? "上传并启动中..." : "上传并进入主页面"}
              </button>
            </div>
            <p className="upload-stage-note">
              {uploadStage < 3 ? "请先选择 NCCT 文件以激活完整上传流程。" : "已满足启动条件，可直接提交。"}
            </p>
            {uploadError ? <div className="error-box">{uploadError}</div> : null}
          </form>
          <div className="recent-cases">
            {(bootstrapData?.candidates || []).map((candidate) => (
              <button key={`${candidate.patient_id || "-"}:${candidate.file_id || "-"}:${candidate.run_id || "-"}`} className="recent-case-card" onClick={() => enterCandidate(candidate)}>
                <div className="recent-case-head">
                  <strong>{candidate.label || `patient ${candidate.patient_id || "-"}`}</strong>
                  <span className="chip">{candidate.source || "-"}</span>
                </div>
                <div className="recent-case-meta">
                  <span>patient_id {fmt(candidate.patient_id)}</span>
                  <span>file_id {fmt(candidate.file_id)}</span>
                  <span>run_id {fmt(candidate.run_id)}</span>
                </div>
              </button>
            ))}
          </div>
            </>
          ) : (
            <section className="kb-manager">
              <div className="kb-manager-head">
                <h3>知识库书架</h3>
                <div className="launcher-actions">
                  <button onClick={() => loadKb(true)} disabled={kbLoading}>{kbLoading ? "刷新中..." : "刷新书架"}</button>
                </div>
              </div>
              <p className="kb-manager-subtitle">按置信度等级从高到低分层展示（S/A/B/C/D）。越靠上代表证据质量越高。</p>
              {isKnowledgeRoute() && (ctx.runId || run.run_id) ? (
                <div className="kg-run-context">
                  <strong>当前任务知识上下文</strong>
                  <span className="chip">run_id {ctx.runId || run.run_id}</span>
                  {(left.available_modalities || []).map((item) => <span key={item} className="chip">{item}</span>)}
                  {(run?.planner_input?.question || run?.planner_input?.goal_question) ? (
                    <span className="chip">问题：{run.planner_input.question || run.planner_input.goal_question}</span>
                  ) : null}
                </div>
              ) : null}
              <div className="launcher-meta">
                <span className="chip">docs {(kbDocs || []).length}</span>
                <span className="chip">
                  {kbSelectedType === "related" && !kbGraph
                    ? "kg nodes 待选择任务"
                    : `kg nodes ${kbGraph?.stats?.node_count || kbGraph?.nodes?.length || 0}`}
                </span>
                {KB_GRADES.map((grade) => (
                  <span key={grade} className="chip">{grade}: {kbBuckets[grade]?.length || 0}</span>
                ))}
              </div>
              {kbError ? <div className="error-box">{kbError}</div> : null}
              <div className="kb-view-tabs" role="tablist" aria-label="knowledge-base-views">
                <button
                  className={`kb-view-tab ${kbView === "shelf" ? "active" : ""}`}
                  onClick={() => setKbView("shelf")}
                >
                  书架
                </button>
                <button
                  className={`kb-view-tab ${kbView === "graph" ? "active" : ""}`}
                  onClick={() => {
                    setKbView("graph");
                    loadKbGraph("", false);
                  }}
                >
                  知识图谱
                </button>
              </div>
              {kbView === "graph" ? (
                <KnowledgeGraphView
                  graph={kbGraph}
                  catalog={kbCatalog}
                  routeResult={kbRouteResult}
                  selectedType={kbSelectedType}
                  loading={kbGraphLoading}
                  contextLoading={kbContextResolving || (bootstrapping && !bootstrapData)}
                  showContextPicker={
                    kbSelectedType === "related"
                    && !kbRouteResult
                    && !kbGraphLoading
                    && !kbContextResolving
                    && !(bootstrapping && !bootstrapData)
                  }
                  candidates={bootstrapData?.candidates || []}
                  candidateLoading={bootstrapping}
                  error={kbGraphError}
                  query={kbGraphQuery}
                  onQueryChange={setKbGraphQuery}
                  onSearch={(query) => {
                    setKbSelectedType("related");
                    loadKbGraph(query, true, "related");
                  }}
                  onRebuild={rebuildGraph}
                  onSelectType={(kgType) => {
                    if (kgType === kbSelectedType && kbGraphLoaded) return;
                    setKbSelectedType(kgType);
                    setKbGraphLoaded(false);
                    loadKbGraph("", true, kgType);
                  }}
                  onSelectCandidate={selectKnowledgeCandidate}
                  onRefreshCandidates={() => loadBootstrap(false)}
                />
              ) : (
              <div className="kb-shelves">
                {KB_GRADES.map((grade) => (
                  <section key={grade} className={`kb-shelf grade-${grade.toLowerCase()}`}>
                    <div className="kb-shelf-head">
                      <h4>{grade} 级书架</h4>
                      <span className="chip">{kbBuckets[grade]?.length || 0} 份</span>
                    </div>
                    <div className="kb-shelf-grid">
                      {(kbBuckets[grade] || []).length === 0 ? <p className="muted">暂无文档</p> : null}
                      {(kbBuckets[grade] || []).map((doc) => (
                        <article key={doc.fileName} className="kb-book">
                          <div className="kb-book-spine" />
                          <div className="kb-book-main">
                            <div className="kb-book-title-row">
                              <strong>{doc.title || doc.fileName}</strong>
                              <span className={`chip kb-grade-chip grade-${String(doc.confidence_grade || "C").toLowerCase()}`}>
                                {String(doc.confidence_grade || "C").toUpperCase()} {(Number(doc.confidence_score || 0) * 100).toFixed(0)}%
                              </span>
                            </div>
                            <p className="kb-book-summary">{doc.summary || "暂无摘要"}</p>
                            <div className="kb-book-meta">
                              <span>来源 {doc.source || "-"}</span>
                              <span>版本 {doc.version || "-"}</span>
                              <span>类型 {doc.doc_type || "guideline"}</span>
                            </div>
                            <div className="kb-book-meta">
                              <span>文件 {doc.fileName}</span>
                            </div>
                            <div className="kb-book-actions">
                              <a href={doc.url} target="_blank" rel="noreferrer">打开文档</a>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
              )}
            </section>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="topbar glass">
        <div>
          <p className="eyebrow">NeuroMatrix Agent Cockpit</p>
          <h1>实施总览控制台</h1>
        </div>
        <div className="toolbar">
          <span className="chip patient-chip">
            <span className="patient-chip-label">病人</span>
            <strong>{fmt(run.patient_id || left?.patient?.patient_id)}</strong>
          </span>
          <button onClick={openKnowledgeGraph}>知识库 / 图谱</button>
          <button onClick={() => refresh(true)} disabled={loading}>
            {loading ? "刷新中..." : "刷新"}
          </button>
        </div>
      </header>

      {error ? <div className="error-box">{error}</div> : null}

      <main className="cockpit-grid">
        <section className="panel glass left-panel">
          <h2 className="panel-title"><span className="panel-title-icon" aria-hidden="true" />病例与输入</h2>
          <div className="kv"><span>patient_id</span><strong>{fmt(run.patient_id || left?.patient?.patient_id)}</strong></div>
          <div className="kv"><span>file_id</span><strong>{fmt(run.file_id)}</strong></div>
          <div className="kv"><span>模态</span><strong>{(left.available_modalities || []).join(" + ") || "-"}</strong></div>
          <div className="kv"><span>半球</span><strong>{fmt(left.hemisphere)}</strong></div>
          <div className="kv"><span>性别</span><strong>{fmt(left?.patient?.sex)}</strong></div>
          <div className="kv"><span>年龄</span><strong>{fmt(left?.patient?.age)}</strong></div>
          <div className="kv"><span>NIHSS</span><strong>{fmt(left?.patient?.admission_nihss)}</strong></div>
          <div className="kv"><span>run_id</span><strong>{fmt(run.run_id)}</strong></div>
          <div className="kv"><span>状态</span><strong className={statusClass(run.status)}>{fmt(run.status)}</strong></div>
        </section>

        <section className="panel glass dag-panel">
          <div className="panel-head">
            <h2 className="panel-title"><span className="panel-title-icon" aria-hidden="true" />DAG 处理监控</h2>
            <div className="chip-wrap">
              <span className="chip">nodes {dag.node_count || 0}</span>
              <span className="chip">edges {dag.edge_count || 0}</span>
              <span className="chip">path {fmt(dag.imaging_path)}</span>
            </div>
          </div>
          <div className="dag-scroll">
            {Object.entries(laneGroups).map(([lane, nodes]) => (
              <div key={lane} className="lane">
                <h3>{lane}</h3>
                <div className="lane-row">
                  {nodes.map((node, index) => (
                    <button
                      key={node.id}
                      className={`node-card ${statusClass(node.status)}`}
                      style={{ animationDelay: `${Math.min(index, 10) * 45}ms` }}
                      onClick={() => openNode(node)}
                    >
                      <span className="node-title">{node.title || node.step_key}</span>
                      <span className="node-key">{node.step_key}</span>
                      <span className="node-meta">{fmt(node.status)}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel glass right-panel">
          <h2 className="panel-title"><span className="panel-title-icon" aria-hidden="true" />结论 / 证据 / 风险</h2>
          <div className="kv"><span>Consensus</span><strong>{fmt(right.consensus)}</strong></div>
          <div className="kv"><span>ICV</span><strong>{fmt(validation?.icv?.status)}</strong></div>
          <div className="kv"><span>EKV</span><strong>{fmt(validation?.ekv?.status)}</strong></div>
          <div className="kv"><span>Support Rate</span><strong>{validation?.ekv?.support_rate == null ? "-" : `${(Number(validation.ekv.support_rate) * 100).toFixed(1)}%`}</strong></div>
          <div className="kv"><span>Traceability</span><strong>{fmt(validation?.traceability?.status)}</strong></div>
          <h3>风险提示</h3>
          <div className="risk-list">
            {riskItems.length === 0 ? <p className="muted">暂无高风险提示</p> : null}
            {riskItems.map((item) => (
              <article key={`${item.event_seq}_${item.tool}`} className={`risk-item level-${item.level}`}>
                <p>{item.message || "-"}</p>
                <small>{item.tool} #{item.event_seq}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="panel glass bottom-panel">
          <h2 className="panel-title"><span className="panel-title-icon" aria-hidden="true" />运行日志与时间线</h2>
          <div className="timeline">
            {logs.length === 0 ? <p className="muted">暂无日志</p> : null}
            {logs.map((evt) => (
              <div key={evt.event_id || `${evt.tool_name}_${evt.event_seq}`} className="timeline-row">
                <div className="dot" />
                <div className="timeline-main">
                  <div className="timeline-title">
                    <strong>{evt.tool_name || "-"}</strong>
                    <span className={statusClass(evt.status)}>{fmt(evt.status)}</span>
                  </div>
                  <p>{evt.result_summary || evt.message || "-"}</p>
                </div>
                <div className="timeline-side">
                  <small>#{fmt(evt.event_seq)}</small>
                  <small>{fmt(evt.timestamp)}</small>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      {selectedNode ? (
        <div className="modal-wrap" onClick={() => setSelectedNode(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>{selectedNode.title || selectedNode.step_key}</h3>
              <button onClick={() => setSelectedNode(null)}>关闭</button>
            </div>
            <div className="modal-kv">
              <div className="kv"><span>step_key</span><strong>{fmt(selectedNode.step_key)}</strong></div>
              <div className="kv"><span>confidence</span><strong>{fmt(selectedNode.confidence)}%</strong></div>
              <div className="kv"><span>latency_ms</span><strong>{fmt(selectedNode.latency_ms)}ms</strong></div>
              <div className="kv"><span>risk_level</span><strong>{fmt(selectedNode.risk_level || selectedNode.risk || "none")}</strong></div>
              <div className="kv"><span>retryable</span><strong>{String(Boolean(selectedNode.retryable))}</strong></div>
              <div className="kv"><span>error_code</span><strong>{fmt(selectedNode.error_code || "-")}</strong></div>
              <div className="kv"><span>message</span><strong className="text-wrap">{fmt(selectedNode.message || "-")}</strong></div>
              {selectedNode.parents ? (
                <div className="kv"><span>parents</span><strong>{Array.isArray(selectedNode.parents) ? selectedNode.parents.join(", ") : fmt(selectedNode.parents)}</strong></div>
              ) : null}
              {selectedNode.children ? (
                <div className="kv"><span>children</span><strong>{Array.isArray(selectedNode.children) ? selectedNode.children.join(", ") : fmt(selectedNode.children)}</strong></div>
              ) : null}
              {selectedNode.secondary_deps !== undefined ? (
                <div className="kv"><span>secondary_deps</span><strong>{fmt(selectedNode.secondary_deps)}</strong></div>
              ) : null}
            </div>
            {nodeLoading ? <p className="muted">节点详情加载中...</p> : null}
            {nodeDetail?.error ? <p className="error-box">{nodeDetail.error}</p> : null}
            <div className="io-grid">
              <section>
                <h4>输入</h4>
                <pre>{prettyJson(nodeDetail?.input_payload || selectedNode.input_payload)}</pre>
              </section>
              <section>
                <h4>输出</h4>
                <pre>{prettyJson(nodeDetail?.output_payload || selectedNode.output_payload)}</pre>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
