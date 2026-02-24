
from typing import Annotated, Any, TypedDict
from langchain_openai import ChatOpenAI
from langchain.chat_models.base import BaseChatModel
from langsmith import traceable

#inference_server_url = "http://localhost:8798/v1" # vllm server

# initialize llm and model
# connect to vllm running on port 8798
# low temperature; less creativity/hallucination

#llm = ChatOpenAI(
#    model="Qwen/Qwen3-4B",
#    openai_api_key="EMPTY",
#    openai_api_base=inference_server_url,
#    max_tokens=500,
#    temperature=0.1,
#)

# Context relevance relation of docs/input
class ContextRelevanceGrade(TypedDict):
    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    score: Annotated[int, ..., "Context Relevancy Score"]
    relevant: Annotated[
        bool, ..., "True if the retrieved documents are relevant to the prompt, False otherwise"
    ]


context_relevance_instructions = """You are a senior software engineer and RAG expert. 
Given a prompt and the set of retrieved documents, assess whether the retrieved context is relevant to the prompt.
Do the documents contain information that could help answer the query?
Explain your reasoning and provide a `score` from 1-5, and a boolean `relevant` (the boolean should be true only if score is >= 3)."""


# Answer groundness - relation of answer/docs
class AnswerGroundnessGrade(TypedDict):
    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    score: Annotated[int, ..., "Answer Groundness Score"]
    relevant: Annotated[
        bool,
        ...,
        "Provide the score on if the answer hallucinates from the documents",
    ]

answer_groundness_instructions = """You are a senior software engineer and RAG expert. 
Given a response and the set of retrieved documents, assess whether generated response is grounded in the retrieved documents.
Explain your reasoning and provide a `score` from 1-5, and a boolean `relevant` (the boolean should be true only if score is >= 3)."""

# Answer relevancy - relation of prompt/response
class AnswerRelevancyGrade(TypedDict):
    explanation: Annotated[str, ..., "Explain your reasoning for the score"]
    score: Annotated[int, ..., "Answer Relevancy Score"]
    relevant: Annotated[
        bool,
        ...,
        "Provide the score on whether the answer addresses the prompt",
    ]

answer_relevancy_instructions = """You are a senior software engineer RAG evaluator.
Assess whether the response fully and directly addresses the original prompt.
Explain your reasoning and provide a `score` from 1-5, and a boolean `relevant` (the boolean should be true only if score is >= 3)."""

# Grader LLM

# Evaluator
@traceable()
def eval_context_relevance(prompt: str, context_docs: dict, llm: BaseChatModel) -> ContextRelevanceGrade:
    """A simple evaluator for RAG answer helpfulness."""
    
    context_relevance_llm = llm.with_structured_output(
        ContextRelevanceGrade, method="json_schema", strict=True
    )

    context = context_docs["context"]

    query = f"PROMPT: {prompt}\nRetrieved Documents: {context}"
    grade = context_relevance_llm.invoke([
        {"role": "system", "content": context_relevance_instructions},
        {"role": "user", "content": query}
    ])
    
    return grade

# Evaluator
@traceable()
def eval_response_groundness(response: str, context_docs: dict, llm: BaseChatModel) -> AnswerGroundnessGrade:
    """A simple evaluator for RAG answer helpfulness."""
    
    answer_groundness_llm = llm.with_structured_output(
        AnswerGroundnessGrade, method="json_schema", strict=True
    )
    context = context_docs["context"]

    
    query = f"Response: {response}\nRetrieved Documents: {context}"
    grade = answer_groundness_llm.invoke([
        {"role": "system", "content": answer_groundness_instructions},
        {"role": "user", "content": query}
    ])
    
    return grade

# Evaluator
@traceable()
def eval_response_relevancy(prompt: str, response: str, llm: BaseChatModel) -> AnswerRelevancyGrade:
    """A simple evaluator for RAG answer helpfulness."""
    
    answer_relevancy_llm = llm.with_structured_output(
        AnswerRelevancyGrade, method="json_schema", strict=True
    )

    query = f"PROMPT: {prompt}\nResponse: {response}"
    grade = answer_relevancy_llm.invoke([
        {"role": "system", "content": answer_relevancy_instructions},
        {"role": "user", "content": query}
    ])
    
    return grade

