import json
import yaml
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_recall,
    context_precision,
    faithfulness,
    answer_relevancy,
)
from src.generation.llm_backend import init_llm
from src.retrieval.retriever import get_hybrid_retriever
from src.retrieval.reranker import get_reranker
from src.ingest.indexer import build_or_load_index

def get_config():
    with open("configs/config.yaml", "r") as f:
        return yaml.safe_load(f)

def run_ragas_evaluation(test_set_path: str):
    """
    运行 RAGAS 自动化评估。
    """
    config = get_config()
    llm = init_llm()
    
    # 1. 加载测试集
    with open(test_set_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    # 2. 初始化 RAG 组件以获取实际回答
    index = build_or_load_index()
    retriever = get_hybrid_retriever(index)
    reranker = get_reranker()
    
    # 3. 收集预测结果
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    
    print(f"开始对 {len(test_data)} 个样本进行推理...")
    for item in test_data:
        q = item['question']
        # 模拟检索
        nodes = retriever.retrieve(q)
        nodes = reranker.postprocess_nodes(nodes)
        context_str = [n.get_content() for n in nodes]
        
        # 模拟生成
        response = llm.complete(f"基于上下文: {context_str}\n回答问题: {q}")
        
        questions.append(q)
        answers.append(str(response))
        contexts.append(context_str)
        ground_truths.append(item.get('reference_answer', ""))

    # 4. 构造 RAGAS 数据集
    ds = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    })
    
    # 5. 执行评估 (使用本地 LLM 作为 Judge)
    # 注意：Ragas 默认尝试使用 OpenAI，这里可能需要针对本地模型进行封装适配
    print("开始 RAGAS 指标计算...")
    result = evaluate(
        ds,
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        ],
        # llm=llm, # 传入本地模型实例
    )
    
    print("评估完成！")
    print(result)
    return result

if __name__ == "__main__":
    run_ragas_evaluation("data/test_set.json")
