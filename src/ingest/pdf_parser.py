import os
from pathlib import Path
from typing import List
from llama_index.core import Document
from llama_index.readers.file import PyMuPDFReader

# 获取全局配置路径
from src.utils.config import GLOBAL_CONFIG

def load_financial_pdfs(data_dir: str | Path = None) -> List[Document]:
    """
    加载指定目录下的所有 PDF 研报。
    强制遵循架构数据契约：每个 Document 的 metadata 必须包含 'source' 和 'page_label'。
    """
    if data_dir is None:
        # 如果未传入路径，默认使用 config.yaml 中配置的数据目录
        project_root = Path(__file__).resolve().parent.parent.parent
        data_dir = project_root / GLOBAL_CONFIG["storage"]["data_dir"].strip("./")
    else:
        data_dir = Path(data_dir)

    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"❌ 找不到数据目录: {data_dir}")

    # 获取目录下所有的 .pdf 文件
    pdf_files = list(data_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"⚠️ 警告: 在目录 {data_dir} 中未找到任何 PDF 文件。")
        return []

    print(f"📂 发现 {len(pdf_files)} 份 PDF 研报，准备提取...")

    all_documents = []
    # 使用专门针对双栏和复杂格式的 PyMuPDF 解析器
    parser = PyMuPDFReader()

    for pdf_path in pdf_files:
        file_name = pdf_path.name
        try:
            # PyMuPDFReader 默认按物理页切分，返回多个 Document
            docs_from_file = parser.load_data(file_path=str(pdf_path))
            
            # 【核心护栏】：强制执行我们的元数据契约 (Metadata Contract)
            for i, doc in enumerate(docs_from_file):
                # 默认提取器可能没有统一的键名，我们必须强行覆盖/规范化
                # 'total_pages' 等字段可以作为补充，但必须有 'source' 和 'page_label'
                
                # PyMuPDF 通常会把页码放在 metadata 的某个字段里，我们统一转换为 page_label
                raw_metadata = doc.metadata or {}
                # 有些提取器用 'page', 有些用 'source_page'
                extracted_page = raw_metadata.get("page", raw_metadata.get("source_page", str(i + 1)))
                
                # 覆写，确保绝对符合 01_architecture_data_flow.md 中的契约
                doc.metadata = {
                    "source": file_name,
                    "page_label": str(extracted_page),
                    "total_pages": raw_metadata.get("total_pages", "未知"),
                }
                
                # 排除不必要的大型无用字段，防止拖慢向量检索速度
                doc.excluded_embed_metadata_keys = ["page_label", "total_pages", "source"]
                doc.excluded_llm_metadata_keys = ["total_pages"]

                all_documents.append(doc)
            
            print(f"  ✅ 成功提取: {file_name} (共 {len(docs_from_file)} 页)")

        except Exception as e:
            print(f"  ❌ 解析失败: {file_name} - 错误信息: {str(e)}")

    print(f"🚀 数据接入完成！共计提取 {len(all_documents)} 个基础 Document 页面。")
    return all_documents


if __name__ == "__main__":
    # 本地测试脚本：验证数据契约
    print("--- 启动数据接入模块测试 ---")
    documents = load_financial_pdfs()
    
    if documents:
        print("\n--- 抽取第一个 Document 进行元数据契约验证 ---")
        sample_doc = documents[0]
        print(f"Content 预览 (前100字):\n{sample_doc.get_content()[:100]}...\n")
        print(f"Metadata 字典:\n{sample_doc.metadata}")
        
        # 契约断言 (Sanity Check)
        assert "source" in sample_doc.metadata, "❌ 违反契约：缺少 'source' 字段"
        assert "page_label" in sample_doc.metadata, "❌ 违反契约：缺少 'page_label' 字段"
        print("\n🎉 完美！元数据契约全部达标！前端可以据此实现精准跳页溯源了！")
    else:
        print("未抽取到任何文档。")
