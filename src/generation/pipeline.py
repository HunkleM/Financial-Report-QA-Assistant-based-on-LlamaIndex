from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import PromptTemplate
from src.generation.llm_backend import init_llm
from src.generation.prompt import QA_PROMPT_TMPL, CONDENSE_PROMPT

def create_chat_engine(retriever, reranker, user_memory: str = ""):
    llm = init_llm()
    memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
    
    # 封装：在引擎层应用精排阈值（通过 Node Postprocessor）
    # 如果 top_1 的分数过低，后续 LLM 会根据 Prompt 规则拒答
    
    # V2.0 动态混入长期偏好记忆
    final_qa_prompt_str = QA_PROMPT_TMPL
    if user_memory and user_memory.strip():
        final_qa_prompt_str += f"\n\n【首席分析师 (用户) 的个人偏好与指令】\n必须严格遵守以下长期设定的分析偏好：\n{user_memory.strip()}"
        
    dynamic_qa_prompt = PromptTemplate(final_qa_prompt_str)
    
    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        node_postprocessors=[reranker],
        memory=memory,
        llm=llm,
        context_prompt=dynamic_qa_prompt.template,
        condense_prompt=CONDENSE_PROMPT.template
    )
    
    return chat_engine
