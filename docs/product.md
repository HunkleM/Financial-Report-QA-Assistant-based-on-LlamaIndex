# Product Document

**配套文档**：实现细节、目录结构与实验脚本以 [`technical_design.md`](./technical_design.md) 为准；本文描述产品目标、范围与验收口径，二者需保持一致。

## 1) 项目名称

**Financial Report Question Answering System based on LlamaIndex**  
（基于 LlamaIndex 的金融研报问答系统）

---

## 2) 背景与动机（Why）

金融研报通常篇幅长、信息密度高，包含：

- 公司基本面分析
- 行业趋势判断
- 风险提示与评级结论

在多文档场景下，传统阅读方式难以高效支持：

- 快速检索
- 跨文档对比
- 结构化总结

因此，需要一个可解释、可追溯的文档智能问答系统来提升分析效率。

---

## 3) 项目目标（What）

构建一个面向金融研报 PDF 的 RAG 问答系统，支持：

- 基于文档的高效问答
- 多文档信息整合与总结
- 引用来源可追踪（evidence/citation）

并重点研究：

- RAG 在金融文本中的实际效果
- 不同 chunking 策略对性能与准确性的影响
- 不同 LLM 后端的质量与效率差异

---

## 4) 问题定义（Problem Statement）

### 4.1 输入与输出

- 输入：
  - 文档集合 `D = {d1, d2, ..., dn}`（金融研报）
  - 用户查询 `q`
- 输出：
  - 答案 `a`
  - 引用集合 `C`，其中 `C ⊂ D`

### 4.2 形式化表达

`a = LLM(q, Retrieve(q, D))`

其中：

- `Retrieve`: 向量检索或混合检索（Hybrid）
- `LLM`: 基于检索证据生成最终回答

---

## 5) 范围、优先级与非目标（Scope, Priority & Non-goals）

### 5.1 范围（In Scope）

- PDF 研报解析、清洗与分块
- 检索增强生成（RAG）问答
- 引用片段返回（见下文「引用与可追溯性」）
- 多轮对话（短期记忆）
- 评估与消融实验
- **演示界面**：默认 **Gradio Web UI**（与 `technical_design.md` 一致；CLI 可作为辅助）

### 5.1.1 索引与日常使用的约定

- **日常使用（P0/P1）**：系统**仅维护当前所选分块/检索策略**下的一套持久化索引（如 Chroma collection），避免用户每上传一篇文档就同步多套实验用索引。
- **消融与对比实验**：需在**多种分块或 collection 策略**下对比时，由**离线脚本**批量构建/重建索引，保证可复现；详见 `technical_design.md` §5.11.5。

### 5.2 实现优先级（与开发计划对齐）

| 优先级 | 内容 |
|--------|------|
| **P0（最小可演示）** | 固定分块 + 向量检索 + 本地 LLM 生成 + 基础引用展示 + Gradio 或 CLI |
| **P0** | 多路召回（BM25 + 向量）+ 可选 rerank；消融矩阵中的 chunk / overlap / 召回 / 模型对比 |
| **P1** | 文档管理（增量增删）、文档概览与建议问题、RAGAS 自动化评估 |
| **P2（可选）** | RAPTOR 层次索引、网页 URL 入索引、GraphRAG（PropertyGraph） |

详细任务拆分见 `technical_design.md` **第 8 节（开发分工）**。

### 5.3 非目标（Out of Scope，当前阶段）

- 金融交易建议或自动投资决策
- 复杂表格的高精度结构化解析
- 大规模在线服务化部署（如高并发生产集群）

### 5.4 引用与可追溯性（Citation）

系统应能展示答案所依据的**证据片段**，并尽量标明**来源文档与位置**，便于人工核对：

- **必选**：`source`（文件名或稳定 doc id）+ 检索到的 `node` 原文片段（与 `source_nodes` 一致）。
- **推荐**：`page` 或 `page_label`（页码）；若 PDF 解析无法可靠提供页级元数据，则 UI 与 Prompt 中改为标注「文档名 + 片段编号/段落」，并在技术实现中说明限制。

验收时，「引用准确性」以**用户可见引用是否与检索证据一致**为主（见 **§8**）。

---

## 6) 系统架构（Architecture）

系统基于 LlamaIndex 构建，核心模块如下。

**主评测基线（P0，与 `technical_design.md` §6.1 一致）**：在报告核心实验结果时，除非专门说明在做哪一项消融，否则默认采用：**Fixed-512**、**overlap = 10%**、**BM25 + 稠密向量 + RRF 融合**、**bge-reranker 精排**、评测 LLM 为 **Qwen2.5-72B**（资源不足时**全班统一**使用 **7B** 并在实验报告中注明）。

### 6.1 数据接入（Data Ingestion）

- 输入：PDF 金融研报
- 处理流程：
  - 文本解析（PDF -> text）
  - 文本清洗（页眉页脚、噪声去除）
  - 文本分块（chunking）

### 6.2 分块策略（Chunking Strategy）

实验对比策略（与 `technical_design.md` 消融矩阵一致）：

- **固定长度分块**：消融使用 **256** 与 **512**（tokens 或框架等价单位，以 LlamaIndex `SentenceSplitter` 配置为准）；**默认开发基线建议 512**，256 作为对照组。
- **重叠率**：**0% / 10% / 20%**（在选定固定 chunk 尺寸下消融）。
- **语义分块**：`SemanticSplitterNodeParser`（可选对照）。
- **RAPTOR**（P2）：层次摘要检索，与固定/语义分块做对比。

### 6.3 索引与检索（Indexing & Retrieval）

- 文本向量化（embedding）：**BAAI/bge-m3**（见技术设计）。
- 向量数据库：**ChromaDB**（持久化；若后续需纯内存实验可再引入 FAISS，非当前默认）。
- 召回：**Top-k** 检索（精排后呈现给用户 **k ≈ 3～5**，中间召回可更大，见配置）。
- **Hybrid Retrieval**：**BM25 + 稠密向量**，多路结果 **RRF（reciprocal rank fusion）** 融合；可选 **cross-encoder rerank**（**BAAI/bge-reranker-base**）。
- **可选（P2）**：GraphRAG（`PropertyGraphIndex`）第三路召回，仅建议用于跨文档对比类问题评估。

### 6.4 答案生成（Answer Generation）

- 输入：`query + retrieved chunks`（经多轮对话时含 **问题改写**，见技术设计 §5.11）
- 输出：
  - 自然语言答案
  - 可追溯引用（来源文档与片段）
- **拒答**：当检索证据不足时，应输出约定格式的「信息不足」表述，**避免幻觉**；实现层策略见 `technical_design.md` §5.11.4。

### 6.5 对话记忆（Conversational Memory）

- 保存短期 chat history
- 支持多轮问答上下文连续性（如 `CondensePlusContextChatEngine` + `ChatMemoryBuffer`，详见技术设计）

---

## 7) 模型后端方案（LLM Backends）

**当前项目默认实现**（本地、零 API 费用）：通过 **Ollama** 运行 **Qwen2.5** 系列 instruction 模型，并至少对比：

- **强模型**：`qwen2.5:72b`（或同系列可本地加载的量化变体，名称以 Ollama 为准）
- **轻量模型**：`qwen2.5:7b`

**说明**：产品层面的「强 / 弱模型对比」与论文中的 Mistral、T5 等**意图相同**（不同参数量与能力的 instruction LLM）；若课程或复现环境受限，允许替换为**同级开源 instruction 模型**，但需在实验报告中注明实际模型名与量化方式。

**运行环境**：优先 Apple Silicon（**MPS**）+ 大内存本地推理；若无 72B 条件，验收以 **7B 端到端流程 + 离线/子集评测** 为降级方案（见 `technical_design.md` 风险表）。

---

## 8) 评估设计（Evaluation）

### 8.1 测试集构建（Test Set）

构建金融问答集合，覆盖以下任务类型（**建议规模**：每类 **10** 题，合计 **40** 题，与 `technical_design.md` §6.3 对齐；可按课程要求微调并说明）：

| 类型 | 示例 |
|------|------|
| 信息提取 | “该公司收入增长的主要驱动因素是什么？” |
| 总结 | “总结该报告的核心观点。” |
| 跨文档对比 | “两份报告对该公司的评级是否一致？” |
| 风险识别 | “报告中提到的主要风险有哪些？” |

### 8.2 评估指标（Metrics）

1. **Relevance（相关性）**：回答与问题是否匹配  
2. **Faithfulness（事实一致性）**：回答是否基于检索证据、是否出现幻觉  
3. **Citation Accuracy（引用准确性）**：用户可见引用（文档名、页码或片段定位）是否与**实际返回的检索片段**及原文一致；是否存在张冠李戴或未引用却断言。  
4. **Task Completion Rate（任务完成率）**：是否完成问题目标（可由人工按题打分或二元判定）。

**自动化（RAGAS）**：在技术实现中使用 **context recall / context precision、faithfulness、answer relevancy** 等（见 `technical_design.md`），与上述 1、2、4 强相关，但**不能单独等同于引用准确性**。

**引用准确性（建议闭环）**：

- **自动代理指标**：答案中逐条引用对应的文本，是否与某条 `source_node` 内容高度重叠（如包含关系或字符级相似度阈值），用于批量筛查。  
- **人工抽检**：在每类任务上抽取若干题，核对引用与原文；实验报告需报告抽检规模与样例。

### 8.3 消融实验（Ablation）

在 **§6 主评测基线** 之外，逐项改变单一因素，固定其余条件；详细矩阵见 `technical_design.md` **§6.1**。

| 实验 | 变量（示例） |
|------|----------------|
| Chunking | Fixed-256 / Fixed-512 / Semantic；（P2）RAPTOR 独立对照 |
| Overlap | 0% / 10% / 20%（在 Fixed-512 下） |
| 召回 | 单路向量 / BM25+向量融合 / 融合 + rerank |
| 模型 | Qwen2.5-7B vs 72B |
| GraphRAG（P2） | KG 关 / 开；**仅跨文档对比类**子集 |

### 8.4 可复现性（Reproducibility）

- **依赖**：锁定 LlamaIndex 及相关库版本，并在 README 或报告中列出（见 `technical_design.md` §2.1、§7）。
- **配置**：实验所用 `chunk_size`、overlap、检索 `top_k`、模型名、collection 名等以 **`configs/config.yaml` + 实验记录** 为准。
- **脚本**：RAGAS 与引用核查（`citation_audit`）的输入测试集路径、judge 模型与随机种子应记录在实验报告中。

---

## 9) 预期贡献（Expected Contributions）

- 构建完整的金融研报 RAG 问答系统
- 提供可解释、可追溯的答案输出
- 系统性分析 chunking 对性能的影响
- 对比不同 LLM 在实际文档任务中的表现差异

---

## 10) 扩展方向（Future Extensions）

在时间允许情况下可增加：

- 模型量化（GPTQ / 4-bit）
- 人类反馈（简单 ranking / preference）
- 多文档自动摘要（multi-document summarization）
- 风险提取模块（structured output）
- **（P3，可选，不计入默认交付）** Agent / 工具调用（如 `ReActAgent` + `FunctionTool`），与主 RAG 多轮对话**分轨**实现；细节见 `technical_design.md` §5.11.6

---

## 11) 交付内容（Deliverables）

- 可运行系统代码
- 演示系统（CLI 或 Web UI）
- 实验报告（含对比与分析）
- 用户使用说明文档

---

## 12) 一句话总结

本项目将实现一个面向金融研报的 RAG 问答系统，并系统研究检索策略与模型选择对真实应用性能的影响。