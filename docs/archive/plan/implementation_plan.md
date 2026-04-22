# 实施计划：金融研报问答系统 (P0 + P1)

## 1. 目标 (Objective)
基于产品需求文档 (`product.md`) 和技术设计文档 (`technical_design.md`)，构建一个基于 LlamaIndex 的金融研报问答系统。
本次实施聚焦于 **P0（最小可演示版本）** 与 **P1（进阶功能与评估）**，并针对 Apple Silicon (MPS) 硬件与 `uv` 依赖管理进行优化。

## 2. 关键文件与目录结构 (Key Files & Directory Structure)
```
CS6496-group/
├── data/                        # 测试 PDF 文档
├── configs/
│   └── config.yaml              # 核心配置（模型、路径、参数）
├── src/
│   ├── ingest/                  # 接入：解析、分块、索引
│   ├── retrieval/               # 检索：多路召回、精排
│   ├── generation/              # 生成：LLM、Prompt、Pipeline
│   ├── evaluation/              # 评估：RAGAS、引用核查
│   └── ui/                      # 界面：Gradio Web UI
├── tests/                       # 单元与集成测试
├── pyproject.toml               # uv 依赖配置
└── README.md
```

## 3. 环境准备
*   **依赖管理**：使用 `uv` 初始化环境并同步依赖。
*   **本地模型 (Ollama)**：
    *   `ollama pull qwen2.5:7b` (对话/生成)
*   **本地模型 (HuggingFace)**：
    *   `BAAI/bge-m3` (Embedding，MPS 加速)
    *   `BAAI/bge-reranker-base` (Reranker，MPS 加速)

## 4. 实施阶段拆解

### 阶段 1：项目初始化 (Setup)
*   [ ] 创建项目骨架目录及 `__init__.py`。
*   [ ] 编写 `configs/config.yaml` 记录全局配置。
*   [ ] 使用 `uv init` 初始化，安装 `llama-index` 相关核心库。

### 阶段 2：数据接入与索引 (Ingestion - P0)
*   [ ] 实现 `pdf_parser.py`：使用 `pymupdf` 提取文本，并注入 `source` 和 `page_label` 元数据。
*   [ ] 实现 `chunker.py`：配置 `SentenceSplitter` (512 tokens, 10% overlap)。
*   [ ] 实现 `indexer.py`：构建基于 ChromaDB 的持久化索引。

### 阶段 3：多路检索与精排 (Retrieval - P0)
*   [ ] 实现 `retriever.py`：构建 BM25 与 Vector 融合检索器 (RRF)。
*   [ ] 实现 `reranker.py`：配置 BGE Reranker 进行 Top-N 精排。

### 阶段 4：答案生成 (Generation - P0)
*   [ ] 实现 `llm_backend.py`：对接本地 Ollama 服务。
*   [ ] 实现 `prompt.py`：编写金融场景专用 Prompt（含引用要求与拒答逻辑）。
*   [ ] 实现 `pipeline.py`：封装 `CondensePlusContextChatEngine`。

### 阶段 5：用户界面 (UI - P0)
*   [ ] 实现 `app.py`：使用 Gradio 构建双栏布局，支持 PDF 上传、对话展示及引用卡片显示。

### 阶段 6：进阶功能 (P1)
*   [ ] **文档管理**：支持单篇文档的动态增删，无需重建全局索引。
*   [ ] **文档概览**：利用 `SummaryIndex` 自动生成文档摘要与建议问题。

### 阶段 7：自动化评估 (Evaluation - P1)
*   [ ] 构建包含 40 个样本的测试集 `test_set.json`。
*   [ ] 实现 `ragas_eval.py`：运行 RAGAS 自动化指标评估。
*   [ ] 实现 `citation_audit.py`：通过自动抽检验证引用准确性。

## 5. 验证标准
*   **P0 验收**：能够上传一份研报，针对其内容进行问答，并准确显示来源文档和页码。
*   **P1 验收**：能够删除已加载文档；能够点击“建议问题”快速提问；RAGAS 指标有基线记录。