import re
from typing import List, Dict
from llama_index.core.schema import NodeWithScore

def audit_citations(answer: str, retrieved_nodes: List[NodeWithScore]) -> Dict[str, any]:
    """
    核查回答中的引用是否与检索到的节点一致。
    """
    # 1. 提取回答中的引用模式，例如：【来源：report.pdf 第12页】
    citation_pattern = r"【来源：(.+?)(?:\s+第(\d+)页)?】"
    found_citations = re.findall(citation_pattern, answer)
    
    # 2. 提取检索节点的元数据
    node_sources = [n.metadata.get('source') for n in retrieved_nodes]
    node_pages = [str(n.metadata.get('page_label', '')) for n in retrieved_nodes]
    
    audit_results = {
        "total_citations": len(found_citations),
        "valid_citations": 0,
        "invalid_citations": [],
        "citation_accuracy": 0.0
    }
    
    for doc_name, page_num in found_citations:
        # 检查该引用是否在检索到的节点中
        match_found = False
        for i, source in enumerate(node_sources):
            if doc_name == source:
                # 如果有页码，则进一步校验页码
                if not page_num or page_num == node_pages[i]:
                    match_found = True
                    break
        
        if match_found:
            audit_results["valid_citations"] += 1
        else:
            audit_results["invalid_citations"].append(f"【来源：{doc_name} {page_num}】")
            
    if audit_results["total_citations"] > 0:
        audit_results["citation_accuracy"] = audit_results["valid_citations"] / audit_results["total_citations"]
    
    return audit_results

if __name__ == "__main__":
    # 示例测试
    test_answer = "营收增长了10%。【来源：report_A.pdf 第5页】"
    # 构造模拟节点
    from llama_index.core.schema import TextNode, NodeWithScore
    mock_node = NodeWithScore(node=TextNode(metadata={"source": "report_A.pdf", "page_label": "5"}))
    
    result = audit_citations(test_answer, [mock_node])
    print(f"Audit Result: {result}")
