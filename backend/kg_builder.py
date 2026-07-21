import json
import os
import re
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


GRAPH_VERSION = "stroke-kg-v1" # AI辅助生成：GLM-5, 2026-04-13
DEFAULT_GRAPH_PATH = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    "runtime",
    "kg",
    "stroke_kg.json",
)


CONCEPTS: List[Dict[str, Any]] = [
    {
        "id": "concept_ais",
        "label": "Acute Ischemic Stroke",
        "name_cn": "急性缺血性卒中",
        "type": "concept",
        "aliases": ["acute ischemic stroke", "ischemic stroke", "ais", "缺血性卒中", "急性缺血"],
    },
    {
        "id": "concept_lvo",
        "label": "Large Vessel Occlusion",
        "name_cn": "大血管闭塞",
        "type": "concept",
        "aliases": ["large vessel occlusion", "lvo", "大血管闭塞", "大血管堵塞", "颅内大血管"],
    },
    {
        "id": "concept_mevo",
        "label": "Medium Vessel Occlusion",
        "name_cn": "中血管闭塞",
        "type": "concept",
        "aliases": ["medium vessel occlusion", "mevo", "中血管闭塞", "中血管堵塞"],
    },
    {
        "id": "metric_core",
        "label": "Core Infarct Volume",
        "name_cn": "核心梗死体积",
        "type": "imaging_metric",
        "aliases": ["core infarct", "ischemic core", "core volume", "核心梗死", "梗死核心"],
    },
    {
        "id": "metric_penumbra",
        "label": "Penumbra Volume",
        "name_cn": "半暗带体积",
        "type": "imaging_metric",
        "aliases": ["penumbra", "hypoperfusion", "半暗带", "低灌注"],
    },
    {
        "id": "metric_mismatch",
        "label": "Mismatch Ratio",
        "name_cn": "不匹配比值",
        "type": "imaging_metric",
        "aliases": ["mismatch ratio", "mismatch", "不匹配", "错配"],
    },
    {
        "id": "metric_nihss",
        "label": "NIHSS",
        "name_cn": "NIHSS评分",
        "type": "imaging_metric",
        "aliases": ["nihss", "national institutes of health stroke scale", "nihss评分", "神经功能缺损"],
    },
    {
        "id": "criterion_time_window",
        "label": "Treatment Time Window",
        "name_cn": "治疗时间窗",
        "type": "criterion",
        "aliases": ["time window", "onset", "treatment window", "发病时间", "时间窗", "发病至入院"],
    },
    {
        "id": "criterion_aspects",
        "label": "ASPECTS",
        "name_cn": "ASPECTS评分",
        "type": "criterion",
        "aliases": ["aspects", "alberta stroke program early ct score"],
    },
    {
        "id": "modality_ncct",
        "label": "NCCT",
        "name_cn": "非增强CT",
        "type": "concept",
        "aliases": ["ncct", "non-contrast ct", "noncontrast ct", "非增强ct", "平扫ct"],
    },
    {
        "id": "modality_cta",
        "label": "CTA",
        "name_cn": "CT血管成像",
        "type": "concept",
        "aliases": ["cta", "ct angiography", "血管成像", "动脉期", "静脉期", "延迟期"],
    },
    {
        "id": "modality_ctp",
        "label": "CTP",
        "name_cn": "CT灌注",
        "type": "concept",
        "aliases": ["ctp", "ct perfusion", "perfusion", "灌注", "cbf", "cbv", "tmax"],
    },
    {
        "id": "treatment_ivt",
        "label": "Intravenous Thrombolysis",
        "name_cn": "静脉溶栓",
        "type": "treatment",
        "aliases": ["intravenous thrombolysis", "thrombolysis", "alteplase", "rt-pa", "静脉溶栓", "阿替普酶"],
    },
    {
        "id": "treatment_evt",
        "label": "Mechanical Thrombectomy",
        "name_cn": "机械取栓",
        "type": "treatment",
        "aliases": ["mechanical thrombectomy", "endovascular therapy", "evt", "thrombectomy", "取栓", "机械取栓", "血管内治疗"],
    },
    {
        "id": "risk_hemorrhage",
        "label": "Hemorrhage Risk",
        "name_cn": "出血风险",
        "type": "criterion",
        "aliases": ["hemorrhage", "bleeding risk", "出血风险", "脑出血", "出血转化"],
    },
    # --- 影像征象 imaging signs ---
    {
        "id": "sign_early_ischemia",
        "label": "Early Ischemic Change",
        "name_cn": "早期缺血征",
        "type": "imaging_sign",
        "aliases": ["early ischemic change", "early ischemic signs", "early ischemia", "早期缺血", "早期缺血征", "灰白质界限模糊", "脑沟消失", "岛带征"],
    },
    {
        "id": "sign_dense_vessel",
        "label": "Hyperdense Vessel Sign",
        "name_cn": "致密动脉征",
        "type": "imaging_sign",
        "aliases": ["hyperdense vessel sign", "hyperdense mca sign", "dense artery sign", "致密动脉征", "高密度血管征", "大脑中动脉高密度征"],
    },
    # --- 血管解剖 vascular anatomy ---
    {
        "id": "vessel_ica",
        "label": "Internal Carotid Artery",
        "name_cn": "颈内动脉(ICA)",
        "type": "anatomy",
        "aliases": ["internal carotid artery", "ica", "颈内动脉", "颈动脉"],
    },
    {
        "id": "vessel_m1",
        "label": "MCA M1",
        "name_cn": "大脑中动脉M1段",
        "type": "anatomy",
        "aliases": ["mca m1", "m1 segment", "middle cerebral artery m1", "m1段", "大脑中动脉m1"],
    },
    {
        "id": "vessel_m2",
        "label": "MCA M2",
        "name_cn": "大脑中动脉M2段",
        "type": "anatomy",
        "aliases": ["mca m2", "m2 segment", "m2段", "大脑中动脉m2"],
    },
    {
        "id": "vessel_m3",
        "label": "MCA M3",
        "name_cn": "大脑中动脉M3段",
        "type": "anatomy",
        "aliases": ["mca m3", "m3 segment", "m3段", "大脑中动脉m3"],
    },
    {
        "id": "vessel_aca",
        "label": "Anterior Cerebral Artery",
        "name_cn": "大脑前动脉(ACA)",
        "type": "anatomy",
        "aliases": ["anterior cerebral artery", "aca", "大脑前动脉"],
    },
    {
        "id": "vessel_pca",
        "label": "Posterior Cerebral Artery",
        "name_cn": "大脑后动脉(PCA)",
        "type": "anatomy",
        "aliases": ["posterior cerebral artery", "pca", "大脑后动脉"],
    },
    {
        "id": "vessel_basilar",
        "label": "Basilar Artery",
        "name_cn": "基底动脉",
        "type": "anatomy",
        "aliases": ["basilar artery", "basilar", "基底动脉", "后循环闭塞", "椎基底动脉"],
    },
    # --- 灌注参数 perfusion parameters ---
    {
        "id": "metric_cbf",
        "label": "CBF",
        "name_cn": "脑血流量(CBF)",
        "type": "imaging_metric",
        "aliases": ["cbf", "cerebral blood flow", "脑血流量", "血流量"],
    },
    {
        "id": "metric_cbv",
        "label": "CBV",
        "name_cn": "脑血容量(CBV)",
        "type": "imaging_metric",
        "aliases": ["cbv", "cerebral blood volume", "脑血容量", "血容量"],
    },
    {
        "id": "metric_tmax",
        "label": "Tmax",
        "name_cn": "达峰时间(Tmax)",
        "type": "imaging_metric",
        "aliases": ["tmax", "time to maximum", "达峰时间", "残余功能达峰时间"],
    },
    # --- 风险禁忌 risk & contraindication ---
    {
        "id": "risk_anticoagulation",
        "label": "Anticoagulation",
        "name_cn": "抗凝状态",
        "type": "risk",
        "aliases": ["anticoagulation", "anticoagulant", "warfarin", "doac", "noac", "inr", "抗凝", "华法林", "口服抗凝药"],
    },
    {
        "id": "risk_glucose",
        "label": "Blood Glucose",
        "name_cn": "血糖",
        "type": "risk",
        "aliases": ["blood glucose", "hypoglycemia", "hyperglycemia", "glucose", "血糖", "低血糖", "高血糖"],
    },
    {
        "id": "risk_blood_pressure",
        "label": "Blood Pressure",
        "name_cn": "血压",
        "type": "risk",
        "aliases": ["blood pressure", "hypertension", "systolic", "血压", "高血压", "收缩压", "血压控制"],
    },
    {
        "id": "risk_history",
        "label": "Medical History",
        "name_cn": "既往病史",
        "type": "risk",
        "aliases": ["medical history", "prior stroke", "recent surgery", "既往病史", "既往卒中", "近期手术", "病史"],
    },
    # --- 转诊 referral ---
    {
        "id": "concept_referral",
        "label": "Referral Pathway",
        "name_cn": "转诊规范",
        "type": "referral",
        "aliases": ["referral", "transfer", "drip and ship", "mothership", "转诊", "转院", "绿色通道", "卒中中心"],
    },
    # --- 病例经验 case experience ---
    {
        "id": "case_history",
        "label": "Historical Cases",
        "name_cn": "历史病例",
        "type": "case",
        "aliases": ["historical case", "case series", "历史病例", "既往病例"],
    },
    {
        "id": "case_feedback",
        "label": "Clinician Feedback",
        "name_cn": "医生反馈",
        "type": "case",
        "aliases": ["clinician feedback", "expert feedback", "医生反馈", "专家反馈"],
    },
    {
        "id": "case_similar",
        "label": "Similar Case Retrieval",
        "name_cn": "相似病例检索",
        "type": "case",
        "aliases": ["similar case", "case retrieval", "相似病例", "病例检索"],
    },
]


STATIC_EDGES: List[Tuple[str, str, str, str, float]] = [
    ("concept_ais", "modality_ncct", "assessed_by", "assessed by", 0.88),
    ("concept_ais", "modality_cta", "assessed_by", "assessed by", 0.88),
    ("concept_ais", "modality_ctp", "assessed_by", "assessed by", 0.88),
    ("modality_cta", "concept_lvo", "indicates", "identifies", 0.90),
    ("modality_ctp", "metric_core", "measures", "measures", 0.92),
    ("modality_ctp", "metric_penumbra", "measures", "measures", 0.92),
    ("metric_penumbra", "metric_mismatch", "supports", "supports mismatch", 0.90),
    ("metric_core", "metric_mismatch", "supports", "supports mismatch", 0.86),
    ("concept_lvo", "treatment_evt", "indicates", "supports EVT evaluation", 0.95),
    ("criterion_time_window", "treatment_evt", "has_threshold", "time-window criterion", 0.90),
    ("criterion_time_window", "treatment_ivt", "has_threshold", "time-window criterion", 0.88),
    ("risk_hemorrhage", "treatment_ivt", "contraindicates", "may contraindicate", 0.82),
    ("risk_hemorrhage", "treatment_evt", "contraindicates", "risk modifier", 0.72),
    ("criterion_aspects", "treatment_evt", "supports", "selection criterion", 0.80),
    ("metric_nihss", "concept_lvo", "related_to", "clinical severity clue", 0.72),
]


CLINICAL_GRAPH_NODES: List[Dict[str, Any]] = [
    {
        "id": "concept_ais",
        "label": "急性缺血性卒中",
        "type": "disease",
        "column": 0,
        "order": 0,
        "description": "卒中诊疗路径的中心疾病实体。",
        "clinical_meaning": "用于汇总影像检查、血管闭塞分型、灌注指标和再通治疗决策。",
        "concept_ids": ["concept_ais"],
    },
    {
        "id": "modality_ncct",
        "label": "NCCT",
        "type": "modality",
        "column": 1,
        "order": 0,
        "description": "无增强头颅 CT。",
        "clinical_meaning": "用于初筛出血、早期缺血征象和大面积低密度改变。",
        "concept_ids": ["modality_ncct"],
    },
    {
        "id": "modality_cta",
        "label": "CTA",
        "type": "modality",
        "column": 1,
        "order": 1,
        "description": "CT 血管成像。",
        "clinical_meaning": "用于判断大/中血管闭塞和责任血管通畅性。",
        "concept_ids": ["modality_cta", "concept_lvo", "concept_mevo"],
    },
    {
        "id": "modality_ctp",
        "label": "CTP",
        "type": "modality",
        "column": 1,
        "order": 2,
        "description": "CT 灌注成像。",
        "clinical_meaning": "用于估计核心梗死、半暗带和灌注不匹配。",
        "concept_ids": ["modality_ctp", "metric_core", "metric_penumbra", "metric_mismatch"],
    },
    {
        "id": "vascular_normal",
        "label": "正常",
        "type": "vascular_class",
        "column": 2,
        "order": 0,
        "description": "未提示明确血管闭塞。",
        "clinical_meaning": "通常降低机械取栓优先级，但仍需结合临床和全序列复核。",
        "concept_ids": ["modality_cta"],
    },
    {
        "id": "concept_mevo",
        "label": "中血管闭塞",
        "type": "vascular_class",
        "column": 2,
        "order": 1,
        "description": "中等管径动脉闭塞。",
        "clinical_meaning": "提示需结合部位、症状严重度和影像获益评估再通策略。",
        "concept_ids": ["concept_mevo"],
    },
    {
        "id": "concept_lvo",
        "label": "大血管闭塞",
        "type": "vascular_class",
        "column": 2,
        "order": 2,
        "description": "颅内或颈部大血管闭塞。",
        "clinical_meaning": "是优先评估机械取栓适应证的重要影像分型。",
        "concept_ids": ["concept_lvo"],
    },
    {
        "id": "metric_core",
        "label": "核心梗死体积",
        "type": "imaging_metric",
        "column": 2,
        "order": 3,
        "description": "不可逆缺血损伤体积估计。",
        "clinical_meaning": "核心越大，出血转化和治疗风险越高，取栓获益需更谨慎评估。",
        "concept_ids": ["metric_core"],
    },
    {
        "id": "metric_penumbra",
        "label": "半暗带体积",
        "type": "imaging_metric",
        "column": 2,
        "order": 4,
        "description": "潜在可挽救脑组织体积估计。",
        "clinical_meaning": "半暗带越大，若及时再通，潜在获益越明确。",
        "concept_ids": ["metric_penumbra"],
    },
    {
        "id": "metric_mismatch",
        "label": "不匹配比值",
        "type": "imaging_metric",
        "column": 2,
        "order": 5,
        "description": "低灌注组织与核心梗死之间的比例关系。",
        "clinical_meaning": "显著不匹配支持存在可挽救组织，是再通获益判断的重要依据。",
        "concept_ids": ["metric_mismatch"],
    },
    {
        "id": "criterion_aspects",
        "label": "ASPECTS",
        "type": "criterion",
        "column": 3,
        "order": 0,
        "description": "早期缺血改变评分。",
        "clinical_meaning": "用于辅助评估梗死范围和取栓治疗选择。",
        "concept_ids": ["criterion_aspects"],
    },
    {
        "id": "metric_nihss",
        "label": "NIHSS评分",
        "type": "criterion",
        "column": 3,
        "order": 1,
        "description": "神经功能缺损严重程度评分。",
        "clinical_meaning": "症状严重程度可提示大血管闭塞可能，并影响治疗收益判断。",
        "concept_ids": ["metric_nihss"],
    },
    {
        "id": "criterion_time_window",
        "label": "治疗时间窗",
        "type": "criterion",
        "column": 3,
        "order": 2,
        "description": "发病到评估/治疗的时间范围。",
        "clinical_meaning": "决定静脉溶栓、机械取栓和影像选择策略的关键条件。",
        "concept_ids": ["criterion_time_window"],
    },
    {
        "id": "risk_hemorrhage",
        "label": "出血风险",
        "type": "risk",
        "column": 3,
        "order": 3,
        "description": "出血或出血转化风险。",
        "clinical_meaning": "影响溶栓、取栓和抗栓策略的风险收益平衡。",
        "concept_ids": ["risk_hemorrhage", "metric_core"],
    },
    {
        "id": "criterion_contraindication",
        "label": "禁忌证",
        "type": "risk",
        "column": 3,
        "order": 4,
        "description": "限制溶栓或取栓的临床/影像条件。",
        "clinical_meaning": "需要在再通治疗前完成快速排查。",
        "concept_ids": ["risk_hemorrhage", "criterion_time_window"],
    },
    {
        "id": "treatment_ivt",
        "label": "静脉溶栓",
        "type": "treatment",
        "column": 4,
        "order": 0,
        "description": "符合条件时考虑 rt-PA/替奈普酶等静脉溶栓治疗。",
        "clinical_meaning": "依赖时间窗、禁忌证和出血风险综合判断。",
        "concept_ids": ["treatment_ivt", "criterion_time_window", "risk_hemorrhage"],
    },
    {
        "id": "treatment_evt",
        "label": "机械取栓",
        "type": "treatment",
        "column": 4,
        "order": 1,
        "description": "血管内机械取栓治疗。",
        "clinical_meaning": "大血管闭塞、合适时间窗和有利影像选择是关键依据。",
        "concept_ids": ["treatment_evt", "concept_lvo", "metric_mismatch", "criterion_time_window"],
    },
    {
        "id": "treatment_reperfusion",
        "label": "综合再通治疗",
        "type": "treatment",
        "column": 4,
        "order": 2,
        "description": "结合溶栓、取栓和围术期管理的综合策略。",
        "clinical_meaning": "用于把血管闭塞、可挽救组织、时间窗和风险因素整合为治疗路径。",
        "concept_ids": ["treatment_ivt", "treatment_evt", "concept_ais"],
    },
]


CLINICAL_GRAPH_EDGES: List[Tuple[str, str, str, str, float]] = [
    ("concept_ais", "modality_ncct", "assessed_by", "初筛出血/缺血", 0.92),
    ("concept_ais", "modality_cta", "assessed_by", "评估血管通畅", 0.92),
    ("concept_ais", "modality_ctp", "assessed_by", "评估灌注状态", 0.90),
    ("modality_cta", "vascular_normal", "identifies", "三分类", 0.72),
    ("modality_cta", "concept_mevo", "identifies", "识别中血管闭塞", 0.82),
    ("modality_cta", "concept_lvo", "identifies", "识别大血管闭塞", 0.94),
    ("modality_ctp", "metric_core", "measures", "测量核心梗死", 0.94),
    ("modality_ctp", "metric_penumbra", "measures", "测量半暗带", 0.94),
    ("modality_ctp", "metric_mismatch", "measures", "计算不匹配", 0.92),
    ("modality_ncct", "criterion_aspects", "measures", "评估早期缺血", 0.80),
    ("metric_core", "risk_hemorrhage", "risk_modifier", "核心越大风险越高", 0.82),
    ("metric_penumbra", "metric_mismatch", "supports", "提示可挽救组织", 0.88),
    ("metric_mismatch", "treatment_evt", "supports", "支持再通获益评估", 0.88),
    ("concept_lvo", "treatment_evt", "supports", "优先评估取栓", 0.96),
    ("concept_mevo", "treatment_reperfusion", "supports", "个体化再通评估", 0.74),
    ("metric_nihss", "concept_lvo", "supports", "严重症状提示闭塞可能", 0.72),
    ("criterion_aspects", "treatment_evt", "supports", "取栓选择条件", 0.80),
    ("criterion_time_window", "treatment_ivt", "supports", "溶栓时间窗", 0.90),
    ("criterion_time_window", "treatment_evt", "supports", "取栓时间窗", 0.90),
    ("risk_hemorrhage", "treatment_ivt", "risk_modifier", "影响溶栓风险", 0.86),
    ("risk_hemorrhage", "treatment_evt", "risk_modifier", "影响围术期风险", 0.76),
    ("criterion_contraindication", "treatment_ivt", "contraindicates", "限制溶栓", 0.84),
    ("criterion_contraindication", "treatment_evt", "contraindicates", "限制取栓", 0.72),
    ("treatment_ivt", "treatment_reperfusion", "supports", "桥接/综合策略", 0.78),
    ("treatment_evt", "treatment_reperfusion", "supports", "血管内再通", 0.88),
]


def _cn(node_id: str, label: str, node_type: str, column: int, order: int, description: str, clinical_meaning: str, concept_ids: List[str]) -> Dict[str, Any]:
    """Compact helper to declare a category graph node."""
    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "column": column,
        "order": order,
        "description": description,
        "clinical_meaning": clinical_meaning,
        "concept_ids": concept_ids,
    }


# 多分类知识图谱：每个分类是一张自洽的临床小图谱，节点通过 concept_ids
# 关联到底层证据（PDF chunk）以及"本轮任务"的相关性匹配。
CATEGORY_GRAPHS: List[Dict[str, Any]] = [
    {
        "id": "guideline",
        "label": "指南图谱",
        "icon": "📘",
        "description": "溶栓、取栓、影像评估与转诊规范的指南决策路径。",
        "focus": ["溶栓", "取栓", "影像评估", "转诊规范"],
        "columns": ["疾病", "影像评估", "适应证", "治疗决策", "转诊"],
        "nodes": [
            _cn("gl_ais", "急性缺血性卒中", "disease", 0, 0, "指南路径的中心疾病实体。", "统筹影像评估、适应证判断与再通治疗决策。", ["concept_ais"]),
            _cn("gl_imaging", "影像评估", "modality", 1, 0, "NCCT/CTA/CTP 一体化影像评估。", "指南要求先完成出血排查、血管评估与灌注评估。", ["modality_ncct", "modality_cta", "modality_ctp"]),
            _cn("gl_time", "发病时间窗", "criterion", 1, 1, "发病至就诊/治疗的时间。", "决定溶栓与取栓路径以及影像选择策略。", ["criterion_time_window"]),
            _cn("gl_lvo", "大血管闭塞", "vascular_class", 2, 0, "CTA 判定的大血管闭塞。", "取栓适应证的核心影像依据。", ["concept_lvo"]),
            _cn("gl_aspects", "ASPECTS", "criterion", 2, 1, "早期缺血改变评分。", "辅助判断梗死范围与取栓获益。", ["criterion_aspects"]),
            _cn("gl_mismatch", "灌注不匹配", "imaging_metric", 2, 2, "核心/半暗带不匹配。", "扩展时间窗取栓的关键选择条件。", ["metric_mismatch"]),
            _cn("gl_ivt", "静脉溶栓", "treatment", 3, 0, "rt-PA / 替奈普酶溶栓。", "依赖时间窗、禁忌证与出血风险综合判断。", ["treatment_ivt"]),
            _cn("gl_evt", "机械取栓", "treatment", 3, 1, "血管内机械取栓。", "大血管闭塞 + 合适时间窗 + 有利影像时优先评估。", ["treatment_evt"]),
            _cn("gl_referral", "转诊规范", "referral", 4, 0, "转诊/绿色通道流程。", "无取栓能力时应快速转运至具备条件的卒中中心。", ["concept_referral"]),
        ],
        "edges": [
            ("gl_ais", "gl_imaging", "assessed_by", "影像评估", 0.94),
            ("gl_ais", "gl_time", "assessed_by", "记录时间窗", 0.9),
            ("gl_imaging", "gl_lvo", "identifies", "识别闭塞", 0.94),
            ("gl_imaging", "gl_aspects", "measures", "评估缺血范围", 0.82),
            ("gl_imaging", "gl_mismatch", "measures", "评估可挽救组织", 0.9),
            ("gl_time", "gl_ivt", "supports", "溶栓时间窗", 0.9),
            ("gl_time", "gl_evt", "supports", "取栓时间窗", 0.9),
            ("gl_lvo", "gl_evt", "supports", "优先取栓", 0.96),
            ("gl_aspects", "gl_evt", "supports", "选择条件", 0.8),
            ("gl_mismatch", "gl_evt", "supports", "扩展窗获益", 0.86),
            ("gl_ivt", "gl_referral", "supports", "桥接转运", 0.72),
            ("gl_evt", "gl_referral", "supports", "转运至取栓中心", 0.8),
        ],
    },
    {
        "id": "imaging_sign",
        "label": "影像征象图谱",
        "icon": "🩻",
        "description": "出血、早期缺血征、致密动脉征、ASPECTS 与闭塞部位征象。",
        "focus": ["出血", "早期缺血征", "致密动脉征", "ASPECTS", "闭塞部位"],
        "columns": ["影像检查", "关键征象", "闭塞部位", "处置提示"],
        "nodes": [
            _cn("sg_imaging", "头颅影像", "modality", 0, 0, "NCCT/CTA 平扫与血管成像。", "征象识别的图像基础。", ["modality_ncct", "modality_cta"]),
            _cn("sg_hemorrhage", "颅内出血", "risk", 1, 0, "脑实质/蛛网膜下腔出血。", "阳性即为溶栓绝对禁忌，须优先排查。", ["risk_hemorrhage"]),
            _cn("sg_early", "早期缺血征", "imaging_sign", 1, 1, "灰白质界限模糊、脑沟消失、岛带征。", "提示早期梗死,影响 ASPECTS 与取栓选择。", ["sign_early_ischemia"]),
            _cn("sg_dense", "致密动脉征", "imaging_sign", 1, 2, "大脑中动脉高密度征。", "提示相应动脉内血栓,间接支持大血管闭塞。", ["sign_dense_vessel"]),
            _cn("sg_aspects", "ASPECTS", "criterion", 1, 3, "早期缺血改变评分。", "量化早期缺血范围。", ["criterion_aspects"]),
            _cn("sg_occlusion", "闭塞部位提示", "vascular_class", 2, 0, "征象指向的责任血管。", "结合征象与 CTA 定位大/中血管闭塞。", ["concept_lvo", "concept_mevo"]),
            _cn("sg_action", "处置提示", "treatment", 3, 0, "征象驱动的下一步。", "出血→停溶栓；大血管征象→启动取栓评估。", ["treatment_ivt", "treatment_evt"]),
        ],
        "edges": [
            ("sg_imaging", "sg_hemorrhage", "identifies", "排查出血", 0.92),
            ("sg_imaging", "sg_early", "identifies", "早期缺血", 0.86),
            ("sg_imaging", "sg_dense", "identifies", "致密动脉征", 0.84),
            ("sg_imaging", "sg_aspects", "measures", "评分", 0.82),
            ("sg_dense", "sg_occlusion", "indicates", "提示血栓", 0.82),
            ("sg_early", "sg_occlusion", "related_to", "缺血区对应", 0.7),
            ("sg_aspects", "sg_occlusion", "related_to", "范围对应", 0.66),
            ("sg_hemorrhage", "sg_action", "contraindicates", "禁溶栓", 0.9),
            ("sg_occlusion", "sg_action", "supports", "评估取栓", 0.88),
        ],
    },
    {
        "id": "vascular_anatomy",
        "label": "解剖血管图谱",
        "icon": "🧠",
        "description": "ICA、M1、M2、M3、ACA、PCA、基底动脉的责任血管解剖。",
        "focus": ["ICA", "M1", "M2", "M3", "ACA", "PCA", "基底动脉"],
        "columns": ["动脉系统", "循环分区", "血管节段", "临床关联"],
        "nodes": [
            _cn("va_root", "颅内动脉系统", "disease", 0, 0, "前循环与后循环供血系统。", "责任血管定位是取栓策略的解剖基础。", ["concept_ais"]),
            _cn("va_anterior", "前循环", "concept", 1, 0, "颈内动脉及其分支系统。", "多数大血管闭塞取栓的主要范围。", ["vessel_ica"]),
            _cn("va_posterior", "后循环", "concept", 1, 1, "椎基底动脉系统。", "基底动脉闭塞病死率高,需积极评估。", ["vessel_basilar"]),
            _cn("va_ica", "颈内动脉 ICA", "anatomy", 2, 0, "颈内动脉。", "ICA 末端闭塞常伴大面积缺血,取栓获益明确。", ["vessel_ica"]),
            _cn("va_m1", "大脑中动脉 M1", "anatomy", 2, 1, "MCA 水平段。", "典型大血管闭塞,取栓一线适应证。", ["vessel_m1"]),
            _cn("va_m2", "大脑中动脉 M2", "anatomy", 2, 2, "MCA 岛叶段。", "部分 M2 闭塞可个体化评估取栓。", ["vessel_m2"]),
            _cn("va_m3", "大脑中动脉 M3", "anatomy", 2, 3, "MCA 皮层段。", "多归为中/远端血管,再通策略需权衡。", ["vessel_m3"]),
            _cn("va_aca", "大脑前动脉 ACA", "anatomy", 2, 4, "大脑前动脉。", "单纯 ACA 闭塞少见,需结合症状评估。", ["vessel_aca"]),
            _cn("va_pca", "大脑后动脉 PCA", "anatomy", 2, 5, "大脑后动脉。", "后循环缺血,取栓证据相对有限。", ["vessel_pca"]),
            _cn("va_basilar", "基底动脉", "anatomy", 2, 6, "基底动脉。", "基底动脉闭塞时间窗可放宽,应积极再通。", ["vessel_basilar"]),
            _cn("va_lvo", "大血管闭塞判定", "vascular_class", 3, 0, "责任血管闭塞分级。", "汇总节段闭塞形成取栓适应证判断。", ["concept_lvo"]),
            _cn("va_evt", "机械取栓", "treatment", 3, 1, "血管内取栓。", "责任血管越近端,取栓获益通常越明确。", ["treatment_evt"]),
        ],
        "edges": [
            ("va_root", "va_anterior", "related_to", "前循环", 0.9),
            ("va_root", "va_posterior", "related_to", "后循环", 0.9),
            ("va_anterior", "va_ica", "related_to", "ICA", 0.86),
            ("va_anterior", "va_m1", "related_to", "M1", 0.86),
            ("va_anterior", "va_m2", "related_to", "M2", 0.8),
            ("va_anterior", "va_m3", "related_to", "M3", 0.74),
            ("va_anterior", "va_aca", "related_to", "ACA", 0.72),
            ("va_posterior", "va_pca", "related_to", "PCA", 0.78),
            ("va_posterior", "va_basilar", "related_to", "基底动脉", 0.88),
            ("va_ica", "va_lvo", "indicates", "大血管", 0.94),
            ("va_m1", "va_lvo", "indicates", "大血管", 0.94),
            ("va_basilar", "va_lvo", "indicates", "大血管", 0.9),
            ("va_lvo", "va_evt", "supports", "取栓评估", 0.94),
        ],
    },
    {
        "id": "perfusion",
        "label": "灌注评估图谱",
        "icon": "🌊",
        "description": "CBF、CBV、Tmax、核心区、半暗带与不匹配的灌注评估。",
        "focus": ["CBF", "CBV", "Tmax", "核心区", "半暗带", "mismatch"],
        "columns": ["灌注检查", "灌注参数", "组织分区", "不匹配", "再通决策"],
        "nodes": [
            _cn("pf_ctp", "CT 灌注 CTP", "modality", 0, 0, "CT 灌注成像。", "估计核心梗死、半暗带与灌注不匹配。", ["modality_ctp"]),
            _cn("pf_cbf", "CBF 脑血流量", "imaging_metric", 1, 0, "脑血流量。", "rCBF<30% 常用于界定核心梗死。", ["metric_cbf"]),
            _cn("pf_cbv", "CBV 脑血容量", "imaging_metric", 1, 1, "脑血容量。", "反映代偿,CBV 明显下降提示不可逆损伤。", ["metric_cbv"]),
            _cn("pf_tmax", "Tmax 达峰时间", "imaging_metric", 1, 2, "残余功能达峰时间。", "Tmax>6s 常用于界定低灌注/半暗带。", ["metric_tmax"]),
            _cn("pf_core", "核心梗死区", "imaging_metric", 2, 0, "不可逆缺血核心。", "核心越大出血风险越高,获益越谨慎。", ["metric_core"]),
            _cn("pf_penumbra", "半暗带", "imaging_metric", 2, 1, "可挽救低灌注组织。", "半暗带越大及时再通潜在获益越明确。", ["metric_penumbra"]),
            _cn("pf_mismatch", "不匹配比值", "imaging_metric", 3, 0, "低灌注与核心之比。", "显著 mismatch 支持存在可挽救组织。", ["metric_mismatch"]),
            _cn("pf_evt", "再通决策", "treatment", 4, 0, "溶栓/取栓获益评估。", "结合核心体积与 mismatch 判断再通获益。", ["treatment_evt"]),
        ],
        "edges": [
            ("pf_ctp", "pf_cbf", "measures", "测量 CBF", 0.92),
            ("pf_ctp", "pf_cbv", "measures", "测量 CBV", 0.9),
            ("pf_ctp", "pf_tmax", "measures", "测量 Tmax", 0.92),
            ("pf_cbf", "pf_core", "supports", "界定核心", 0.9),
            ("pf_cbv", "pf_core", "supports", "界定核心", 0.82),
            ("pf_tmax", "pf_penumbra", "supports", "界定低灌注", 0.9),
            ("pf_core", "pf_mismatch", "supports", "计算不匹配", 0.86),
            ("pf_penumbra", "pf_mismatch", "supports", "计算不匹配", 0.9),
            ("pf_mismatch", "pf_evt", "supports", "再通获益", 0.9),
            ("pf_core", "pf_evt", "risk_modifier", "核心过大风险", 0.76),
        ],
    },
    {
        "id": "risk_contra",
        "label": "风险禁忌图谱",
        "icon": "⚠️",
        "description": "出血、抗凝、时间窗、血糖、血压、既往病史等风险与禁忌。",
        "focus": ["出血", "抗凝", "时间窗", "血糖", "血压", "既往病史"],
        "columns": ["患者评估", "风险因素", "治疗禁忌/风险"],
        "nodes": [
            _cn("rc_patient", "患者综合评估", "concept", 0, 0, "溶栓/取栓前的风险排查。", "再通治疗前需快速完成禁忌证与风险评估。", ["concept_ais"]),
            _cn("rc_hemorrhage", "出血风险", "risk", 1, 0, "活动性出血/出血转化风险。", "颅内出血为溶栓绝对禁忌。", ["risk_hemorrhage"]),
            _cn("rc_anticoag", "抗凝状态", "risk", 1, 1, "口服抗凝药/INR。", "抗凝达治疗量常为溶栓禁忌。", ["risk_anticoagulation"]),
            _cn("rc_time", "时间窗", "criterion", 1, 2, "发病至治疗时间。", "超窗需依赖影像筛选,超过上限限制再通。", ["criterion_time_window"]),
            _cn("rc_glucose", "血糖", "risk", 1, 3, "血糖异常。", "极端高/低血糖需纠正,低血糖可类卒中表现。", ["risk_glucose"]),
            _cn("rc_bp", "血压", "risk", 1, 4, "血压控制。", "溶栓前需将血压控制在阈值以下。", ["risk_blood_pressure"]),
            _cn("rc_history", "既往病史", "risk", 1, 5, "近期手术/出血/卒中史。", "影响溶栓禁忌与出血风险评估。", ["risk_history"]),
            _cn("rc_ivt", "静脉溶栓", "treatment", 2, 0, "溶栓适应证/禁忌判断。", "多项风险因素直接构成溶栓禁忌。", ["treatment_ivt"]),
            _cn("rc_evt", "机械取栓", "treatment", 2, 1, "取栓围术期风险。", "风险因素多为相对禁忌,影响围术期管理。", ["treatment_evt"]),
        ],
        "edges": [
            ("rc_patient", "rc_hemorrhage", "assessed_by", "评估出血", 0.9),
            ("rc_patient", "rc_anticoag", "assessed_by", "评估抗凝", 0.86),
            ("rc_patient", "rc_time", "assessed_by", "评估时间", 0.9),
            ("rc_patient", "rc_glucose", "assessed_by", "评估血糖", 0.8),
            ("rc_patient", "rc_bp", "assessed_by", "评估血压", 0.82),
            ("rc_patient", "rc_history", "assessed_by", "评估病史", 0.82),
            ("rc_hemorrhage", "rc_ivt", "contraindicates", "绝对禁忌", 0.94),
            ("rc_anticoag", "rc_ivt", "contraindicates", "限制溶栓", 0.86),
            ("rc_time", "rc_ivt", "contraindicates", "超窗限制", 0.84),
            ("rc_bp", "rc_ivt", "risk_modifier", "血压阈值", 0.78),
            ("rc_glucose", "rc_ivt", "risk_modifier", "需先纠正", 0.7),
            ("rc_history", "rc_ivt", "contraindicates", "近期手术/出血", 0.8),
            ("rc_hemorrhage", "rc_evt", "risk_modifier", "围术期风险", 0.76),
            ("rc_time", "rc_evt", "contraindicates", "超窗限制", 0.78),
            ("rc_anticoag", "rc_evt", "risk_modifier", "围术期风险", 0.66),
        ],
    },
    {
        "id": "case_experience",
        "label": "病例经验图谱",
        "icon": "🗂️",
        "description": "历史病例、医生反馈与相似病例检索的经验支持。",
        "focus": ["历史病例", "医生反馈", "相似病例检索"],
        "columns": ["本例", "经验来源", "经验加工", "决策支持"],
        "nodes": [
            _cn("ce_current", "本轮病例", "concept", 0, 0, "当前患者的影像与临床特征。", "作为相似病例检索与经验匹配的查询锚点。", ["concept_ais"]),
            _cn("ce_similar", "相似病例检索", "case", 1, 0, "按影像/临床特征检索相似历史病例。", "为当前决策提供可比参照与转归预期。", ["case_similar"]),
            _cn("ce_history", "历史病例库", "case", 1, 1, "既往诊疗病例与随访结果。", "沉淀真实世界证据,补充指南之外的经验。", ["case_history"]),
            _cn("ce_feedback", "医生反馈", "case", 2, 0, "专家对既往决策的复盘反馈。", "校正模型倾向,强化可信决策路径。", ["case_feedback"]),
            _cn("ce_outcome", "转归经验", "imaging_metric", 2, 1, "相似病例的治疗与转归。", "评估不同再通策略的经验获益与风险。", ["case_history"]),
            _cn("ce_decision", "经验支持决策", "treatment", 3, 0, "融合经验的再通治疗建议。", "将相似病例与反馈整合进当前治疗建议。", ["treatment_evt", "treatment_ivt"]),
        ],
        "edges": [
            ("ce_current", "ce_similar", "assessed_by", "特征检索", 0.88),
            ("ce_similar", "ce_history", "related_to", "命中病例库", 0.86),
            ("ce_history", "ce_feedback", "supports", "专家复盘", 0.78),
            ("ce_history", "ce_outcome", "supports", "转归统计", 0.8),
            ("ce_feedback", "ce_decision", "supports", "校正决策", 0.8),
            ("ce_outcome", "ce_decision", "supports", "经验获益", 0.82),
            ("ce_current", "ce_decision", "related_to", "个体化建议", 0.7),
        ],
    },
]


CATEGORY_INDEX: Dict[str, Dict[str, Any]] = {str(cat["id"]): cat for cat in CATEGORY_GRAPHS}
DEFAULT_CATEGORY = "guideline"


def _now_ts() -> int:
    return int(time.time())


def _normalize_text(text: str) -> str:
    value = str(text or "").lower()
    value = value.replace("\u3000", " ") # AI辅助生成：GLM-5, 2026-04-14
    return re.sub(r"\s+", " ", value).strip()


def _node(node_id: str, label: str, node_type: str, **extra: Any) -> Dict[str, Any]:
    payload = {"id": node_id, "label": label, "type": node_type}
    payload.update({k: v for k, v in extra.items() if v is not None}) # AI辅助生成：GLM-5, 2026-04-15
    return payload


def _edge(source: str, target: str, edge_type: str, label: str = "", weight: float = 1.0, **extra: Any) -> Dict[str, Any]:
    payload = {
        "id": f"edge_{uuid.uuid5(uuid.NAMESPACE_URL, source + '|' + target + '|' + edge_type)}",
        "source": source,
        "target": target,
        "type": edge_type,
        "label": label or edge_type,
        "weight": round(float(weight), 4),
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload # AI辅助生成：GLM-5, 2026-04-16


def _concept_terms() -> Dict[str, List[str]]:
    return {
        item["id"]: [_normalize_text(x) for x in item.get("aliases", []) if str(x or "").strip()]
        for item in CONCEPTS
    }


def match_concepts(text: str) -> List[str]:
    norm = _normalize_text(text)
    if not norm:
        return [] # AI辅助生成：GLM-5, 2026-04-17
    matched: List[str] = []
    for concept_id, terms in _concept_terms().items():
        if any(term and term in norm for term in terms):
            matched.append(concept_id)
    return matched # AI辅助生成：GLM-5, 2026-04-18


def _chunk_source_ref(chunk: Any) -> str:
    return f"{chunk.doc_name}#page={chunk.page}&source={chunk.source_bucket}"


def _best_chunks_for_graph(chunks: Sequence[Any], max_chunks: int = 90) -> List[Tuple[Any, List[str], float]]:
    candidates: List[Tuple[Any, List[str], float]] = []
    for chunk in chunks:
        concept_ids = match_concepts(getattr(chunk, "norm_text", "") or getattr(chunk, "text", ""))
        if not concept_ids:
            continue # AI辅助生成：GLM-5, 2026-04-19
        score = len(concept_ids) * float(getattr(chunk, "confidence_score", 0.58) or 0.58)
        score += 0.15 if getattr(chunk, "confidence_grade", "C") in ("S", "A") else 0.0
        candidates.append((chunk, concept_ids, score)) # AI辅助生成：GLM-5, 2026-04-20
    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates[: max(1, int(max_chunks))]


def build_graph_from_chunks(chunks: Sequence[Any], max_chunks: int = 90) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {} # AI辅助生成：GLM-5, 2026-04-21
    edges: Dict[str, Dict[str, Any]] = {}
    evidence: List[Dict[str, Any]] = []

    for concept in CONCEPTS:
        label = concept.get("name_cn") or concept.get("label") # AI辅助生成：GLM-5, 2026-04-22
        nodes[concept["id"]] = _node(
            concept["id"],
            label,
            concept.get("type", "concept"),
            label_en=concept.get("label"),
            aliases=concept.get("aliases", []),
        )

    for source, target, edge_type, label, weight in STATIC_EDGES:
        e = _edge(source, target, edge_type, label, weight, source_type="curated")
        edges[e["id"]] = e

    best_chunks = _best_chunks_for_graph(chunks, max_chunks=max_chunks) # AI辅助生成：GLM-5, 2026-04-23
    doc_refs: Dict[str, Dict[str, Any]] = {}
    concept_evidence_count: Dict[str, int] = defaultdict(int)

    for chunk, concept_ids, score in best_chunks:
        doc_id = f"doc_{getattr(chunk, 'source_bucket', 'kb')}_{re.sub(r'[^a-zA-Z0-9_]+', '_', getattr(chunk, 'doc_name', 'document')).strip('_')}" # AI辅助生成：GLM-5, 2026-03-01
        if doc_id not in nodes:
            nodes[doc_id] = _node(
                doc_id,
                getattr(chunk, "doc_name", "guideline"),
                "guideline_doc",
                source_bucket=getattr(chunk, "source_bucket", "kb"),
                confidence_grade=getattr(chunk, "confidence_grade", "C"),
                confidence_score=float(getattr(chunk, "confidence_score", 0.58) or 0.58),
            )
        doc_refs[doc_id] = nodes[doc_id]

        chunk_id = f"chunk_{getattr(chunk, 'evidence_id', str(uuid.uuid4()))}"
        snippet = str(getattr(chunk, "text", "") or "").strip() # AI辅助生成：GLM-5, 2026-03-02
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        nodes[chunk_id] = _node(
            chunk_id,
            f"{getattr(chunk, 'doc_name', 'guideline')} p.{getattr(chunk, 'page', '-')}",
            "evidence_chunk",
            snippet=snippet,
            source_ref=_chunk_source_ref(chunk),
            doc_name=getattr(chunk, "doc_name", ""),
            page=getattr(chunk, "page", None),
            source_bucket=getattr(chunk, "source_bucket", "kb"),
            confidence_grade=getattr(chunk, "confidence_grade", "C"),
            confidence_score=float(getattr(chunk, "confidence_score", 0.58) or 0.58),
            retrieval_score=round(float(score), 4),
        )

        cite = _edge(chunk_id, doc_id, "cites", "cites", 1.0, source_type="pdf_chunk")
        edges[cite["id"]] = cite # AI辅助生成：GLM-5, 2026-03-03

        evidence.append(
            {
                "evidence_id": getattr(chunk, "evidence_id", chunk_id),
                "node_id": chunk_id,
                "source_ref": _chunk_source_ref(chunk),
                "doc_name": getattr(chunk, "doc_name", ""),
                "page": getattr(chunk, "page", None),
                "snippet": snippet,
                "concept_ids": concept_ids,
                "confidence_grade": getattr(chunk, "confidence_grade", "C"),
                "confidence_score": float(getattr(chunk, "confidence_score", 0.58) or 0.58),
            }
        )

        for concept_id in concept_ids:
            concept_evidence_count[concept_id] += 1
            e = _edge(
                chunk_id,
                concept_id,
                "supports",
                "supports",
                min(1.0, 0.55 + float(getattr(chunk, "confidence_score", 0.58) or 0.58) * 0.4),
                evidence_ids=[getattr(chunk, "evidence_id", chunk_id)],
                source_ref=_chunk_source_ref(chunk),
                source_type="pdf_chunk",
            )
            edges[e["id"]] = e

        for idx, source in enumerate(concept_ids):
            for target in concept_ids[idx + 1 :]:
                e = _edge(
                    source,
                    target,
                    "related_to",
                    "co-mentioned",
                    0.45,
                    source_type="cooccurrence",
                    evidence_ids=[getattr(chunk, "evidence_id", chunk_id)],
                )
                if e["id"] not in edges:
                    edges[e["id"]] = e # AI辅助生成：GLM-5, 2026-03-04

    for concept_id, count in concept_evidence_count.items():
        if concept_id in nodes:
            nodes[concept_id]["evidence_count"] = count

    graph_nodes = list(nodes.values())
    graph_edges = list(edges.values()) # AI辅助生成：GLM-5, 2026-03-05
    stats = {
        "version": GRAPH_VERSION,
        "node_count": len(graph_nodes),
        "edge_count": len(graph_edges),
        "evidence_count": len(evidence),
        "doc_count": len(doc_refs),
        "built_at": _now_ts(),
    }
    return {"version": GRAPH_VERSION, "nodes": graph_nodes, "edges": graph_edges, "evidence": evidence, "stats": stats}


def _load_index_chunks(force_rebuild: bool = False) -> Sequence[Any]:
    try:
        from .ekv_retrieval import _ensure_index
    except ImportError:
        from ekv_retrieval import _ensure_index
    chunks, _idf = _ensure_index(force_rebuild=force_rebuild)
    return chunks # AI辅助生成：GLM-5, 2026-03-06


def _graph_path() -> str:
    return os.environ.get("STROKE_KG_PATH", DEFAULT_GRAPH_PATH)


def save_graph(graph: Dict[str, Any], path: str = "") -> None:
    target = path or _graph_path()
    os.makedirs(os.path.dirname(target), exist_ok=True) # AI辅助生成：GLM-5, 2026-03-07
    with open(target, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)


def load_graph(force_rebuild: bool = False) -> Dict[str, Any]:
    path = _graph_path()
    if not force_rebuild and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                graph = json.load(f) # AI辅助生成：GLM-5, 2026-03-08
            if graph.get("version") == GRAPH_VERSION:
                return graph
        except Exception:
            pass
    chunks = _load_index_chunks(force_rebuild=force_rebuild) # AI辅助生成：GLM-5, 2026-03-09
    graph = build_graph_from_chunks(chunks)
    save_graph(graph, path)
    return graph # AI辅助生成：GLM-5, 2026-03-10


def _evidence_for_concepts(
    graph: Dict[str, Any],
    concept_ids: Sequence[str],
    limit: int = 4,
) -> List[Dict[str, Any]]:
    concept_set = {str(item) for item in concept_ids if str(item or "").strip()}
    if not concept_set:
        return [] # AI辅助生成：GLM-5, 2026-03-11
    selected = []
    seen = set()
    for item in graph.get("evidence") or []:
        item_concepts = {str(x) for x in item.get("concept_ids") or []} # AI辅助生成：GLM-5, 2026-03-12
        if not (item_concepts & concept_set):
            continue
        evidence_id = str(item.get("evidence_id") or item.get("source_ref") or "")
        if evidence_id and evidence_id in seen:
            continue # AI辅助生成：GLM-5, 2026-03-13
        if evidence_id:
            seen.add(evidence_id)
        selected.append(
            {
                "evidence_id": item.get("evidence_id"),
                "source_ref": item.get("source_ref"),
                "doc_name": item.get("doc_name"),
                "page": item.get("page"),
                "snippet": item.get("snippet"),
                "concept_ids": item.get("concept_ids") or [],
                "confidence_grade": item.get("confidence_grade") or "C",
                "confidence_score": float(item.get("confidence_score") or 0.58),
            }
        )
    selected.sort(key=lambda x: float(x.get("confidence_score") or 0), reverse=True)
    return selected[: max(1, int(limit))] # AI辅助生成：GLM-5, 2026-03-14


def _best_grade(evidence_items: Sequence[Dict[str, Any]]) -> Tuple[str, float]:
    grade_rank = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
    best_grade = "C"
    best_score = 0.58 # AI辅助生成：GLM-5, 2026-03-15
    for item in evidence_items:
        grade = str(item.get("confidence_grade") or "C").upper()
        score = float(item.get("confidence_score") or 0.58)
        if grade_rank.get(grade, 0) > grade_rank.get(best_grade, 0) or (
            grade == best_grade and score > best_score # AI辅助生成：GLM-5, 2026-03-16
        ):
            best_grade = grade
            best_score = score # AI辅助生成：GLM-5, 2026-03-17
    return best_grade, round(float(best_score), 4)


def _clinical_seed_ids(query: str) -> Set[str]:
    matched_concepts = set(match_concepts(query))
    if not matched_concepts:
        return set() # AI辅助生成：GLM-5, 2026-03-18
    seeds = set()
    for node in CLINICAL_GRAPH_NODES:
        concept_ids = {str(x) for x in node.get("concept_ids") or []}
        if concept_ids & matched_concepts:
            seeds.add(str(node.get("id"))) # AI辅助生成：GLM-5, 2026-03-19
    return seeds


def _clinical_neighbors(seed_ids: Set[str], depth: int = 1) -> Set[str]:
    selected = set(seed_ids)
    frontier = set(seed_ids) # AI辅助生成：GLM-5, 2026-03-20
    for _ in range(max(0, int(depth))):
        next_frontier = set()
        for source, target, _edge_type, _label, _weight in CLINICAL_GRAPH_EDGES:
            if source in frontier:
                next_frontier.add(target)
            if target in frontier:
                next_frontier.add(source) # AI辅助生成：GLM-5, 2026-03-21
        next_frontier -= selected
        selected |= next_frontier
        frontier = next_frontier # AI辅助生成：GLM-5, 2026-03-22
        if not frontier:
            break
    return selected


def clinical_graph_view(query: str = "", depth: int = 1) -> Dict[str, Any]:
    """Return the doctor-facing clinical decision graph projection.

    The full graph keeps evidence chunks for retrieval. This projection keeps the
    visible canvas small and pushes evidence snippets into node details.
    """
    full_graph = load_graph(force_rebuild=False) # AI辅助生成：GLM-5, 2026-03-23
    seed_ids = _clinical_seed_ids(query)
    if seed_ids:
        selected_ids = _clinical_neighbors(seed_ids, depth=depth)
        selected_ids.add("concept_ais") # AI辅助生成：GLM-5, 2026-03-24
    else:
        selected_ids = {str(node.get("id")) for node in CLINICAL_GRAPH_NODES}

    nodes = []
    all_evidence = [] # AI辅助生成：GLM-5, 2026-03-25
    seen_evidence = set()
    for item in CLINICAL_GRAPH_NODES:
        node_id = str(item.get("id"))
        if node_id not in selected_ids:
            continue # AI辅助生成：GLM-5, 2026-03-26
        top_evidence = _evidence_for_concepts(
            full_graph,
            item.get("concept_ids") or [node_id],
            limit=4,
        )
        grade, score = _best_grade(top_evidence)
        node = dict(item)
        node["evidence_count"] = len(top_evidence) # AI辅助生成：GLM-5, 2026-03-27
        node["top_evidence"] = top_evidence
        node["confidence_grade"] = grade
        node["confidence_score"] = score # AI辅助生成：GLM-5, 2026-03-28
        nodes.append(node)
        for evidence_item in top_evidence:
            evidence_id = str(evidence_item.get("evidence_id") or evidence_item.get("source_ref") or "")
            if evidence_id and evidence_id in seen_evidence:
                continue # AI辅助生成：GLM-5, 2026-03-29
            if evidence_id:
                seen_evidence.add(evidence_id)
            all_evidence.append(evidence_item)

    node_ids = {str(node.get("id")) for node in nodes} # AI辅助生成：GLM-5, 2026-03-30
    edges = []
    for source, target, edge_type, label, weight in CLINICAL_GRAPH_EDGES:
        if source not in node_ids or target not in node_ids:
            continue
        edges.append(
            _edge(
                source,
                target,
                edge_type,
                label,
                weight,
                source_type="clinical_projection",
            )
        )

    nodes.sort(key=lambda n: (int(n.get("column") or 0), int(n.get("order") or 0), str(n.get("label") or ""))) # AI辅助生成：GLM-5, 2026-03-31
    stats = {
        **(full_graph.get("stats") or {}),
        "view": "clinical",
        "subgraph_node_count": len(nodes),
        "subgraph_edge_count": len(edges),
        "seed_ids": sorted(seed_ids),
        "full_node_count": len(full_graph.get("nodes") or []),
        "full_edge_count": len(full_graph.get("edges") or []),
    }
    return {
        "version": full_graph.get("version") or GRAPH_VERSION,
        "view": "clinical",
        "nodes": nodes,
        "edges": edges,
        "evidence": all_evidence,
        "stats": stats,
    }


def _relevant_concepts(task_text: str) -> Set[str]:
    """Concepts inferred from the current task/run context text."""
    return set(match_concepts(task_text or ""))


def _category_neighbors(edges: Sequence[Tuple[str, str, str, str, float]], seed_ids: Set[str], depth: int = 1) -> Set[str]:
    selected = set(seed_ids)
    frontier = set(seed_ids)
    for _ in range(max(0, int(depth))):
        next_frontier: Set[str] = set()
        for source, target, _t, _l, _w in edges:
            if source in frontier:
                next_frontier.add(target)
            if target in frontier:
                next_frontier.add(source)
        next_frontier -= selected
        selected |= next_frontier
        frontier = next_frontier
        if not frontier:
            break
    return selected


def _category_node_relevance(node: Dict[str, Any], relevant_concepts: Set[str]) -> bool:
    if not relevant_concepts:
        return False
    node_concepts = {str(x) for x in node.get("concept_ids") or []}
    return bool(node_concepts & relevant_concepts)


def list_categories(task: str = "") -> List[Dict[str, Any]]:
    """Return metadata for every knowledge-graph category.

    When ``task`` (current run context) is provided, each category also reports
    how strongly it relates to the current case so the UI can surface the most
    relevant chapters first.
    """
    relevant = _relevant_concepts(task)
    out: List[Dict[str, Any]] = []
    for cat in CATEGORY_GRAPHS:
        nodes = cat.get("nodes") or []
        matched_nodes = [n for n in nodes if _category_node_relevance(n, relevant)]
        matched_labels = [str(n.get("label")) for n in matched_nodes]
        relevance_score = round(len(matched_nodes) / max(1, len(nodes)), 4) if relevant else 0.0
        out.append(
            {
                "id": cat["id"],
                "label": cat["label"],
                "icon": cat.get("icon", ""),
                "description": cat.get("description", ""),
                "focus": cat.get("focus", []),
                "node_count": len(nodes),
                "edge_count": len(cat.get("edges") or []),
                "relevant_count": len(matched_nodes),
                "matched_labels": matched_labels,
                "relevance": relevance_score,
            }
        )
    if relevant:
        out.sort(key=lambda c: (c["relevance"], c["relevant_count"]), reverse=True)
    return out


def category_graph_view(category: str = "", query: str = "", task: str = "", depth: int = 1) -> Dict[str, Any]:
    """Project a single category sub-graph, attaching evidence and task relevance.

    - ``query`` focuses the canvas on a searched neighborhood.
    - ``task`` marks nodes/edges relevant to the current run so the UI can
      highlight the chapters that matter for this case.
    """
    category_id = str(category or DEFAULT_CATEGORY).strip().lower()
    cat = CATEGORY_INDEX.get(category_id) or CATEGORY_INDEX[DEFAULT_CATEGORY]
    category_id = str(cat["id"])

    full_graph = load_graph(force_rebuild=False)
    all_nodes = cat.get("nodes") or []
    all_edges = cat.get("edges") or []
    node_index = {str(n.get("id")): n for n in all_nodes}

    # Query focusing: seed by concept match on node concept_ids, expand neighbors.
    query_concepts = set(match_concepts(query)) if str(query or "").strip() else set()
    if query_concepts:
        seed_ids = {
            str(n.get("id"))
            for n in all_nodes
            if {str(x) for x in n.get("concept_ids") or []} & query_concepts
        }
        if seed_ids:
            selected_ids = _category_neighbors(all_edges, seed_ids, depth=depth)
        else:
            selected_ids = {str(n.get("id")) for n in all_nodes}
    else:
        seed_ids = set()
        selected_ids = {str(n.get("id")) for n in all_nodes}

    relevant_concepts = _relevant_concepts(task)

    nodes: List[Dict[str, Any]] = []
    all_evidence: List[Dict[str, Any]] = []
    seen_evidence: Set[str] = set()
    for item in all_nodes:
        node_id = str(item.get("id"))
        if node_id not in selected_ids:
            continue
        top_evidence = _evidence_for_concepts(full_graph, item.get("concept_ids") or [node_id], limit=4)
        grade, score = _best_grade(top_evidence)
        node = dict(item)
        node["evidence_count"] = len(top_evidence)
        node["top_evidence"] = top_evidence
        node["confidence_grade"] = grade
        node["confidence_score"] = score
        node["relevant"] = _category_node_relevance(item, relevant_concepts)
        nodes.append(node)
        for evidence_item in top_evidence:
            evidence_id = str(evidence_item.get("evidence_id") or evidence_item.get("source_ref") or "")
            if evidence_id and evidence_id in seen_evidence:
                continue
            if evidence_id:
                seen_evidence.add(evidence_id)
            all_evidence.append(evidence_item)

    node_ids = {str(n.get("id")) for n in nodes}
    relevant_node_ids = {str(n.get("id")) for n in nodes if n.get("relevant")}
    edges = []
    for source, target, edge_type, label, weight in all_edges:
        if source not in node_ids or target not in node_ids:
            continue
        edge = _edge(source, target, edge_type, label, weight, source_type="category_projection")
        edge["relevant"] = source in relevant_node_ids and target in relevant_node_ids
        edges.append(edge)

    nodes.sort(key=lambda n: (int(n.get("column") or 0), int(n.get("order") or 0), str(n.get("label") or "")))
    stats = {
        **(full_graph.get("stats") or {}),
        "view": "category",
        "category": category_id,
        "subgraph_node_count": len(nodes),
        "subgraph_edge_count": len(edges),
        "relevant_node_count": len(relevant_node_ids),
        "seed_ids": sorted(seed_ids),
        "full_node_count": len(full_graph.get("nodes") or []),
        "full_edge_count": len(full_graph.get("edges") or []),
    }
    return {
        "version": full_graph.get("version") or GRAPH_VERSION,
        "view": "category",
        "category": category_id,
        "category_label": cat.get("label"),
        "category_description": cat.get("description"),
        "columns": cat.get("columns") or [],
        "nodes": nodes,
        "edges": edges,
        "evidence": all_evidence,
        "stats": stats,
    }


def _neighbors(graph: Dict[str, Any], seed_ids: Iterable[str], depth: int = 1) -> Set[str]:
    selected: Set[str] = set(seed_ids)
    frontier: Set[str] = set(seed_ids)
    edges = graph.get("edges") or [] # AI辅助生成：GLM-5, 2026-04-01
    for _ in range(max(0, int(depth))):
        next_frontier: Set[str] = set()
        for edge in edges:
            src = str(edge.get("source") or "")
            dst = str(edge.get("target") or "") # AI辅助生成：GLM-5, 2026-04-02
            if src in frontier and dst:
                next_frontier.add(dst)
            if dst in frontier and src:
                next_frontier.add(src)
        next_frontier -= selected # AI辅助生成：GLM-5, 2026-04-03
        selected |= next_frontier
        frontier = next_frontier
        if not frontier:
            break
    return selected


def subgraph_for_query(query: str, seed_evidence: Sequence[Dict[str, Any]] = (), depth: int = 1, limit: int = 60) -> Dict[str, Any]:
    graph = load_graph()
    node_by_id = {str(node.get("id")): node for node in graph.get("nodes") or []}
    seed_ids: Set[str] = set(match_concepts(query))

    seed_refs = {str(item.get("source_ref") or "") for item in seed_evidence or [] if item.get("source_ref")}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        if node.get("type") == "evidence_chunk" and str(node.get("source_ref") or "") in seed_refs:
            seed_ids.add(node_id)
            for concept_id in match_concepts(str(node.get("snippet") or "")):
                seed_ids.add(concept_id)

    if not seed_ids:
        seed_ids = {"concept_ais", "modality_ctp", "treatment_evt"}

    selected = _neighbors(graph, seed_ids, depth=depth)
    priority = {"concept": 1, "imaging_metric": 1, "criterion": 1, "treatment": 1, "guideline_doc": 2, "evidence_chunk": 3}
    ordered_nodes = sorted(
        [node_by_id[nid] for nid in selected if nid in node_by_id],
        key=lambda n: (priority.get(str(n.get("type")), 9), str(n.get("label") or "")),
    )[: max(1, int(limit))]
    selected = {str(node.get("id")) for node in ordered_nodes}
    selected_edges = [
        edge
        for edge in graph.get("edges") or []
        if str(edge.get("source") or "") in selected and str(edge.get("target") or "") in selected
    ]
    selected_evidence = [
        ev for ev in graph.get("evidence") or [] if str(ev.get("node_id") or "") in selected
    ]
    return {
        "nodes": ordered_nodes,
        "edges": selected_edges,
        "evidence": selected_evidence,
        "stats": {
            **(graph.get("stats") or {}),
            "subgraph_node_count": len(ordered_nodes),
            "subgraph_edge_count": len(selected_edges),
            "seed_ids": sorted(seed_ids),
        },
    }


def graph_paths_for_query(query: str, seed_evidence: Sequence[Dict[str, Any]] = (), max_paths: int = 8) -> List[Dict[str, Any]]:
    sub = subgraph_for_query(query, seed_evidence=seed_evidence, depth=1, limit=70)
    node_by_id = {str(node.get("id")): node for node in sub.get("nodes") or []}
    paths: List[Dict[str, Any]] = []
    for edge in sub.get("edges") or []:
        src = node_by_id.get(str(edge.get("source") or ""))
        dst = node_by_id.get(str(edge.get("target") or ""))
        if not src or not dst:
            continue
        if src.get("type") == "evidence_chunk" and dst.get("type") == "guideline_doc":
            continue
        paths.append(
            {
                "source": src.get("label"),
                "source_type": src.get("type"),
                "relation": edge.get("label") or edge.get("type"),
                "target": dst.get("label"),
                "target_type": dst.get("type"),
                "weight": edge.get("weight"),
                "source_ref": edge.get("source_ref") or src.get("source_ref") or dst.get("source_ref"),
                "evidence_ids": edge.get("evidence_ids") or [],
            }
        )
    paths.sort(key=lambda item: float(item.get("weight") or 0), reverse=True)
    return paths[: max(1, int(max_paths))]
