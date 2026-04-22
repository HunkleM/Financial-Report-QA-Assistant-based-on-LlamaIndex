from typing import List
from llama_index.core.schema import Document, BaseNode
from llama_index.core.node_parser import SentenceSplitter

# 导入 Phase 2 需要的语义分块组件 (后续会用到)
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 导入全局配置
from src.utils.config import GLOBAL_CONFIG

def get_baseline_nodes(documents: List[Document]) -> List[BaseNode]:
    """
    【Phase 1 基线策略】
    使用传统的固定长度句子级切分。
    参数由 config.yaml 严格控制 (如 chunk_size: 256, chunk_overlap: 25)。
    """
    chunk_size = GLOBAL_CONFIG["chunking"].get("chunk_size", 256)
    chunk_overlap = GLOBAL_CONFIG["chunking"].get("chunk_overlap", 25)
    
    print(f"✂️ [Baseline] 启动固定分块策略 (Size: {chunk_size}, Overlap: {chunk_overlap})...")
    
    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    
    # 将 Document 列表切分为细粒度的 Node 列表
    nodes = splitter.get_nodes_from_documents(documents)
    
    # 打上内部溯源标签，方便后期调试和 UI 区分策略
    for node in nodes:
        node.metadata["chunk_strategy"] = f"fixed_{chunk_size}"
        
    return nodes

def get_semantic_nodes(documents: List[Document]) -> List[BaseNode]:
    """
    【Phase 2 高级策略 - 语义分块】
    使用真正的自适应语义分块。利用 BGE-M3 计算句间相似度。
    只有当上下句的语义发生突变（低于 95% 相似度）时才切分，保证财报分析逻辑不断层。
    """
    buffer_size = GLOBAL_CONFIG["chunking"].get("semantic_buffer_size", 1)
    threshold = GLOBAL_CONFIG["chunking"].get("semantic_breakpoint_percentile", 95)
    
    print(f"✂️ [Advanced] 启动自适应语义分块策略 (Buffer: {buffer_size}, Threshold: {threshold}%)...")
    print(f"🧠 [Embedding] 正在加载 BGE-M3 模型用于计算断点 (硬件加速: {GLOBAL_CONFIG['embedding']['device']})...")
    
    # 1. 初始化高精度稠密向量提取模型用于切分
    embed_model = HuggingFaceEmbedding(
        model_name=GLOBAL_CONFIG["embedding"]["model"], 
        device=GLOBAL_CONFIG["embedding"]["device"]
    )
    
    # 2. 初始化语义分块器
    splitter = SemanticSplitterNodeParser(
        buffer_size=buffer_size, 
        breakpoint_percentile_threshold=threshold, 
        embed_model=embed_model
    )
    
    # 3. 执行自适应切分 (此过程在 M3 Ultra 上会密集调用 Neural Engine)
    print("⏳ 正在进行密集的句子级余弦相似度计算，请稍候...")
    nodes = splitter.get_nodes_from_documents(documents)
    
    # 4. 打上内部溯源标签
    for node in nodes: 
        node.metadata["chunk_strategy"] = "semantic"
        
    return nodes

def get_nodes(documents: List[Document]) -> List[BaseNode]:
    """
    通用入口：根据 config.yaml 自动分发切块策略。
    """
    strategy = GLOBAL_CONFIG["chunking"].get("strategy", "fixed")
    
    if strategy == "semantic":
        return get_semantic_nodes(documents)
    else:
        return get_baseline_nodes(documents)

if __name__ == "__main__":
    # 本地联合测试脚本：测试解析 + 分块
    from src.ingest.pdf_parser import load_financial_pdfs
    
    print("--- 启动分块器联合测试 ---")
    # 1. 模拟数据摄入
    docs = load_financial_pdfs()
    if not docs:
        print("❌ 未找到 PDF，分块器测试终止。")
        exit(1)
        
    # 2. 执行分块 (根据 config.yaml 自动选择策略)
    nodes = get_nodes(docs)
    
    print(f"\n✅ 分块完成！由 {len(docs)} 页 Document 裂变为 {len(nodes)} 个高精度 Node。")
    
    if nodes:
        print("\n--- 抽取第一个 Node 验证继承属性 ---")
        sample_node = nodes[0]
        print(f"Node 内容前 50 字:\n{sample_node.get_content()[:50]}...")
        print(f"继承自父级的 Metadata: {sample_node.metadata}")
        
        # 契约断言 (Sanity Check)
        assert "source" in sample_node.metadata, "❌ 致命错误：切块后丢失了文件名"
        assert "page_label" in sample_node.metadata, "❌ 致命错误：切块后丢失了物理页码"
        assert "chunk_strategy" in sample_node.metadata, "❌ 内部标签缺失"
        print("\n🎉 太棒了！元数据在裂变过程中完美继承，UI 溯源机制不可摧毁！")
