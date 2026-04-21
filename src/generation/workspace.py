from typing import List, Dict
from llama_index.core import VectorStoreIndex
from src.generation.llm_backend import init_llm

def generate_comparison_table(index: VectorStoreIndex, doc_names: List[str], dimension: str) -> str:
    """
    针对选定的多篇文档，就特定维度生成 Markdown 格式的对比表格，并附带冲突/共识分析。
    """
    if not doc_names or not dimension:
        return "请选择要对比的文档并输入对比维度。"
    
    if len(doc_names) < 2:
        return "对比分析需要至少选择两篇文档。"
        
    llm = init_llm()
    
    # 针对每篇文档分别进行信息检索和提取
    extracted_info = {}
    
    for doc in doc_names:
        # 构建一个针对单篇文档的过滤检索器 (简化处理)
        query_engine = index.as_query_engine(similarity_top_k=5)
        
        prompt = f"请**仅**基于来源于文档 '{doc}' 的内容，提取关于【{dimension}】的信息。务必简明扼要（100字以内）。如果文档中未明确提及，请准确回复'未提及'。"
        
        try:
            response = query_engine.query(prompt)
            extracted_info[doc] = str(response).strip()
        except Exception as e:
            extracted_info[doc] = f"提取失败: {e}"
            
    # 1. 组装 Markdown 表格
    table_md = f"### 📊 跨文档深度对比：{dimension}\n\n"
    table_md += "| 文档来源 | 提取信息 |\n"
    table_md += "| :--- | :--- |\n"
    
    for doc, info in extracted_info.items():
         clean_info = info.replace("\n", " ")
         table_md += f"| **{doc}** | {clean_info} |\n"
         
    # 2. V2.0 新增：让大模型执行一次交叉验证 (Fact-Checking Synthesis)
    synthesis_prompt = (
        f"你是一名严谨的金融审计员。以下是多份不同机构的研报中关于【{dimension}】的提取信息：\n\n"
        f"{table_md}\n\n"
        "请基于上述表格内容，给出一小段（约 100-150 字）的**『洞察结论 (Synthesis)』**。\n"
        "如果各方观点一致，请总结共识；如果存在明显的**数据冲突或观点分歧**，请务必以加粗的警告语气明确指出矛盾点。"
    )
    
    try:
        synthesis_response = llm.complete(synthesis_prompt)
        table_md += f"\n\n**💡 综合洞察 (Synthesis & Fact-Check)**：\n> {str(synthesis_response).strip()}"
    except Exception as e:
        pass # 忽略合成失败，保留表格即可
         
    return table_md
