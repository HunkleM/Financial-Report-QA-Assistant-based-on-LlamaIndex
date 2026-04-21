# 📈 Insight: 机构级金融研报智能工作台

![Status](https://img.shields.io/badge/Status-Beta-brightgreen)
![LLM](https://img.shields.io/badge/LLM-Qwen2.5--7B-blue)
![RAG](https://img.shields.io/badge/Framework-LlamaIndex-purple)

**Insight** 是一个深度对标 **NotebookLM** 体验的 RAG (检索增强生成) 分析工作台，专为处理复杂排版的金融研报 (PDF) 而设计。

系统从底层解析、索引架构到前台沉浸式交互，经过了全方位的打磨。它不仅能“找到原文”，还能“读懂表格”、“总结宏观”并“合成知识”。

---

## ✨ 核心特性 (Features)

### 1. 数据底座 (Deep Parsing & Indexing)
- **云端解析 (LlamaParse)**：智能穿透复杂 PDF 排版，完美提取财务表格、双栏文本并转化为高保真 Markdown。
- **语义分块 (Semantic Chunking)**：抛弃生硬的按字数切断，基于 BGE 句向量识别语义边界，保持段落与表格的完整逻辑。
- **混合检索 (Hybrid RRF)**：同时利用 `BM25` (关键词) 与 `bge-m3` (语义) 进行双路召回，使用 RRF (倒数排序融合) 算法合并。
- **二次精排 (Reranking)**：引入 `bge-reranker-base` 过滤噪音，确保送入 LLM 的都是最高质量的证据。

### 2. 认知升级 (Macro-Vision)
- **RAPTOR 树状摘要**：系统在入库时自底向上构建层次摘要树 (Level 1~3)。无论问及细枝末节，还是宏观行业趋势，都能被准确命中。

### 3. 沉浸式工作台 (NotebookLM-like UX)
- **三分栏设计**：左侧数据面板、中间对话与灵感区域、右侧原生 PDF 阅读器。
- **证据链联动 (Interactive Citations)**：AI 生成的每一个数据都会附带来源卡片。点击引用标签，右侧 PDF 预览区将**瞬间跳转至源文档对应的页码**。
- **跨文档知识合成**：一键生成“多文档对比分析表格”，并可将其无缝存入“分析师灵感库 (Notepad)” 以供后续组装研究报告。

---

## 🚀 快速启动

### 1. 硬件配置要求
为了流畅运行本地大模型与 RAG 检索链路，建议您的设备满足以下要求：
*   **最小配置**：Apple Silicon (M1/M2) 或 Intel/AMD CPU + 16GB 内存。*(仅能勉强运行 7B 量化模型，推理速度较慢，不推荐用于深度跨文档分析。)*
*   **推荐配置**：Apple Silicon (M1/M2/M3 Max/Pro) 配合至少 32GB 统一内存，或搭载 NVIDIA GPU (如 RTX 3060/4060 12GB+ VRAM) 的 Windows/Linux 设备。

### 2. 本地模型服务 (Ollama)
本项目所有核心分析均在本地计算，保护金融数据隐私。请先安装 [Ollama](https://ollama.com/) 客户端。

```bash
# 下载并启动 Qwen2.5 7B 对话与摘要模型
ollama pull qwen2.5:7b
```

### 3. 配置高保真解析密钥
在项目根目录创建 `.env` 文件，填入您的 [LlamaCloud API Key](https://cloud.llamaindex.ai/) 以激活强大的财务表格解析能力：
```env
LLAMA_CLOUD_API_KEY="llx-xxxxxxxxxxxxxxxx"
```
*(注：如果不配置此项，系统将降级使用本地基础解析器，面对复杂财务报表时可能会出现数据乱序。)*

### 4. 安装依赖与启动
```bash
# 推荐在虚拟环境中执行
pip install -r requirements.txt

# 启动工作台界面
python -m src.ui.app
```
打开浏览器访问 `http://localhost:7860`。

---

## 🛠️ 架构白皮书

如果您希望深入了解本系统的技术细节（如 RAPTOR 的实现机制、检索链路的数据流向等），请参阅我们详细的 [技术规格文档 (Technical Specification)](docs/specs/technical_specification.md)。

## 🧪 自动化评估
内置集成 `Ragas` 评估框架与正则级的 `Citation Audit` 工具。
运行基准测试：
```bash
python -m src.evaluation.ragas_eval
```
