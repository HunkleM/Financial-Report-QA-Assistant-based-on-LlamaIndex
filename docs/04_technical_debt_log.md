# 📝 技术债与优化日志 (Technical Debt & Refactoring Log)

> **操作规范**:
> 在敏捷开发（MVP 优先）的理念下，为了抢占项目进度，我们必然会在代码中留下一些不够优雅或缺乏扩展性的“技术债”。
> 任何开发者在编写或审查代码时发现非致命的架构缺陷，**不得阻塞当前主线开发**，必须将缺陷记录于此。待核心里程碑完成后，再集中清理本日志。

---

## 1. 基础配置模块 (`src/utils/config.py`)

- **[非致命] 类型安全缺失 (Lack of Type Safety)**
  - **现状**: `load_config()` 返回的是松散的 `Dict[str, Any]`。在其他模块调用如 `GLOBAL_CONFIG["chunking"]["chunk_size"]` 时，IDE 无法提供类型推断和代码补全，容易引发运行时的拼写错误 (KeyError)。
  - **重构建议**: 引入 `Pydantic` 或 `dataclass` 定义严格的配置 Schema。实现 `GLOBAL_CONFIG.chunking.chunk_size` 的强类型点语法调用。
  - **状态**: ⚪ 待处理 (Pending)

- **[非致命] 缺少环境变量覆盖机制 (No Env Var Overrides)**
  - **现状**: 所有配置硬编码在 `config.yaml` 文件中。如果需要在不同环境（如从 Mac Studio 迁移到云端服务器）临时修改 `OLLAMA_BASE_URL` 等参数，修改文件极不方便。
  - **重构建议**: 在解析 YAML 后，增加一层环境变量覆盖逻辑（例如优先读取 `os.environ.get("OLLAMA_BASE_URL")`）。
  - **状态**: ⚪ 待处理 (Pending)

- **[边缘场景] 空文件容错处理缺陷**
  - **现状**: 若 `config.yaml` 文件存在但内容为空，`yaml.safe_load(f)` 将返回 `None`。这会导致系统在后续尝试读取字典键值时抛出 `TypeError: 'NoneType' object is not subscriptable`，错误堆栈不够友好。
  - **重构建议**: 增加 `if config is None: raise ValueError("配置文件为空")` 的显式防御性检查。
  - **状态**: ⚪ 待处理 (Pending)

---

## 2. 检索模块 (`src/retrieval/retriever.py`)

- **[非致命] ChromaDB 底层强耦合 (Vector Store Coupling)**
  - **现状**: 为了在内存中构建 BM25 词频矩阵，代码通过 `index.storage_context.vector_store.client.get()` 暴力反向提取了所有的底层文本。这个 `client.get()` 是 ChromaDB 专属的 API。
  - **隐患**: 这省去了维护 `docstore.json` 的麻烦，并在当前原型阶段完美运行。但如果未来项目需要迁移到 Milvus 或 Qdrant 等其他向量数据库，这行代码将直接崩溃。
  - **重构建议**: (P3 选做) 如果要追求企业级普适性，应使用 LlamaIndex 官方的 `SimpleDocumentStore` 进行文本的持久化与读取分离，从而与底层向量库解耦。
  - **状态**: ⚪ 待处理 (Pending)