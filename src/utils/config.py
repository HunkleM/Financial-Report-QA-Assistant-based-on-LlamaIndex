import os
import yaml
from pathlib import Path
from typing import Dict, Any

# 获取项目根目录 (假设该脚本位于 src/utils/ 下)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"

def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """
    加载全局配置文件 config.yaml。
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"❌ 致命错误: 找不到配置文件 {config_path}。\n"
            f"请确保你位于项目根目录，或者该文件未被误删。"
        )
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            # print(f"✅ 成功加载全局配置: {config_path}")
            return config
    except yaml.YAMLError as e:
        raise ValueError(f"❌ 配置文件 {config_path} 存在 YAML 语法错误: {e}")

# 初始化全局单例配置对象，供其他模块直接导入
# 用法: from src.utils.config import GLOBAL_CONFIG
GLOBAL_CONFIG = load_config()

if __name__ == "__main__":
    # 测试代码：打印当前加载的配置策略
    print("--- 当前系统运行模式 ---")
    print(f"Chunking Strategy: {GLOBAL_CONFIG['chunking']['strategy']}")
    print(f"LLM (Strong):      {GLOBAL_CONFIG['llm']['strong_model']}")
    print(f"LLM (Weak):        {GLOBAL_CONFIG['llm']['weak_model']}")
    print(f"RAPTOR Enabled:    {GLOBAL_CONFIG['raptor']['use_raptor']}")
    print(f"Vector Storage:    {GLOBAL_CONFIG['storage']['chroma_persist_dir']}")
    print("------------------------")
