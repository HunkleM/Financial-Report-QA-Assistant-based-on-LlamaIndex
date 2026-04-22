# 01 架构细节与数据流转 (Architecture & Data Flow Details)

本文档旨在为开发者提供本项目核心模块的具体技术实现规范、API 接口定义及数据流转结构，确保各模块开发时的数据契约一致性。

---

## 1. 核心数据结构契约 (Core Data Schema)

系统在数据接入 (Ingest) 阶段生成的核心数据单元为 `BaseNode`。为了支撑前端界面的“可验证交互（点击引用跳转原文）”（`P2` 必做），系统强制所有 Node 必须遵循以下 `metadata` 契约：

```python
# 数据契约示例
node.metadata = {
    "source": "2023_Tesla_Annual_Report.pdf",  # [必选] 原始文档名，用于分组过滤与展示
    "page_label": "42",                        # [必选] 物理页码，用于 iframe 动态跳转
    "chunk_strategy": "fixed_256",             # [内部] 记录分块策略 (fixed_256 / semantic)
    "is_raptor_summary": False,                # [内部] 区分底层事实块与高层摘要块
    "raptor_level": 0                          # [内部] 摘要树层级 (0 为叶子节点)
}
```

---

## 2. 数据接入与分块模块 (`src/ingest/`)

### 2.1 PDF 解析 (`pdf_parser.py`)
- **核心工具**: 强制使用 `PyMuPDFReader`（优先于 `SimpleDirectoryReader` 默认的 PyPDF），因其对页码 `page_label` 的提取更为稳定。
- **输入**: 存放研报的本地目录路径。
- **输出**: `List[Document]`。每个 Document 对应 PDF 的一页或整篇，且 metadata 中携带正确的 `source` 和 `page_label`。

### 2.2 分块策略分发 (`chunker.py`)
本模块是系统“自适应分块”实验的核心战场，提供统一的切块入口：

- **基线分块 (Phase 1)**: 
  使用 LlamaIndex 的 `SentenceSplitter`。
  - `chunk_size` = 256
  - `chunk_overlap` = 25
- **语义分块 (Phase 2)**: 
  使用 `SemanticSplitterNodeParser`。
  - 依赖 `BAAI/bge-m3` 提供的嵌入向量计算句间余弦相似度。
  - `breakpoint_percentile_threshold` = 95。

---

## 3. 存储与多路检索模块 (`src/retrieval/`)

### 3.1 向量数据库与持久化 (`indexer.py`)
- **核心组件**: ChromaDB (`chromadb.PersistentClient`)。
- **隔离策略**: 针对不同的分块策略，系统必须建立不同的 Collection 物理隔离（如：`phase1_fixed_256` 集合，`phase2_semantic` 集合），避免混合检索导致数据污染。
- **RAPTOR 树状构建 (Phase 2)**: 启用时，调用 LlamaIndex 的 `RaptorPack`，并注入 `qwen2.5:7b` 模型作为 `summary_model` 进行后台层级摘要。

### 3.2 混合召回与精排 (`retriever.py`)
- **Phase 1 (单路检索)**: 直接使用 `VectorStoreIndex.as_retriever(similarity_top_k=5)`。
- **Phase 2 (多路混合检索)**:
  1.  **Dense 召回**: `VectorIndexRetriever(top_k=20)`
  2.  **Sparse 召回**: 基于 LlamaIndex `BM25Retriever` (需在内存中维护完整的 Node 列表，`top_k=20`)
  3.  **融合 (RRF)**: 使用 `QueryFusionRetriever` 合并上述两路召回结果。
  4.  **精排 (Cross-Encoder)**: 将融合后的 Top-N 传入 `SentenceTransformerRerank(model="BAAI/bge-reranker-base", top_n=5)`，最终只向大模型输入前 5 个高分片段。

---

## 4. 生成与交互模块 (`src/generation/` & `src/ui/`)

### 4.1 对话引擎与记忆池 (`pipeline.py`)
系统不使用最简单的 `query_engine`，而是使用能够处理多轮对话的带状态引擎。
- **核心组件**: `CondensePlusContextChatEngine`。
- **记忆管理**: 注入 `ChatMemoryBuffer(token_limit=4096)`。
- **工作机制**: 当用户提出带代词的问题（如“它的风险是什么？”）时，引擎会自动提取 `ChatMemoryBuffer` 中的历史对话，利用 LLM 将问题重写为无歧义的独立 Query（如“Tesla 2023年的风险是什么？”），再送入底层检索器。

### 4.2 严格引用 Prompt 设计
大模型的 Context Prompt 必须内置极其严格的“反幻觉”与“强制引用”指令：
> "你是一个严谨的金融分析师。仅使用提供的研报片段作答。若片段信息不足，必须回答'基于当前源文档暂未找到关联信息'。**回答末尾必须严格按照以下格式标注出处：【来源：{source} 第{page_label}页】。**"

### 4.3 可验证交互（P2 必做）
- UI 必须支持“点击引用 -> 右侧 PDF 预览跳转到对应页码”的联动。
- 当引用信息缺失或页码无效时，前端需给出降级提示，不得静默失败。