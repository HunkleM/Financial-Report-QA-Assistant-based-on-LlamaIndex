# 技术设计方案

**配套文档**：目标、范围、验收口径见 [`product.md`](./product.md)。若与本文冲突，以 **product.md 为产品真理源**，以 **本文为实现与实验细节**；选型变更需同时改两份文档。

## 1. 与 product.md 对齐摘要

| 维度 | 产品文档要求 | 本文实现 |
|------|-------------|---------|
| 向量库 | 默认 Chroma，FAISS 仅备选 | Chroma 持久化；FAISS 未列入 P0 |
| 分块消融 | Fixed **256 / 512**、overlap 0/10/20%、语义、（可选）RAPTOR | 与 **§6.1** 实验矩阵一致；**默认开发基线 Fixed-512** |
| LLM | 强/弱模型对比 | **Ollama：`qwen2.5:72b` / `qwen2.5:7b`**；环境不足时 7B 为主 |
| 引用 | 文档名 + 片段；推荐页码 | `source` + `source_nodes`；页码见 **§5.1** |
| 评估 | RAGAS + 引用准确性（自动代理 + 人工抽检） | **§6.2** |

## 2. 技术选型总览

| 模块 | 选型 | LlamaIndex 组件 |
|------|------|----------------|
| Demo UI | Gradio Web UI | 独立，调用 LlamaIndex pipeline |
| 向量数据库 | ChromaDB | `ChromaVectorStore` + `StorageContext` |
| Embedding | BAAI/bge-m3 | `HuggingFaceEmbedding` |
| Re-ranker | BAAI/bge-reranker-base | `SentenceTransformerRerank`（`sentence-transformers`） |
| 强模型 | Qwen2.5-72B-Instruct (Ollama) | `Ollama` LLM |
| 弱模型 | Qwen2.5-7B-Instruct (Ollama) | `Ollama` LLM |
| 分块策略 | Fixed-256/512 + 语义 +（P2）RAPTOR | `SentenceSplitter` / `SemanticSplitterNodeParser` / `RaptorPack` |
| 召回策略 | BM25 + 稠密向量多路召回 | `BM25Retriever` + `VectorIndexRetriever` + `QueryFusionRetriever` |
| 知识图谱（可选，P2） | GraphRAG（用户可选开启） | `PropertyGraphIndex` + `SimpleLLMPathExtractor` |
| 对话记忆 | 短期 chat history | `ChatMemoryBuffer` + `CondensePlusContextChatEngine` |
| 评估框架 | RAGAS + 引用核查 | `ragas` + LlamaIndex dataset builder；见 **§6.2** |
| 运行环境 | Apple Silicon + Ollama（推荐大内存跑 72B） | **MPS** 优先；无 72B 时 **7B 演示 + 子集/离线评测**（见 **§9**） |

### 2.1 版本与 API 约定

LlamaIndex 各子包 API 随小版本变化较快。项目应在 `requirements.txt` 中**锁定一组可安装版本**（或使用 `pip-tools`/`uv lock`），并在 README 注明「已验证版本」。合并依赖前对 **ingest / fusion retrieve / chat_engine / RaptorPack（若启用）** 做一次 smoke test。本文中的代码片段为**设计示意**，以当前锁定版本的官方文档为准。

---

## 3. 系统架构

```
用户上传 PDF
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│                   Data Ingestion (LlamaIndex)                 │
│  SimpleDirectoryReader → 清洗 → SentenceSplitter / RAPTOR    │
│                                  │                            │
│              HuggingFaceEmbedding(bge-m3)                    │
│                                  │                            │
│         ChromaVectorStore + StorageContext 持久化             │
└──────────────────────────────────────────────────────────────┘
     │
     ▼ 用户提问
┌──────────────────────────────────────────────────────────────┐
│                   Retrieval (LlamaIndex)                      │
│  BM25Retriever ──┐                                           │
│                  ├─→ QueryFusionRetriever (RRF 融合)         │
│  VectorIndexRetriever ──┤                                    │
│                         │                                    │
│  [可选] KGRetriever ────┘  ← PropertyGraphIndex             │
│                  │                                            │
│         SentenceTransformerRerank (bge-reranker) → Top-5     │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│                   Generation (LlamaIndex)                     │
│  CondensePlusContextChatEngine                               │
│    + ChatMemoryBuffer (多轮记忆)                             │
│    + Ollama(qwen2.5:72b) → 答案 + source_nodes 引用         │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│                   Gradio Web UI                               │
│  文档管理 + 概览/建议问题 + 对话 + 引用展示 + 策略切换       │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. 项目目录结构

```
CS6496-group/
├── data/                        # 金融研报 PDF（不入 git）
├── src/
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py        # PDF → 清洗后文本
│   │   ├── web_reader.py        # 网页 → Document（SimpleWebPageReader）
│   │   ├── chunker.py           # 固定分块 / 语义分块 / RAPTOR
│   │   └── indexer.py           # 构建 ChromaDB 索引（支持增量增删）
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── retriever.py         # BM25 + 向量多路召回（可选 KG 第三路）
│   │   ├── reranker.py          # bge-reranker-base_v1 精排
│   │   └── kg_retriever.py      # PropertyGraphIndex（可选 GraphRAG）
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── llm_backend.py       # Ollama Qwen2.5 封装
│   │   ├── prompt.py            # Prompt 模板管理
│   │   ├── overview.py          # 文档概览 + 建议问题生成
│   │   ├── pipeline.py          # RAG 主流程编排
│   │   └── tools.py             # FunctionTool 定义（可选，P3 Agent 模式）
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── ragas_eval.py        # RAGAS 评估
│   │   ├── citation_audit.py    # 引用与 source_nodes 一致性（自动代理 + 抽检清单）
│   │   └── ablation.py          # 消融实验脚本
│   └── ui/
│       └── app.py               # Gradio Web UI 入口
├── configs/
│   └── config.yaml              # 模型路径、参数、实验配置
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_chunking_analysis.ipynb
│   └── 03_ablation_results.ipynb
├── tests/
│   ├── test_ingest.py
│   ├── test_retrieval.py
│   └── test_pipeline.py
├── docs/
│   ├── product.md               # 产品需求文档
│   └── technical_design.md      # 本文档
├── requirements.txt
└── README.md
```

---

## 5. 核心模块设计

### 5.1 PDF 解析与清洗（`ingest/pdf_parser.py`）

**目标**：将金融研报 PDF 转为干净的 LlamaIndex `Document` 列表，去除页眉页脚噪声，并为 **引用展示** 预留元数据。

**技术方案**：
- 使用 LlamaIndex `SimpleDirectoryReader` + `pymupdf` 后端读取 PDF
- **元数据（与 product.md §5.4 一致）**：
  - **必选**：`source`（文件名或稳定 id），保证 `source_nodes` 可展示「来自哪份文档」。
  - **推荐**：`page_label` / `page`（页码）。若 reader 按页产出多个 `Document`，在 `metadata` 中写入页码；若仅为整份文本，则在 UI/Prompt 中降级为「文档名 + 片段」，并在文档中说明限制。
- 基于规则过滤页眉页脚（检测重复出现在固定位置的文本行）

```python
from llama_index.core import SimpleDirectoryReader

def load_documents(pdf_dir: str) -> list:
    reader = SimpleDirectoryReader(
        input_dir=pdf_dir,
        required_exts=[".pdf"],
        file_metadata=lambda path: {"source": Path(path).name},
    )
    return reader.load_data()
```

实现阶段可改为「按页加载」或自定义 `PDFReader`，确保 `node.metadata` 中尽可能带 **`source` + `page_label`**，供 Gradio 引用区与 Prompt「文档名+页码」一致。

---

### 5.2 分块策略（`ingest/chunker.py`）

消融实验的核心维度，全部使用 LlamaIndex 原生 NodeParser：

#### 策略 A：固定长度分块（基线）

```python
from llama_index.core.node_parser import SentenceSplitter

splitter = SentenceSplitter(chunk_size=512, chunk_overlap=51)  # 10% overlap；消融另设 256 / 0%|20% overlap
nodes = splitter.get_nodes_from_documents(documents)
```

#### 策略 B：语义分块

```python
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3", device="mps")
splitter = SemanticSplitterNodeParser(
    buffer_size=1, breakpoint_percentile_threshold=95, embed_model=embed_model
)
nodes = splitter.get_nodes_from_documents(documents)
```

#### 策略 C：RAPTOR（**P2**，与固定/语义对照）

使用 LlamaIndex 官方 `RaptorPack`，构建递归摘要树：

```python
from llama_index.packs.raptor import RaptorPack

raptor_pack = RaptorPack(
    documents,
    embed_model=embed_model,
    llm=Ollama(model="qwen2.5:7b", ...),   # 用小模型生成摘要
    vector_store=chroma_vector_store,
    similarity_top_k=5,
    mode="collapsed",   # 检索时合并所有层级节点
)
```

RAPTOR 构建层次摘要树：叶节点为原始 chunk，父节点为 LLM 生成的摘要，检索时同时覆盖细节和全局视角。

---

### 5.3 索引构建（`ingest/indexer.py`）

```python
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

def build_index(nodes, collection_name: str) -> VectorStoreIndex:
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
    embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3", device="mps")

    return VectorStoreIndex(
        nodes, storage_context=storage_ctx, embed_model=embed_model
    )
```

---

### 5.4 多路召回（`retrieval/retriever.py`）

全部使用 LlamaIndex 原生检索器，通过 `QueryFusionRetriever` 做 RRF 融合：

```python
from llama_index.core.retrievers import QueryFusionRetriever, BM25Retriever
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank

# 两路召回
bm25_retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=20)
vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=20)

# RRF 融合
fusion_retriever = QueryFusionRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    similarity_top_k=20,
    num_queries=1,   # 不做 query 扩展，只做融合
    mode="reciprocal_rerank",
)

# bge-reranker 精排
reranker = SentenceTransformerRerank(
    model="BAAI/bge-reranker-base", top_n=5
)
```

---

### 5.5 答案生成与多轮对话（`generation/pipeline.py`）

使用 LlamaIndex `CondensePlusContextChatEngine`，内置多轮记忆和引用追踪：

```python
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.ollama import Ollama
from llama_index.core import PromptTemplate

llm = Ollama(model="qwen2.5:72b", base_url="http://localhost:11434",
             temperature=0.1, request_timeout=300.0)

memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

# 自定义金融场景 Prompt
qa_prompt = PromptTemplate(
    "你是一位专业的金融分析师助手。请根据以下研报片段回答问题。\n"
    "要求：仅基于提供内容作答；信息不足时明确说明；末尾标注引用来源（文档名+页码）。\n\n"
    "研报片段：\n{context_str}\n\n"
    "问题：{query_str}\n\n回答："
)

chat_engine = CondensePlusContextChatEngine.from_defaults(
    retriever=fusion_retriever,
    memory=memory,
    llm=llm,
    node_postprocessors=[reranker],
    context_prompt=qa_prompt,
    verbose=True,
)

# 调用：返回 response.response（答案）和 response.source_nodes（引用）
response = chat_engine.chat("该公司的主要风险有哪些？")
```

---

### 5.6 知识图谱增强检索（可选 P2，`retrieval/kg_retriever.py`）

用户在 UI 中勾选"启用知识图谱"后，系统使用 LlamaIndex `PropertyGraphIndex` 从文档中抽取实体与关系，构建本地知识图谱，并将 KG retriever 加入多路召回。

**构建知识图谱**：

```python
from llama_index.core import PropertyGraphIndex
from llama_index.core.indices.property_graph import (
    SimpleLLMPathExtractor,
    ImplicitPathExtractor,
)

def build_kg_index(documents, llm, embed_model) -> PropertyGraphIndex:
    return PropertyGraphIndex.from_documents(
        documents,
        llm=llm,                          # 用 Qwen2.5-7B 抽取实体，节省时间
        embed_model=embed_model,
        kg_extractors=[
            SimpleLLMPathExtractor(llm=llm, max_paths_per_chunk=10),
            ImplicitPathExtractor(),      # 基于句法规则的隐式关系
        ],
        show_progress=True,
    )
```

**三路融合检索（启用 KG 时）**：

```python
kg_retriever = kg_index.as_retriever(
    include_text=True,
    similarity_top_k=10,
)

fusion_retriever = QueryFusionRetriever(
    retrievers=[bm25_retriever, vector_retriever, kg_retriever],
    similarity_top_k=20,
    num_queries=1,
    mode="reciprocal_rerank",
)
```

**适用场景**：多文档跨报告对比、实体关系追踪（如"A公司的主要竞争对手在其他报告中的评级"）。

**注意**：KG 构建需要大量 LLM 调用，建议用 Qwen2.5-7B 构建，构建完成后持久化复用。

---

### 5.7 文档概览与建议问题（`generation/overview.py`，P1）

对标 NotebookLM 的 Notebook Guide，文档上传并建索引后自动触发。

```python
from llama_index.core import SummaryIndex
from llama_index.core import PromptTemplate

def generate_overview(nodes, llm) -> dict:
    summary_index = SummaryIndex(nodes)
    query_engine = summary_index.as_query_engine(llm=llm)

    overview = query_engine.query(
        "请用3-5句话总结这批研报的核心主题、覆盖公司及主要结论。"
    )
    questions = query_engine.query(
        "基于这批研报内容，生成8个用户最可能提问的问题，每行一个，用数字编号。"
    )
    return {
        "overview": str(overview),
        "suggested_questions": str(questions),
    }
```

生成结果展示在 UI 左侧面板，建议问题可点击直接填入对话框。

---

### 5.8 文档管理（增量增删，P1）

支持单篇文档的添加与移除，无需重建整个索引。

```python
from llama_index.core import VectorStoreIndex

# 增量添加单篇文档
def add_document(index: VectorStoreIndex, pdf_path: str, embed_model):
    new_docs = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
    for doc in new_docs:
        index.insert(doc)

# 移除单篇文档（按 doc_id）
def remove_document(index: VectorStoreIndex, doc_id: str):
    index.delete_ref_doc(doc_id, delete_from_docstore=True)
```

UI 中展示已加载文档列表，每行显示文件名 + 删除按钮。

---

### 5.9 多源类型支持（网页，P2）

```python
from llama_index.readers.web import SimpleWebPageReader

def load_from_url(url: str) -> list:
    reader = SimpleWebPageReader(html_to_text=True)
    return reader.load_data(urls=[url])
```

UI 中在上传 PDF 旁边增加"输入网页 URL"文本框，加载后与 PDF 文档统一进入同一索引。

---

### 5.10 Gradio UI（`ui/app.py`，P0 最小可演示 + P1 完整体验）

**界面布局**：
```
┌──────────────────────────────────────────────────────────┐
│  左侧面板                  │  右侧主区域                  │
│                            │                              │
│  [上传 PDF / 输入 URL]     │  [选择分块策略] [选择模型]   │
│  已加载文档列表：          │  [☐ 启用知识图谱] [构建 KG]  │
│  > report_A.pdf  [删除]   ├──────────────────────────────┤
│  > report_B.pdf  [删除]   │                              │
│                            │  对话区域（流式输出）        │
│  ── 文档概览 ──            │                              │
│  [自动生成摘要文本]        ├──────────────────────────────┤
│                            │  引用来源（source_nodes）    │
│  ── 建议问题 ──            │  > [report_A.pdf P.12]      │
│  1. [点击填入对话框]       │    "...原文片段..."          │
│  2. [点击填入对话框]       │                              │
│  ...                       │                              │
└──────────────────────────────────────────────────────────┘
```

**关键功能**：
- 文件上传 / URL 输入后调用 `build_index()` + `generate_overview()`
- 文档列表支持单篇删除，调用 `remove_document()`
- 建议问题点击后自动填入对话输入框
- 流式输出：`chat_engine.stream_chat()` + Gradio `yield`
- 引用展示：`node.metadata["source"]` +（若有）`page_label` + `node.get_content()`
- KG 开关：勾选后触发 `build_kg_index()`，检索自动加入第三路

---

### 5.11 问答核心细节（`generation/pipeline.py` + `generation/prompt.py`）

#### 5.11.1 Prompt 设计

系统使用两套 Prompt，分别对应不同阶段：

**① 问题改写 Prompt（condense prompt）**

`CondensePlusContextChatEngine` 在每轮对话前，先用此 prompt 将「历史对话 + 当前问题」压缩为一个独立的检索查询，消除指代歧义（如"它"、"该公司"）。

```python
from llama_index.core import PromptTemplate

CONDENSE_PROMPT = PromptTemplate(
    "以下是对话历史和用户的最新问题。\n"
    "请将最新问题改写为一个**独立、完整、无指代歧义**的检索查询，"
    "使其不依赖历史对话也能被理解。\n"
    "若最新问题本身已足够独立，直接返回原问题。\n\n"
    "对话历史：\n{chat_history}\n\n"
    "最新问题：{question}\n\n"
    "改写后的查询："
)
```

**② 答案生成 Prompt（context prompt）**

检索完成后，将 Top-5 节点拼入上下文，要求模型严格基于证据作答，并在末尾输出结构化引用。

```python
QA_PROMPT = PromptTemplate(
    "你是一位专业的金融分析师助手，只能基于下方提供的研报片段回答问题。\n\n"
    "【规则】\n"
    "1. 仅使用研报片段中的信息作答，不得引入外部知识。\n"
    "2. 若片段中信息不足以回答问题，输出固定格式：\n"
    "   「根据已加载的研报，暂无足够信息回答该问题。」\n"
    "3. 答案末尾必须附引用，格式：【来源：{文档名} 第{页码}页】；无页码时写文档名。\n"
    "4. 禁止编造数据、评级或预测结论。\n\n"
    "研报片段：\n{context_str}\n\n"
    "问题：{query_str}\n\n"
    "回答："
)
```

两套 prompt 通过 `update_prompts()` 注入 chat engine：

```python
chat_engine.update_prompts({
    "condense_question_prompt": CONDENSE_PROMPT,
    "context_prompt": QA_PROMPT,
})
```

---

#### 5.11.2 多轮对话上下文压缩

`CondensePlusContextChatEngine` 的两阶段机制：

```
第 N 轮用户输入
       │
       ▼
[Stage 1] condense_question_prompt
  输入：chat_history（最近 K 轮）+ 当前问题
  输出：独立检索查询 q'
       │
       ▼
[Stage 2] fusion_retriever(q') → reranker → Top-5 nodes
       │
       ▼
[Stage 3] context_prompt(context_str=Top-5, query_str=q')
  输出：答案 + source_nodes
```

`ChatMemoryBuffer` 控制历史窗口大小，防止 context 爆炸：

```python
from llama_index.core.memory import ChatMemoryBuffer

# token_limit 控制传入 condense prompt 的历史长度
# 超出后自动截断最早的轮次（FIFO）
memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
```

**注意**：`token_limit` 仅限制传入 condense prompt 的历史，不影响当前轮的检索上下文长度。建议根据 Qwen2.5 的实际 context window 调整（7B 约 32K，72B 约 128K）。

---

#### 5.11.3 答案生成完整流程

```
用户输入 q
    │
    ├─[有历史]─→ condense_question_prompt → 改写为 q'
    └─[无历史]─→ q' = q
         │
         ▼
    fusion_retriever(q')
    BM25(top-20) + Vector(top-20) → RRF → top-20
    [可选] KG(top-10) 加入融合
         │
         ▼
    SentenceTransformerRerank → top-5 nodes
         │
         ▼
    拒答检测（见 §5.11.4）
         │
    ┌────┴────┐
  信息不足    信息充足
    │            │
    ▼            ▼
  固定拒答语   QA_PROMPT(context_str, query_str)
                 │
                 ▼
           Ollama(qwen2.5:72b) 流式生成
                 │
                 ▼
           response.response + response.source_nodes
                 │
                 ▼
           Gradio 展示答案 + 引用卡片
```

---

#### 5.11.4 拒答机制

当检索结果与问题相关性不足时，应拒绝作答而非幻觉生成。采用「可选检索过滤 + Prompt / UI」组合：

**层 1（可选）：检索后过滤——区分两种分数，避免混用**

- **`SimilarityPostprocessor(similarity_cutoff=…)`** 使用的是 **query–chunk 的向量相似度**（与 embedding 空间一致），**不是** cross-encoder reranker 的输出分数。适合放在 **rerank 之前** 做粗剪枝（省算力），阈值需单独调参。  
- **Rerank 分数阈值**：若实现对 `SentenceTransformerRerank` 做了包装、能在 node 上拿到 **cross-encoder 分**，可在 **rerank 之后** 设 `top1_score < τ` 则拒答；若当前 LlamaIndex 版本**未暴露**该分数，则**不要**误用 `SimilarityPostprocessor` 冒充 rerank 阈值，可跳过本层，依赖层 2。

```python
from llama_index.core.postprocessor import SimilarityPostprocessor

# 示例：仅作「向量相似度」粗过滤（在 rerank 前）；cutoff 与 embedding 模型相关，需实验标定
similarity_prune = SimilarityPostprocessor(similarity_cutoff=0.2)
node_postprocessors = [similarity_prune, reranker]  # 顺序：先向量阈值再精排
```

若启用粗过滤且过滤后节点数为 0，可直接返回拒答语，不进入 LLM。

**层 2：Prompt 内置拒答指令**

即使有节点通过过滤，QA_PROMPT 中的规则 2 要求模型在信息不足时输出固定格式：

```
「根据已加载的研报，暂无足够信息回答该问题。」
```

UI 层检测到此固定前缀时，不展示引用卡片，避免误导用户。

---

#### 5.11.5 数据库设计（ChromaDB）

系统使用 ChromaDB 作为唯一持久化向量存储，按**分块策略**分 collection，支持消融实验并行对比：

```
chroma_db/
├── collection: fin_fixed_512      # Fixed-512 基线
├── collection: fin_fixed_256      # Fixed-256 消融
├── collection: fin_semantic       # 语义分块
└── collection: fin_raptor         # RAPTOR（P2）
```

**与增量文档管理（P0/P1）的约定**：Gradio 日常使用中**只维护当前 UI 所选策略**对应的一个 collection，避免每加一篇 PDF 就同步更新多套 collection。需跑 **§6.1 多策略对比** 时，用 **离线脚本 / `ablation.py`** 按策略批量重建各 collection，保证评测可复现。

每个 collection 的 document metadata schema：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | str | 原始文件名，如 `report_A.pdf` |
| `page_label` | str | 页码（若 reader 支持），如 `"12"` |
| `doc_id` | str | LlamaIndex 文档级 id，用于增量删除 |
| `node_id` | str | chunk 级 id，ChromaDB 主键 |
| `chunk_strategy` | str | `fixed_512` / `semantic` / `raptor` |

**collection 选择逻辑**（`indexer.py`）：

```python
COLLECTION_MAP = {
    "fixed_512": "fin_fixed_512",
    "fixed_256": "fin_fixed_256",
    "semantic":  "fin_semantic",
    "raptor":    "fin_raptor",
}

def get_or_build_index(strategy: str, nodes=None) -> VectorStoreIndex:
    collection_name = COLLECTION_MAP[strategy]
    chroma_client = chromadb.PersistentClient(path=config.chroma.persist_dir)
    collection = chroma_client.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_ctx = StorageContext.from_defaults(vector_store=vector_store)

    if collection.count() > 0 and nodes is None:
        # 已有索引，直接加载
        return VectorStoreIndex.from_vector_store(
            vector_store, embed_model=embed_model
        )
    # 首次构建
    return VectorStoreIndex(nodes, storage_context=storage_ctx, embed_model=embed_model)
```

KG 持久化单独配置：

```yaml
# config.yaml 新增
kg:
  persist_dir: ./kg_store
```

---

#### 5.11.6 Function Calling（工具调用，**P3 / 时间充裕**）

**优先级说明**：本小节**不在** product.md 的 P0–P2 交付范围内；与 `CondensePlusContextChatEngine` 双线并存会增加联调与测试成本，默认**不实现**；仅在与产品负责人对齐后作为加分项启动。

使用 LlamaIndex `FunctionTool` + `ReActAgent` 为系统扩展结构化查询能力，让 LLM 在需要时主动调用工具，而非仅依赖检索上下文。

**设计原则**：工具调用作为 RAG 的**补充**，不替代检索；仅在用户问题明确需要元数据列表或显式对比流程时触发。

**工具定义**（`generation/tools.py`）：

```python
from llama_index.core.tools import FunctionTool

def list_loaded_documents() -> str:
    """返回当前已加载的文档列表（文件名 + 页数）。"""
    # 从 ChromaDB metadata 中聚合 source 字段
    ...

def get_document_summary(doc_name: str) -> str:
    """返回指定文档的摘要（从 overview 缓存读取）。"""
    ...

def compare_ratings(doc_a: str, doc_b: str, company: str) -> str:
    """对比两份研报中对指定公司的评级结论。"""
    # 在对应 collection 中按 source 过滤，检索评级相关片段
    ...

list_docs_tool    = FunctionTool.from_defaults(fn=list_loaded_documents)
get_summary_tool  = FunctionTool.from_defaults(fn=get_document_summary)
compare_tool      = FunctionTool.from_defaults(fn=compare_ratings)
```

**Agent 集成**（可选模式，UI 中提供"Agent 模式"开关）：

```python
from llama_index.core.agent import ReActAgent

agent = ReActAgent.from_tools(
    tools=[list_docs_tool, get_summary_tool, compare_tool],
    llm=llm,
    verbose=True,
    max_iterations=5,
)
```

**适用场景**：

| 用户问题类型 | 触发工具 |
|-------------|---------|
| "你加载了哪些文档？" | `list_loaded_documents` |
| "给我看看 report_A 的摘要" | `get_document_summary` |
| "report_A 和 report_B 对 XX 公司的评级一致吗？" | `compare_ratings` |
| "该公司 2023 年营收是多少？" | 不触发工具，走 RAG 检索 |

**注意**：`ReActAgent` 模式与 `CondensePlusContextChatEngine` 是两条独立路径，UI 中通过"普通问答 / Agent 模式"切换，不混用。

---

## 6. 消融实验设计

### 6.1 实验矩阵

**主评测基线（P0，与 §8 开发顺序一致）**：**Fixed-512**、**overlap=10%**、**BM25 + 向量 + RRF 融合**、**bge-reranker 精排**、评测用 **Qwen2.5-72B**（资源不足时 **全班统一改用 7B**，并在报告中注明）。  
**RAPTOR、GraphRAG、网页源** 为 **P2**：仅在对应实验中作为变量或附加行出现，**不作为**上述主基线的默认固定条件。

| 实验 | 变量 | 固定条件 |
|------|------|---------|
| Chunking 消融 | Fixed-256 / Fixed-512 / Semantic；另可增 **RAPTOR（P2）** 作独立对照 | 主基线检索栈（多路 + RRF + rerank）与评测 LLM；**overlap=10%**（RAPTOR 行按 RAPTOR 惯例构建，overlap 不适用处需在报告中说明） |
| Overlap 消融 | 0% / 10% / 20% | **Fixed-512**、主基线检索栈、同一评测 LLM |
| 召回策略消融 | 单路向量 / BM25+向量融合 / 融合 + rerank | **Fixed-512**、overlap=10%、同一评测 LLM |
| 模型消融 | Qwen2.5-7B vs Qwen2.5-72B | **Fixed-512**、overlap=10%、主基线检索栈（多路 + RRF + rerank） |
| GraphRAG 消融（P2） | KG 关闭 vs KG 开启（三路融合） | **Fixed-512**、overlap=10%、主基线检索栈 + 第三路 KG、评测 LLM；**仅跨文档对比类问题**（测试集第三类） |

### 6.2 评估指标（RAGAS + 引用准确性）

#### 6.2.1 RAGAS（自动化）

用 LlamaIndex `RagasEvaluator` 或直接对接 `ragas` 库，以本地 **Qwen2.5-72B**（或资源不足时的 **7B**）作为 judge model：

```python
from ragas import evaluate
from ragas.metrics import context_recall, context_precision, faithfulness, answer_relevancy
from ragas.llms import LlamaIndexLLMWrapper
from ragas.embeddings import LlamaIndexEmbeddingsWrapper

result = evaluate(
    dataset=ragas_dataset,
    metrics=[context_recall, context_precision, faithfulness, answer_relevancy],
    llm=LlamaIndexLLMWrapper(llm),           # 本地 Qwen2.5-72B
    embeddings=LlamaIndexEmbeddingsWrapper(embed_model),
)
```

| 指标 | 含义 |
|------|------|
| Context Recall | 检索到的相关内容比例 |
| Context Precision | 检索结果的精确率 |
| Faithfulness | 答案是否基于检索内容，无幻觉 |
| Answer Relevancy | 答案与问题的相关性 |

上述指标**不等价**于 product.md 中的 **Citation Accuracy**，需补充下列闭环。

#### 6.2.2 引用准确性（Citation Accuracy）

与 **product.md §8.2** 一致，建议：

1. **自动代理**：对每条答案，解析或结构化保存「引用 → 对应 `source_node` id」；检查引用文本是否被该 node 内容**包含**或与该 node 有高于阈值的相似度（如 token overlap）。用于批量失败检测。  
2. **人工抽检**：每类任务至少抽 **N** 题（如 5），核对引用是否与原文一致、是否存在未引用断言；**N** 与结果写入实验报告。

评估脚本可放在 `src/evaluation/citation_audit.py`（与 `ragas_eval.py` 并列）。

### 6.3 测试集构建

覆盖四类问题（每类 10 题，共 40 题）：

| 类型 | 示例 |
|------|------|
| 信息提取 | "该公司 2023 年营收增长率是多少？" |
| 总结 | "总结该报告对行业前景的核心判断。" |
| 跨文档对比 | "两份报告对该公司评级是否一致？" |
| 风险识别 | "报告中提到的主要风险因素有哪些？" |

---

## 7. 依赖与环境

### 7.1 核心依赖

```
# requirements.txt
# LlamaIndex 核心
llama-index-core>=0.10.0
llama-index-vector-stores-chroma
llama-index-embeddings-huggingface
llama-index-llms-ollama
llama-index-retrievers-bm25
llama-index-packs-raptor          # 仅启用 RAPTOR（P2）时需要
llama-index-readers-web           # 仅网页入索引（P2）时需要

# 向量库
chromadb>=0.5.0

# PDF 解析
pymupdf>=1.23.0

# Reranker：`SentenceTransformerRerank` 依赖 sentence-transformers（与 BAAI/bge-reranker-base 配合）
sentence-transformers>=2.2.0

# 可选：FlagEmbedding 相关能力若单独使用再引入
# FlagEmbedding>=1.2.0

# 评估
ragas>=0.2.0
datasets

# UI
gradio>=4.0.0

# 工具
pyyaml
html2text
```

### 7.2 Ollama 模型安装

```bash
# 安装 Ollama
brew install ollama

# 拉取模型（大内存机器可跑 72B 量化；否则以 7B 为主）
ollama pull qwen2.5:72b
ollama pull qwen2.5:7b
```

### 7.3 配置文件（`configs/config.yaml`）

```yaml
llm:
  strong_model: qwen2.5:72b
  weak_model: qwen2.5:7b
  ollama_base_url: http://localhost:11434
  temperature: 0.1
  max_tokens: 2048

embedding:
  model: BAAI/bge-m3
  device: mps          # Apple Silicon；无 MPS 时用 cpu / cuda

reranker:
  model: BAAI/bge-reranker-base
  top_k: 5

chunking:
  default_strategy: fixed              # P0：fixed；raptor 为 P2
  fixed_chunk_size: 512              # 开发基线；消融含 256
  fixed_overlap: 0.1
  raptor_max_levels: 3
  raptor_summary_model: qwen2.5:7b   # 用小模型生成摘要，节省时间

retrieval:
  bm25_top_k: 20
  vector_top_k: 20
  final_top_k: 5

chroma:
  persist_dir: ./chroma_db

evaluation:
  test_set_path: ./data/test_set.json
  judge_model: qwen2.5:72b
```

---

## 8. 开发分工

| 模块 | 主要任务 | 优先级 |
|------|---------|--------|
| ingest | PDF 解析、清洗、**Fixed/Semantic 分块**、Chroma 索引构建 | P0 |
| ingest | **RAPTOR**、**网页 URL** 入索引 | P2 |
| retrieval | 多路召回 + reranker；**KG retriever** | P0 / P2（KG） |
| generation | Ollama 封装 + Prompt + Pipeline | P0 |
| generation | 文档概览 + 建议问题 | P1 |
| evaluation | 测试集 + **RAGAS** + **引用核查脚本** | P1 |
| ui | Gradio：对话 + 引用展示 + 策略切换 | P0 |
| ui | 文档管理 + 概览面板 | P1 |
| notebooks | 消融实验分析 | P2 |

**开发顺序建议**（与 product.md §5.2 一致）：
1. 先跑通最小 pipeline（固定分块 → 向量检索 → Qwen2.5-7B 生成 + 基础引用）
2. 接入 Gradio UI，验证端到端流程
3. 加入 BM25 + Fusion + rerank；跑 chunk / overlap / 模型消融
4. 加入文档管理、概览与建议问题、RAGAS + 引用抽检流程
5. **P2**：RAPTOR、网页源、GraphRAG
6. 汇总消融与报告

---

## 9. 关键风险与应对

| 风险 | 应对 |
|------|------|
| RAPTOR 构建时间长 | 预先构建索引并持久化，UI 加载时直接读取；`indexer.py` 需明确区分"首次构建"和"加载已有索引"两条路径 |
| Qwen2.5-72B 推理慢 | 演示时用 7B，实验结果用 72B 离线跑 |
| 金融 PDF 表格解析差 | 当前阶段跳过表格，仅处理文本（在 Non-goals 范围内） |
| RAGAS 需要 LLM 评估 | 用本地 Qwen2.5-72B 作为 judge model，无需 OpenAI |
| KG 构建耗时 | 用 Qwen2.5-7B 构建，完成后持久化，不在请求路径上重建；在 `config.yaml` 增加 `kg.persist_dir`，`kg_retriever.py` 实现 load-or-build 逻辑 |
| 概览生成慢 | 异步触发（`asyncio` 或 Gradio 后台线程），UI 显示 loading 状态，不阻塞对话功能 |
| BM25 与向量索引节点不同步 | 增量添加/删除文档时，`BM25Retriever` 的内存节点列表需与 ChromaDB 同步重建；在 `indexer.py` 的 `add_document()` / `remove_document()` 中统一维护节点列表 |
| 多 collection 与日常增量冲突 | 日常 UI 只维护**当前策略**的 collection；多策略消融依赖**离线重建**（见 §5.11.5），避免每次上传同步 N 套索引 |
| Agent / 工具调用范围蔓延 | **P3**：默认不做；若做则单独排期与测试，不与 P0 对话主路径耦合 |
