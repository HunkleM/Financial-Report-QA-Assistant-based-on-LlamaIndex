import yaml
from llama_index.core.postprocessor import SentenceTransformerRerank

def get_config():
    with open("configs/config.yaml", "r") as f:
        return yaml.safe_load(f)

def get_reranker():
    """
    配置 BGE-Reranker 精排器。
    """
    config = get_config()
    
    reranker = SentenceTransformerRerank(
        model=config['reranker']['model'],
        top_n=config['reranker']['top_n'],
        device=config['embedding']['device'] # 沿用 mps 设置
    )
    
    return reranker
