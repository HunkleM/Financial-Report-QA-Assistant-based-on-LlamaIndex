import yaml
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings

def get_config():
    with open("configs/config.yaml", "r") as f:
        return yaml.safe_load(f)

def init_llm():
    """
    配置本地 Ollama LLM 模型（Qwen2.5）。
    """
    config = get_config()
    
    llm = Ollama(
        model=config['llm']['strong_model'],
        base_url=config['llm']['ollama_base_url'],
        temperature=config['llm']['temperature'],
        request_timeout=300.0, # 针对长文本生成的宽容超时设置
        additional_kwargs={
            "num_predict": config['llm']['max_tokens']
        }
    )
    
    # 将其设为全局默认 LLM
    Settings.llm = llm
    return llm
