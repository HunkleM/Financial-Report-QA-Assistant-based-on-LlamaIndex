# Insight: 金融研报分析引擎 - 课程执行与架构设计方案

本文档专为满足课程要求（System Architecture Design, Capability Evaluation, Advanced Suggestions）而编写。本系统定位为**垂直领域的“带有短期记忆的对话式文档问答代理”（Conversational Document QA Agent）**，专注于高保真、低幻觉的金融研报分析。

## 硬件与运行环境上下文
- **硬件平台**: Mac Studio (M3 Ultra, 32-core CPU, 512GB 统一内存)
- **核心优势**: 512GB 的统一内存允许我们在本地直接加载并运行 72B 级别的大语言模型（如 Qwen2.5-72B），实现高质量本地推理、零核心大模型 API 推理成本以及更好的数据隐私控制（仅在需要时调用外部数据 API）。

---

## 1. 系统架构与技术路线图 (Architecture & Data Flow)

本系统采用高内聚、低耦合的模块化设计，完美适配 Mac Studio (M3 Ultra) 的极致本地算力。

以下为系统的端到端数据流转与技术路线图：

```mermaid
graph TD
    subgraph Data Ingestion [数据接入层 (src/ingest)]
        A[金融研报 PDF] --> B(PyMuPDF / SimpleDirectoryReader)
        B -->|提取文本 + source + page_label| C{Chunking 策略分发}
        
        C -->|Phase 1: Baseline| D[Fixed-256 分块 <br> SentenceSplitter]
        C -->|Phase 2: Advanced| E[Semantic Chunking <br> BGE-M3 语义切分]
        
        D --> F[Embedding 向量化 <br> BAAI/bge-m3]
        E --> F
        
        F --> G[(ChromaDB 本地向量库)]
        
        E -.->|Phase 2: P2| H[RAPTOR 宏观摘要树 <br> qwen2.5:7b 后台聚类]
        H -.-> G
    end

    subgraph Retrieval & Generation [检索生成层 (src/retrieval & generation)]
        I[用户输入 / Agent 查询] --> J{Retrieval 策略分发}
        
        J -->|Phase 1: Baseline| K[单路稠密向量检索 <br> VectorIndexRetriever]
        J -->|Phase 2: Advanced| L[多路混合检索 Hybrid <br> BM25 + Vector + RRF]
        
        K --> M[Reranker 精排 <br> bge-reranker-base]
        L --> M
        
        M -->|Top-5 Context| N[生成核心 <br> CondensePlusContextChatEngine]
        N -->|LLM Backend: Qwen2.5-7B| O[结构化回答 <br> 强制附带原文页码]
    end

    subgraph Evaluation [评估闭环层 (src/evaluation)]
        O --> P((RAGAS 自动化评估))
        P -->|本地无情裁判 <br> Qwen2.5-72B| Q[量化指标 <br> Context Precision / Faithfulness]
    end

    subgraph Workspace UI [交互层 (src/ui)]
        I -.-> R[Gradio 前端]
        O -.-> R
        R -.->|RLHF 机制| S[收集人类 Like/Dislike 偏好]
    end
```

---

## 2. 系统架构设计细节

### 2.1 应用类型与功能
系统对标 Google NotebookLM 的核心体验，融合了以下三种课程要求的应用类型：
1. **文档问答系统 (Document QA System) & 产物生成**:
   - **核心链路**：PDF 摄入 -> 文本清洗 -> 分块 -> BGE-M3 向量化 -> ChromaDB 存储 -> 混合检索 (BM25 + Vector) -> bge-reranker 精排 -> LLM 综合回答。
   - **结果产物能力 (Artifacts)**：系统不仅支持单轮问答，还具备 NotebookLM 式的结构化产物生成能力（如：基于研报一键生成 FAQ、执行摘要、跨公司财务对比表）。
   - **自适应分块策略 (Adaptive Chunking)**: 课程要求的“256 Token 分块”仅作为本系统的**对比基线 (Baseline)**。针对金融研报数据密集、段落逻辑连贯的特点，本系统采用了真正的自适应技术——**基于 BGE-M3 的语义分块 (Semantic Chunking)**。系统通过计算句间余弦相似度，在语义发生突变（如相似度跌破 95% 阈值）时才进行切分，最大程度保留了财务分析的上下文完整性。
   - **宏观问答杀器 (RAPTOR 树状检索)**: 针对传统 RAG 无法处理“跨页总结”（如“总结全文提到的三大风险”）的痛点，本系统引入了 RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval) 技术。利用后台小模型（默认 `qwen2.5:7b`，可替换为同级模型）对底层语义块进行递归聚类与摘要，构建宏观知识树，将其作为解决复杂金融总结问题的重要方案，与基础的 256 分块形成性能对比。
   - **【产品边界声明】**：当前版本侧重于“检索问答与自动产物生成”。NotebookLM 级的“用户手动摘录片段 -> 二次组织 -> 基于个人笔记再生成”的重度双向笔记工作流，因前端工程量巨大，明确列为 **[P3 选做/非当前目标]**。
2. **对话式代理 (Conversational Agent)**:
   - 具备**短期记忆管理能力**。在 LlamaIndex 的 `CondensePlusContextChatEngine` 中集成 `ChatMemoryBuffer` (token limit = 4096)，确保模型能在多轮对话中理解上下文指代（如：“它去年的营收是多少？”）。
3. **自主代理 (Autonomous Agent)**:
   - 系统集成了 LlamaIndex 的 `ReActAgent` 与外部 API，构建了一个任务导向型智能体。
   - **API 集成**: 接入了 **Yahoo Finance API (`yfinance`)**。当用户提问不仅涉及研报内的静态基本面分析，还涉及动态市场表现时（例如：“研报看好该公司，它今天的实时股价是多少？”），Agent 将自主决定调用股价查询工具，将静态研报内容与实时金融数据融合，作为**客观信息辅助展示（系统郑重声明：所有输出均不构成自动投资决策或建议）**。

### 2.2 数据连接器与源管理 (Source Lifecycle)
- **输入源边界**: **[P0 核心]** 当前版本专注于高质量 PDF 研报的解析与清洗。**[P3 选做]** 网页 URL、纯文本文件、多模态混合源的统一聚合策略。
- **源生命周期管理 (Notebook-level)**: UI 层需具备基础的“工作区”源管理能力，包括：多份研报文档的上传聚合（共享同一向量空间）、支持针对特定研报的**禁用/启用过滤 (Filter by metadata)**、以及动态去重与删除。
- **元数据保留**: 在 Node 级别强制保留 `source` (文件名) 和 `page_label` (物理页码)。这是支撑下游 UI 层实现“可验证交互”的底层基石。

### 2.3 LLM 后端性能对比
系统配置两套本地运行的模型后端进行严格的 A/B 对比：
- **强模型后端 (The Heavyweight)**: `Qwen2.5-72B` (通过 Ollama 4-bit/8-bit 量化运行)。得益于 M3 Ultra 的算力，它将作为最终回答的生成器和幻觉控制中枢。
- **弱模型后端 (The Lightweight)**: `Qwen2.5-7B`（默认）；可选同级开源模型作为补充对照。用于对比展示在长文本推理和严格格式遵循（如强制输出页码引用）上，小模型与 72B 模型的差距。

---

## 3. 能力评估 (Capability Evaluation)

针对金融场景，系统的评估不依赖人类的主观感受，而是建立严谨的量化指标和性能分析体系。

### 3.1 实用评估指标 (Metrics & Test Cases)
系统内置统一的 **20 个标准化的金融问答测试用例**（涵盖微观数据提取与宏观风险总结），贯穿所有阶段的消融实验，确保数据具备横向可比性。

- **最小分层设计（避免“平均抽题”偏差）**：
  - 研报类别：公司深度、行业策略
  - 任务类型：事实抽取、总结归纳、跨文档对比
  - 建议配额：`2 (类别) x 3 (任务) x 每格3题 = 18题`，其余 2 题作为边界案例（长文本总结/低相关拒答）
- **回答相关性 (Relevance) 与 幻觉率 (Faithfulness)**: 
  - 引入 **RAGAS** 评估框架。
  - **核心亮点 (本地化评估闭环)**: 不依赖 OpenAI API。得益于 M3 Ultra 的庞大统一内存，系统直接将本地运行的 `Qwen2.5-72B` 注册为 RAGAS 的 `judge_model`（无情裁判）。它将对 7B 弱模型以及不同检索策略（基础 256 分块 vs 语义分块+RAPTOR）的回答进行打分，在当前实验设置下兼顾隐私与评估一致性。
- **任务完成率 (Task Completion / Citation Accuracy)**:
  - 任务成功的定义为：不仅给出正确答案，还必须附带正确的 `source` 和 `page_label`（原文溯源引用）。统计系统在测试集上的引用准确率。

### 3.2 内存-性能权衡分析 (Memory-Performance Trade-offs)
在构建索引和检索阶段，系统将记录并分析不同分块策略下的性能损耗：
1. **策略 A (基线)**: Fixed-256 (256 tokens, 10% overlap)
2. **策略 B (对照 1)**: Fixed-512 (512 tokens, 10% overlap)
3. **策略 C (对照 2)**: Semantic Chunking (语义分块，基于 BGE-M3 的句间余弦相似度)
- **分析维度**: 
  - 索引构建耗时 (Time to Index)
  - ChromaDB 磁盘/内存占用 (Storage Space)
  - RAGAS 检索精度得分 (Context Precision)
- **预期结论**: 展示细粒度分块（256）与粗粒度分块在召回率与计算资源之间的 Trade-off。

### 3.3 交互质量与可用性指标 (UX & Interaction SLOs)
为缩小与 NotebookLM 等真实产品的体验差距，除模型精度外，本系统设定以下可验收的非功能性指标约束（单机本地环境，PDF 工作区规模 <= 20 份）：
- **可验证交互 (Verifiable UX)**:
  - 引用点击跳页成功率 >= 95%
  - 引用页码命中率 >= 90%（人工抽检）
  - 伪造引用拦截率 >= 95%（在 `citation_audit` 标记为无对应 source/page 时触发降级）
- **流式响应与首包延迟 (TTFT)**:
  - P50 <= 3s，P95 <= 8s（7B 路径）
  - 72B 离线评估路径不纳入交互时延指标
- **兜底/降级策略 (Fallback)**:
  - 当检索相关度低于阈值（配置化）时，触发固定拒答模板
  - 拒答样本误答率（应拒答却给出结论）<= 10%

---

## 4. 进阶建议落实 (Advanced Suggestions)

系统设计自然融合了课程要求的两项进阶挑战：

### 4.1 模型部署中的量化技术 (Model Quantization)
- **技术落地**: 本项目未使用传统的 FP16/FP32 全精度模型，而是基于 `llama.cpp` 和 `Ollama` 引擎，成功在 Apple Silicon 统一内存架构下部署了 **GGUF 格式的 4-bit (Q4_K_M) / 8-bit (Q8_0) 量化模型**。
- **收益**: 将 72B 模型的显存占用从 ~144GB 压缩至 ~42GB，在保持极高推理精度的同时，极大地提高了 Token 生成速度。

---

## 5. 两阶段敏捷开发路线图 (2-Phase Execution Plan)

为确保项目平稳落地并在核心架构上取得及格分，随后逐步释放 M3 Ultra 算力以获取高分，本项目采取两阶段开发策略。

### 5.1 Phase 1: 核心引擎与无情裁判 (The Engine & The Judge)
**目标**: 跑通端到端的 RAG 数据流，并建立量化评估闭环。优先解决金融研报的读取、基础检索和 72B 自动打分。

*   **配置参数 (`configs/config.yaml`)**:
    - `chunking.strategy`: "fixed" (强制使用基线)
    - `chunking.chunk_size`: 256 (满足课程字面要求)
    - `raptor.use_raptor`: false (暂时关闭)
    - `parser.use_llamaparse`: false (使用本地 `PyMuPDF`)

*   **开发任务与代码映射**:
    1. **Ingest (数据接入)**
       - `src/ingest/pdf_parser.py`: 编写 `load_financial_pdfs(dir_path)` 函数。使用 `SimpleDirectoryReader` 或 `PyMuPDFReader` 读取 `data/` 目录下的 PDF，**必须确保提取并保留 `source` (文件名) 和 `page_label` (物理页码) 元数据**。
       - `src/ingest/chunker.py`: 编写 `get_baseline_nodes(documents)` 函数。调用 LlamaIndex 的 `SentenceSplitter(chunk_size=256, chunk_overlap=25)`，将文档切割为 Node。
       - `src/ingest/indexer.py`: 编写 `build_vector_index(nodes)` 函数。使用 BGE-M3 向量化，存入本地 ChromaDB (`./chroma_db/phase1_baseline`)。
    2. **Retrieval & Generation (基础问答)**
       - `src/retrieval/retriever.py`: 编写 `get_basic_retriever(index)` 函数，实现简单的 `VectorIndexRetriever(top_k=5)`。
       - `src/generation/pipeline.py`: 编写 `run_basic_qa(query, retriever)` 函数。使用 `Qwen2.5-7b` 运行基础问答。在 Prompt 中强制要求输出【来源：xxx 第x页】。
    3. **Evaluation (核心战役：评估闭环)**
       - `src/evaluation/ragas_eval.py`: 编写 `run_evaluation(test_questions)`。将本地的 `Qwen2.5-72B` 实例化为 Ragas 的 `judge_model`（若遇极端资源限制，允许降级至 7B + 小样本人工抽检兜底）。
       - 使用全套的 **20 个金融测试题**，让裁判对 Phase 1 的回答计算 `Context Precision` 和 `Faithfulness`。

*   **Phase 1 验收标准**: 产出一份控制台输出日志，证明系统能解析 PDF，用 7B 模型回答问题，且 72B 裁判打出了量化分数（资源不足时采用文中降级方案并说明）。

### 5.2 Phase 2: 火力全开与高级交互 (The Turbochargers & The Frontend)
**目标**: 释放 M3 Ultra 算力，引入高分进阶特性，完成系统交互封装与“内存-性能权衡”进阶实验。

*   **配置参数 (`configs/config.yaml`)**:
    - `chunking.strategy`: "semantic"
    - `raptor.use_raptor`: true
    - `raptor.summary_model`: "qwen2.5:7b"

*   **开发任务与代码映射**:
    1. **架构跃升 (Adaptive & Macro) [P2 必做]**
       - `src/ingest/chunker.py`: 编写 `get_semantic_nodes(documents)` 函数。调用 `SemanticSplitterNodeParser`，利用 BGE-M3 的余弦相似度（阈值 95%）实现真正的自适应语义分块。
       - `src/ingest/indexer.py`: 编写 `build_raptor_index(nodes)` 函数。集成 `RaptorPack`，后台拉起 `qwen2.5:7b`（或同级小模型）构建宏观摘要树，存入 ChromaDB (`./chroma_db/phase2_raptor`)。
    2. **多路召回 (Hybrid Search) [P2 必做]**
       - 在 `src/retrieval/retriever.py` 中扩展 `get_hybrid_retriever(index)` 函数。集成 BM25 检索，与向量检索组合，并通过 `QueryFusionRetriever` 进行 RRF 融合，最后叠加 `bge-reranker-base` 精排。
    3. **进阶实验 (Trade-off Analysis) [P2 必做]**
       - 使用 Phase 1 建立的 `ragas_eval.py`，对升级后的 Phase 2 架构重新打分。记录 `chroma_db/` 目录体积和构建耗时，产出用于报告的对比表格。
    4. **自主代理 (Autonomous Agent) [P3 选做]**
       - 在现有 `src/generation/pipeline.py`（或 `src/ui/app.py`）中增加 Agent 模式入口，编写 `fetch_stock_price(ticker)` 工具函数（调用 `yfinance`），并通过 `ReActAgent` 进行工具调用编排。
    5. **沉浸交互与 Notebook 体验 (Gradio UI & RLHF) [P2/P3]**
       - 在现有 `src/ui/app.py` 基础上，搭建“左侧源管理 + 右侧对话/产物生成”的 NotebookLM 级工作台布局。
       - **[P2 必做] 落地可验证交互**: 实现引用点击联动 PDF 动态跳转（利用 iframe 参数）。
       - **[P3 选做]** 编写 `log_feedback()` 函数，将人类反馈数据追加写入 `data/human_feedback_log.jsonl`，用于后续偏好分析。

*   **Phase 2 验收标准**:
    - **P2 必做通过标准**：
      1) 运行 `python src/ui/app.py`，完成 Phase 2 必做实验数据（语义分块、RAPTOR、Hybrid 检索消融）  
      2) 支持多文档动态挂载/过滤  
      3) 支持一键生成执行摘要/FAQ（Artifacts）
      4) 支持引用点击跳转原文（PDF 联动跳页）
    - **P3 加分项（选做）**：
      - 雅虎金融工具调用  
      - 反馈日志（RLHF 数据采集）

---

## 6. AI 编码规约与技术断言 (Developer & AI Coding Conventions)

**致接手本项目的任何 AI Agent 或人类开发者**：为确保项目在架构上的绝对一致性和代码的可运行性，请严格遵守以下技术断言。

### 6.1 框架版本与依赖断言 (LlamaIndex v0.10+)
本项目**强制基于 LlamaIndex v0.10 及以上版本**构建。禁止使用 `llama_index` 单一包的过时 import 方式。
- **Core**: 所有核心模块必须从 `llama_index.core` 导入（例如 `from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings`）。
- **Integrations**: 外部集成必须使用独立的包，包括：
  - `llama-index-vector-stores-chroma`
  - `llama-index-embeddings-huggingface`
  - `llama-index-llms-ollama`
  - `llama-index-postprocessor-flag-embedding-reranker` (或 `sentence-transformers`)

### 6.2 数据字典契约 (Node Metadata Schema)
在 Ingest 阶段切分出的每一个 `BaseNode`，其 `metadata` 字典**必须**包含以下两个键，否则 UI 层将抛出溯源错误：
1. `source` (str): 原始 PDF 的文件名（例如 `"report_2023.pdf"`）。
2. `page_label` (str): 该文本块所在的物理页码（例如 `"12"`）。若跨页，取起始页。

### 6.3 评估裁判的实例化断言 (Local Ragas Judge)
在 `evaluation/ragas_eval.py` 中，**严禁调用 OpenAI API**。
必须使用本地 Ollama 提供的 `qwen2.5:72b`（或降级模型）作为 Ragas 的裁判。请通过 `ragas.llms.LangchainLLMWrapper` 包装 `langchain_community.chat_models.ChatOllama`，或寻找适配你所用 Ragas 版本的 LlamaIndex Wrapper 注入给 `judge_model`。

### 6.4 配置文件骨架 (config.yaml)
所有代码的硬编码参数必须迁移至 `configs/config.yaml`。本系统解析该文件的标准骨架如下，请勿随意更改键名：

```yaml
llm:
  strong_model: "qwen2.5:72b"
  weak_model: "qwen2.5:7b"
  ollama_base_url: "http://localhost:11434"
  temperature: 0.1

embedding:
  model: "BAAI/bge-m3"
  device: "mps"

reranker:
  model: "BAAI/bge-reranker-base"
  top_n: 5

chunking:
  strategy: "fixed" # "fixed" | "semantic"
  chunk_size: 256
  chunk_overlap: 25
  semantic_buffer_size: 1
  semantic_breakpoint_percentile: 95

raptor:
  use_raptor: false
  max_levels: 3
  summary_model: "qwen2.5:7b"

retrieval:
  bm25_top_k: 20
  vector_top_k: 20
  final_top_k: 5

storage:
  chroma_persist_dir: "./chroma_db"
  data_dir: "./data"

evaluation:
  test_set_path: "./data/test_set.json"
  judge_model: "qwen2.5:72b"
```