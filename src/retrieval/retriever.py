from typing import List
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever, BM25Retriever
from llama_index.core.schema import BaseNode
from src.utils.config import load_config
from src.ingest.indexer import get_persisted_nodes

def get_hybrid_retriever(index: VectorStoreIndex, nodes: List[BaseNode] = None):
    config = load_config()
    
    # 向量检索
    vector_retriever = index.as_retriever(similarity_top_k=config['retrieval']['vector_top_k'])
    
    # 优先从缓存获取节点，解决 BM25 性能问题
    if nodes is None:
        nodes = get_persisted_nodes()
        
    if nodes:
        bm25_retriever = BM25Retriever.from_defaults(
            nodes=nodes, 
            similarity_top_k=config['retrieval']['bm25_top_k']
        )
    else:
        # Fallback to vector only if no nodes available
        return vector_retriever
    
    return QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=config['retrieval']['final_top_k'],
        mode="reciprocal_rerank",
        use_async=True
    )
