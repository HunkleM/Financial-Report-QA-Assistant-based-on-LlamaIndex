# 技术规格文档 (Technical Specification)

本文档旨在详细描述 **Insight: 金融研报分析引擎** 的架构演进、核心算法及数据流转机制，供研发与维护团队参考。

---

## 1. 架构全景图

系统由原本的基础 RAG 升级为 **NotebookLM-Like** 工作台架构，横跨四个深度优化的技术域：

1.  **高保真解析层 (Data & Parsing)**：引入云端能力与语义切割，确保财务表格不乱序、段落不断层。
2.  **认知增强检索层 (Retrieval & Indexing)**：通过混合搜索及预计算的宏观摘要树 (RAPTOR) 建立全局与微观视角的索引。
3.  **智能合成层 (Generation)**：基于 Qwen2.5 的角色扮演 (Persona) Prompt，支持跨文档维度的信息萃取与合成。
4.  **沉浸交互层 (Workspace UI)**：Gradio 构建的三栏联动机制，提供从“对话”到“核查原文”的无缝闭环体验。

---

## 2. 核心模块与算法规格

### 2.1 高保真接入 (`src/ingest/`)

*   **PDF 解析器 (`pdf_parser.py`)**：
    *   **引擎**：集成 `LlamaParse(result_type="markdown")`。
    *   **机制**：当存在有效 `.env` 密钥时，接管默认的 `PyMuPDFReader`，将双栏布局与复杂表单重建为干净的 Markdown 表格，并提取对应的物理页码。
*   **语义分块 (`chunker.py`)**：
    *   **算法**：`SemanticSplitterNodeParser`。
    *   **指标**：利用 BGE-M3 的 `embed_model` 计算句间余弦相似度。若两句相似度低于 `breakpoint_percentile_threshold=95`，则判定为语义断点进行切分，取代生硬的 Token 定长切割。
*   **层次摘要索引 (`indexer.py`)**：
    *   **架构引入：RAPTOR (Recursive Abstractive Processing)**。
    *   **实现**：针对入库的基础节点，执行步长聚类 (如每 5 个块为一簇)，使用本地 LLM 生成该簇的摘要，作为 Level-2 父节点，直至收敛。
    *   **产出**：叶子节点（细节原话）+ 父节点（全局规律）均同时编入 ChromaDB 与本地 `nodes_cache.pkl`，供后续 BM25 读取。

### 2.2 多路联合检索 (`src/retrieval/`)

*   **召回链路**：
    1.  **Dense 向量召回**：Chroma 引擎，检索 `top_k=20`。
    2.  **Sparse 词频召回**：BM25 引擎 (基于缓存的持久化节点初始化)，检索 `top_k=20`。
*   **排序与精排**：
    *   **融合算法**：`Reciprocal Rank Fusion (RRF)`，有效缓解多模态分数不可通约的问题。
    *   **Cross-Encoder**：最终 Top-5 交由 `BAAI/bge-reranker-base` 重新打分，丢弃相关度极低的幻觉干扰项。

### 2.3 互动与证据链 (`src/ui/app.py`)

*   **工作台状态管理 (`AppState`)**：单例维护内存中的 ChatEngine 与 Index 引用。
*   **证据链路由 (Citation Routing)**：
    *   流式生成结束后，拦截 `source_nodes`。
    *   提取每个 Node 的 `source` 和 `page_label` 元数据。若为 RAPTOR 节点，则打上“宏观摘要”标签。
    *   **联动核心**：Gradio 的 UI Dropdown 事件监听器接收用户点击后，重写右侧 `gr.HTML` 中 `iframe` 的 URL 属性 (`src="/file=...#page=N"`)，触发浏览器原生的 PDF 跳转。

---

## 3. 提示词工程 (Prompt Engineering)

系统在 `src/generation/prompt.py` 中定义了两类专业模板：

*   **Persona QA 模板**：赋予 LLM “华尔街资深分析师” 的角色。强制要求**严密溯源**与**优雅拒答**。若未命中上下文，模型必须回复特定的标准化语言，以配合后端的审计。
*   **Condense 探针模板**：在多轮对话中，利用 LLM 将包含模糊代词（“它”、“这几个”）的追问，压缩并重写为独立、精准的**底层数据库搜索语句 (Search Query)**。

---

## 4. 数据字典 (Metadata Schema)

ChromaDB 与本地内存中的 `BaseNode` 均遵循以下元数据契约：

| 键名 (Key) | 数据类型 | 作用域 | 描述 |
| :--- | :--- | :--- | :--- |
| `source` | `str` | 全局 | PDF 文档的物理文件名 (e.g., `report2023.pdf`) |
| `page_label` | `str` | 叶子节点 | 文本在原始文档中的显示或物理页码 (e.g., `12`) |
| `is_summary` | `bool` | 父节点 | 标记该块是否为 RAPTOR 生成的非叶子聚合节点 |
| `raptor_level`| `int` | 父节点 | 表示该摘要在树中的高度 (Level 1~3) |
