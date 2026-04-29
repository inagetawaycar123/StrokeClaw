# StrokeClaw — 卒中先锋智能影像诊断平台

## 项目简介
**StrokeClaw** 是一款面向急性缺血性脑卒中首诊场景的专病智能体辅助决策系统。项目主要服务于基层医院和区域卒中协作场景，在 NCCT、CTA、mCTA、CTP 等影像条件不完全一致的情况下，将安全分诊、血管闭塞风险识别、类 CTP 灌注评估、卒中量化分析、指南知识校验、结构化报告生成与医生复核组织成一条可规划、可执行、可追踪、可复核的临床辅助决策链。

StrokeClaw 不是单一影像分类工具，也不是普通医学问答系统。它的核心目标是把医学影像算法真正嵌入急性缺血性脑卒中首诊流程，并通过 DAG 编排、Skill Registry、多 Agent 协同、分级知识库、证据追溯和医生反馈闭环，使系统输出具备临床可解释性、工程可审计性和后续可迭代性。

典型链路：

```text
病例输入
-> 模态识别与图像质控
-> NCCT 三分类安全分诊
-> 血管闭塞三分类风险识别
-> MRDPM 类 CTP 生成
-> 卒中自动分析
-> 指南知识校验与一致性检查
-> 结构化报告生成
-> 医生复核与反馈归档
```

## 临床价值
### 面向基层真实首诊场景
急性缺血性脑卒中高度依赖时间窗。首诊医生需要在有限时间内综合判断患者是否存在出血风险、早期缺血改变、大血管或中等血管闭塞、可挽救脑组织，以及是否需要进入溶栓、取栓、远程会诊或上转流程。

基层医院常具备 NCCT、CTA 或 mCTA 等基础影像条件，但不一定具备完整 CTP 检查能力；同时，NCCT 早期缺血征象可能不明显，血管闭塞和灌注状态判断也高度依赖经验。StrokeClaw 面向的正是“有影像、无完整 CTP、缺少稳定专科辅助”的真实断点，帮助基层在现有影像条件下获得更完整、更标准化、更可追溯的辅助判断。

### 服务关键临床问题
- **出血安全排查**：NCCT 三分类优先识别正常、出血、缺血，作为系统进入缺血性卒中分析路径前的安全入口。
- **闭塞风险识别**：血管闭塞三分类识别正常、大血管闭塞和中等血管闭塞，辅助判断 LVO / MeVO 高危风险。
- **无 CTP 场景补足灌注评估**：MRDPM 基于 NCCT 和多期 CTA/mCTA 生成 CBF、CBV、Tmax 等类 CTP 图，为基层无真实 CTP 场景提供灌注层面辅助信息。
- **上转与会诊支持**：系统输出闭塞风险、灌注异常、半暗带提示、关键证据和结构化摘要，便于远程会诊和上级医院复核。
- **医生复核闭环**：系统结论不替代医生最终诊断，关键节点支持确认、修改、驳回和反馈归档。

### 安全边界
- 系统结论仅用于教学、科研、工程验证和临床辅助决策参考。
- 最终诊断与治疗方案必须由具备资质的临床医生结合完整影像、病史、查体、实验室检查和院内流程确认。
- 对疑似出血、结果冲突、置信度不足或指南禁忌证冲突的场景，系统应触发人工复核或降低结论强度。

## 算法价值
StrokeClaw 的算法价值不在于简单堆叠多个模型，而在于形成一条符合卒中首诊逻辑的四级算法链：

| 层级 | 算法模块 | 临床作用 |
|---|---|---|
| 1 | NCCT 三分类 | 首诊安全分诊，优先识别出血风险与缺血倾向 |
| 2 | 血管闭塞三分类 | 识别正常、大血管闭塞、中等血管闭塞，支持 LVO / MeVO 风险判断 |
| 3 | MRDPM 类 CTP 生成 | 在无真实 CTP 条件下生成 CBF、CBV、Tmax，补足灌注评估信息 |
| 4 | 卒中自动分析 | 输出梗死核心、缺血半暗带、mismatch ratio、受累侧别和风险等级 |

### 关键量化指标
- `core_infarct_volume`：核心梗死体积
- `penumbra_volume`：缺血半暗带体积
- `mismatch_ratio`：灌注-核心不匹配比值
- `occlusion_risk`：血管闭塞风险分层
- `risk_level`：综合风险等级

这些指标会进入结构化报告、风险提示、证据追溯和医生复核流程，形成“影像输入 -> 模型结果 -> 量化指标 -> 医学解释 -> 医生确认”的闭环。

### 阶段性模型结果
以下指标来自项目阶段性整理材料，用于说明当前算法底座的可验证基础，后续仍需更大规模、多中心、多设备数据继续验证。

| 模块 | 阶段性结果 |
|---|---|
| NCCT 三分类 | Accuracy 93.55%，Macro F1 91.83%；正常类召回率 100%，缺血类召回率超过 98%，出血类精确率 95.99%，出血类召回率 71.22% |
| 血管闭塞三分类 | Accuracy 80.00%，Macro F1 0.81，Balanced Accuracy 80%，ROC-AUC 0.90，MCC 0.69，Cohen's Kappa 0.69 |
| MRDPM 类 CTP | 相关判别评估 AUC = 0.867，说明生成图像在后续病理判别链条中保留了一定有效信息 |

## 工程价值
### 从固定 pipeline 到 DAG 专病智能体
传统医学 AI 工具常见流程是“上传影像 -> 模型推理 -> 输出报告”。但卒中首诊病例存在明显条件分支：有的病例只有 NCCT，有的病例有 NCCT + CTA/mCTA，有的病例已有真实 CTP，有的病例疑似出血，有的病例模型结果之间存在冲突。StrokeClaw 使用 DAG 动态任务编排，将不同病例路由到不同执行路径。

典型路径包括：

```text
病例创建
-> 模态识别 Skill
-> 图像质控 Skill
-> NCCT 三分类 Skill
-> 疑似出血？若是，进入出血预警与医生复核路径
-> 存在 CTA/mCTA？若是，调用血管闭塞三分类 Skill
-> 已有真实 CTP？若是，跳过 MRDPM；若否，调用 MRDPM 生成类 CTP
-> 卒中自动分析
-> 指南检索
-> 一致性校验
-> 结构化报告
-> 医生确认、修改或驳回
-> 归档与反馈学习
```

### Skill Registry 与统一协议
系统将核心能力封装为标准化 Skill，而不是写死在单一函数链中。核心 Skills 包括：

- 模态识别 Skill
- 图像质控 Skill
- NCCT 三分类 Skill
- 血管闭塞三分类 Skill
- MRDPM 类 CTP 生成 Skill
- 卒中分析 Skill
- 指南检索 Skill
- 一致性校验 Skill
- 报告生成 Skill
- 医生复核 Skill
- 归档与反馈学习 Skill

每个 Skill 尽量输出统一结构，例如 `skill_name`、`status`、`input_summary`、`output`、`confidence`、`risk_level`、`need_human_review`、`evidence_items`、`start_time`、`end_time`、`error_message`。这样未来替换模型、增加工具或适配不同医院流程时，只需注册新 Skill 并保持输出协议一致，而不需要推翻整体系统。

### 可观测、可审计、可复核
StrokeClaw 通过 `AgentRun` 记录一次完整智能体运行，通过 `NodeRun` 记录每个任务节点，通过 `SkillResult` 记录每个工具输入输出，通过 `EvidenceItem` 记录证据来源，通过日志与反馈记录医生修改过程。

Agent Cockpit 前端用于展示：

- 病例信息与输入模态
- DAG 执行图与节点状态
- 节点详情、模型输出、置信度和风险等级
- 证据面板与指南/知识来源
- 运行日志时间线
- 报告分段审阅与医生确认状态

这使系统不只是“能给结果”，也能解释“结果如何产生、在哪一步产生、有哪些证据、哪里需要人工确认”。

## 核心能力概览
| 模块 | 说明 |
|---|---|
| 多模态输入 | 支持 NCCT、CTA/mCTA、真实 CTP 或由 MRDPM 生成的类 CTP |
| 模态识别与路径决策 | 自动识别可用影像并选择 `ncct_only`、`ncct_mcta`、`ncct_mcta_ctp` 等路径 |
| NCCT 安全分诊 | 判断正常、出血、缺血，作为进入 AIS 深度分析前的安全入口 |
| 血管闭塞识别 | 判断正常、大血管闭塞、中等血管闭塞，辅助 LVO / MeVO 风险识别 |
| 类 CTP 生成 | 在无真实 CTP 场景下生成 CBF、CBV、Tmax 等类灌注图 |
| 卒中自动分析 | 输出 core、penumbra、mismatch、侧别、风险等级等结构化指标 |
| ICV 内部一致性校验 | 检查结论、指标、建议之间是否自相矛盾 |
| EKV 外部证据校验 | 对照指南、SOP、专家共识和知识库证据进行核验 |
| Consensus 冲突裁决 | 对冲突结果进行风险标记、降级表达或请求人工复核 |
| 结构化报告 | 生成可读、可编辑、可追溯的报告草案 |
| 医生反馈闭环 | 支持确认、修改、驳回、归档和难例沉淀 |

## 系统架构
StrokeClaw 采用六层解耦架构：

1. **前端交互层**：病例上传、Agent Cockpit、DAG 执行图、影像查看器、证据面板、报告审阅。
2. **服务与任务管理层**：病例管理、文件上传、Agent Run 管理、任务状态、API 与事件流。
3. **智能体编排层**：Planner、DAG Orchestrator、Executor、RePlanner、Consistency Reviewer、Human Review Controller。
4. **Skills 能力层**：将模型推理、知识检索、报告生成、复核归档等封装为可调用能力。
5. **知识与模型层**：MRDPM、NCCT 三分类、血管闭塞三分类、卒中分析、分级知识库、混合 RAG、规则库。
6. **数据与审计层**：保存 Case、AgentRun、NodeRun、SkillResult、EvidenceItem、ClinicalDecisionBundle、Feedback、Logs。

## 分级知识库与证据校验
医疗智能体不能只依赖普通 RAG，因为“相似文本”不一定权威，也不一定适用于当前病例。StrokeClaw 将知识库设计为分级证据库，并结合语义检索、关键词匹配、权威等级、时效性、场景匹配和冲突惩罚进行综合排序。

| 等级 | 来源示例 | 用途 |
|---|---|---|
| S | 国家/国际指南、诊疗规范 | 最高优先级医学依据 |
| A | 医院 SOP、区域转诊流程 | 本地流程适配 |
| B | 专家共识、教材、综述 | 医学解释与补充说明 |
| C | 脱敏病例、历史报告、医生修改记录 | 案例参考与难例沉淀 |
| D | 模型生成内容、普通问答记录 | 低权重参考，不直接作为强依据 |

## 已落地 API
### Run 与事件
- `POST /api/agent/runs`
- `GET /api/agent/runs/{run_id}`
- `GET /api/agent/runs/{run_id}/events`
- `GET /api/agent/runs/{run_id}/result`

### 计划预览
- `POST /api/agent/plans/preview`

### 报告分段审阅
- `GET /api/agent/runs/{run_id}/review`
- `POST /api/agent/runs/{run_id}/review`

`POST /review` 支持 action：

- `init_review`
- `rewrite_section`
- `save_section`
- `confirm_section`
- `finalize_review`

## 演示与示例数据
- Demo：https://nonmodally-tinkliest-bennie.ngrok-free.dev
- 示例数据：通过网盘分享的文件 `example_NCCT_mCTA`
- 链接：https://pan.baidu.com/s/1-FTBVHpTg18amsuf_QQ0wQ
- 提取码：`cbtu`

说明：示例数据来自百度网盘超级会员 v4 分享文件 `example_NCCT_mCTA`。若 Demo 因 ngrok 会话变更失效，请以本地部署结果为准。

## 快速启动
### 环境要求
- Python：建议与 `.python-version` 对齐
- Node.js + npm
- Windows / Linux 均可

### 配置 `.env`
```bash
cp .env.example .env
```

最小示例：

```env
FLASK_ENV=development
FLASK_DEBUG=1
VITE_API_URL=http://localhost:5011

BAICHUAN_API_URL=https://api.baichuan-ai.com/v1/chat/completions
BAICHUAN_API_KEY=your_key
BAICHUAN_MODEL=Baichuan-M3
```

### 安装依赖并启动后端
```bash
uv sync
uv run python run.py
```

访问：

- `http://127.0.0.1:5011`

### 构建前端
```bash
cd frontend
npm install
npm run build
cd ..
```

构建输出：

- `static/dist/index.html`
- `static/dist/assets/*`

## 模型权重配置
默认 `.gitignore` 不包含大权重文件，请手动补齐。建议按下表放置：

| 模块 | 文件 | 放置路径 | 链接 | 提取码 |
|---|---|---|---|---|
| MedGemma | `model-00001-of-00002.safetensors` | `MedGemma_Model/` | https://pan.baidu.com/s/1G6Ru1CaU3OiqDt5W7OrOUQ | `31k4` |
| MedGemma | `model-00002-of-00002.safetensors` | `MedGemma_Model/` | https://pan.baidu.com/s/1xtl-r96R0f_dvJSFLwUDmw | `vqj8` |
| Palette | CBF/CBV/Tmax 权重 | `palette/weights/cbf`、`palette/weights/cbv`、`palette/weights/tmax` | https://pan.baidu.com/s/1QzYK6Fx-wKtBSB-iVkhXBg | `ynua` |
| MRDPM | CBF/CBV/Tmax 权重 | `mrdpm/weights/cbf`、`mrdpm/weights/cbv`、`mrdpm/weights/tmax` | https://pan.baidu.com/s/1hLgUh_lVA6RDWm4SaMZedg | `ixqm` |
| NCCT 三分类 | `best_model.pt` | `backend/three_class/best_model.pt` | https://pan.baidu.com/s/1pyZbx1pIH3G6DlZkbm1gAg | `bvnv` |
| 血管闭塞三分类 | `dinov3权重.pth` | `dinov3/src/dinov3权重.pth` | https://pan.baidu.com/s/1-l1VILpsuaV2AN0jmDeGcQ | `e59n` |

说明：

- NCCT 三分类权重来自百度网盘超级会员 v4 分享文件 `best_model.pt`。
- 血管闭塞三分类权重来自百度网盘超级会员 v4 分享文件 `dinov3权重.pth`。
- DINOv3 预训练权重仍按代码默认路径放置到 `dinov3/src/ckpt/dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth`。

## 工程复现与最小测试
### 最小复现
```bash
uv sync
cd frontend && npm install && npm run build && cd ..
uv run python run.py
```

### 最小测试
```bash
pytest tests/test_agent_loop_modules.py tests/test_icv.py tests/test_ekv.py
```

## 验收清单
1. API 可用：可成功创建 run 并查询 `/runs`、`/events`、`/result`。
2. 路径可变：不同输入模态可生成不同 DAG 执行路径。
3. 节点可见：Agent Cockpit 可展示节点状态、输入输出、风险等级和日志。
4. 结果可读：报告包含 core、penumbra、mismatch、闭塞风险和对应临床解释。
5. 证据可追溯：关键结论可映射到模型结果、量化指标、指南/知识库证据和医生复核状态。
6. 风险可拦截：疑似出血、结果冲突、指南禁忌证冲突等场景可触发人工复核或风险提示。
7. 反馈可归档：医生确认、修改、驳回结果可沉淀为后续难例和优化依据。

## 项目结构
```text
backend/                 Flask 后端、Agent 编排、API、报告与质控逻辑
backend/agent/           planner / loop_controller / context / tool registry
backend/three_class/     NCCT 三分类模型推理与 Grad-CAM
backend/workers/         异步任务 worker
dinov3/                  血管闭塞三分类相关推理代码与权重目录
frontend/                React + Vite 前端源码
static/                  静态页面、构建产物与前端脚本
EKV_docs/                外部知识校验文档与知识库 manifest
tests/                   核心模块测试
```

## 应用场景
1. **基层医院急性缺血性脑卒中首诊辅助评估**：在有 NCCT / CTA / mCTA、缺少完整 CTP 的环境中辅助完成出血安全分诊、闭塞风险识别和灌注评估补足。
2. **上转前快速结构化分析与远程会诊支持**：自动生成包含闭塞风险、灌注异常、半暗带提示、证据来源和风险提示的结构化病例摘要。
3. **CT 设备厂商基层智能配套服务**：作为“硬件设备 + 专病智能体辅助分析”的增值模块，在不额外配置完整 CTP 流程的情况下增强基层卒中辅助评估能力。
4. **教学与科研辅助**：DAG 执行图、结构化报告、证据链和节点日志可用于医学教学、低年资医生培训、难例复盘和后续模型优化研究。

## 后续优化方向
- 扩大真实脱敏病例规模，开展多中心、多设备、多模态验证。
- 持续优化 NCCT 三分类与血管闭塞识别，重点提升出血类召回率、早期缺血识别能力和 LVO / MeVO 稳定性。
- 完善 MRDPM 类 CTP 生成质量评价体系，结合真实 CTP 对照、专家评分和临床一致性分析验证辅助价值。
- 强化分级知识库、混合 RAG、证据追溯和冲突处理策略。
- 优化 Agent Cockpit 的 DAG 可视化、影像查看、证据展开、风险提示和报告编辑效率。

## 合规与使用声明
- 本系统用于教学、科研、比赛展示和工程验证场景。
- 不可替代执业医师诊疗行为。
- 生产落地前需结合本地法规、院内流程、数据安全要求和伦理规范进行合规审查。
