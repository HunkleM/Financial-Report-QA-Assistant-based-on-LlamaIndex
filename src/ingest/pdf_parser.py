import os
from typing import List
from dotenv import load_dotenv
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document
from src.utils.config import load_config

# 加载环境变量 (读取 .env 中的 LLAMA_CLOUD_API_KEY)
load_dotenv()

def load_pdf_documents(data_dir: str) -> List[Document]:
    """
    加载 PDF，支持使用 LlamaParse 提取高质量 Markdown 格式 (复杂表格/双栏优化)。
    """
    config = load_config()
    use_llamaparse = config.get('parser', {}).get('use_llamaparse', False)
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")

    def filename_metadata_helper(file_path: str):
        return {"source": os.path.basename(file_path)}

    file_extractor = {}
    if use_llamaparse and api_key and not api_key.startswith("llx-your"):
        print("💡 [解析引擎] 启用 LlamaParse 进行深度 Markdown 解析...")
        parser = LlamaParse(
            result_type="markdown",
            api_key=api_key,
            verbose=True
        )
        file_extractor = {".pdf": parser}
    else:
        print("⚠️ [解析引擎] LlamaParse 未启用或未配置 API Key，降级使用基础解析器...")

    reader = SimpleDirectoryReader(
        input_dir=data_dir,
        required_exts=[".pdf"],
        file_extractor=file_extractor,
        file_metadata=filename_metadata_helper,
        recursive=True
    )
    
    documents = reader.load_data()
    
    # 增强：注入页码逻辑，供引用展示使用
    for i, doc in enumerate(documents):
        if "page_label" not in doc.metadata:
            # 某些解析器可能未提取页码，尝试后备方案
            doc.metadata["page_label"] = doc.metadata.get("page_number", str(i + 1))
            
    return documents

if __name__ == "__main__":
    docs = load_pdf_documents("./data")
    if docs:
        print(f"成功解析 {len(docs)} 个片段。示例内容：")
        print(docs[0].get_content()[:200])
