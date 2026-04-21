import yaml
from functools import lru_cache
from pathlib import Path

@lru_cache()
def load_config():
    """
    单例模式加载配置文件，避免重复 IO。
    """
    config_path = Path("configs/config.yaml")
    if not config_path.exists():
        # 提供默认配置路径后备
        config_path = Path(__file__).parent.parent.parent / "configs" / "config.yaml"
        
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
