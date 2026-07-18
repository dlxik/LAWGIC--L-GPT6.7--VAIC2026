"""[eval] Chấm Q&A bằng RAGAS thật — chạy trong venv RIÊNG (ragas xung đột langchain
của project). LLM + embedding của RAGAS trỏ về FPT (OpenAI-compatible).

Chuẩn bị dataset trước (chạy pipeline, ở venv project):
    python -c "..."  -> ragas_dataset.json  {question, answer, contexts, ground_truth}

Chạy RAGAS (ở ragas-venv):
    LLM_API_KEY=... LLM_BASE_URL=https://mkp-api.fptcloud.com \
    <ragas-venv>/bin/python eval/ragas_eval.py <ragas_dataset.json>

Metric RAGAS:
    faithfulness       answer có bám context không (chống bịa)
    answer_relevancy   answer có liên quan câu hỏi không
    context_precision  context lấy về có đúng/xếp tốt không
    context_recall     context có đủ để suy ra ground_truth không
    answer_correctness answer so với ground_truth

LƯU Ý: RAGAS-judge chạy trên gpt-oss-20b (FPT) — model nhỏ làm judge kém tin cậy
hơn GPT-4. Con số RAGAS ở đây chỉ NÊN so tương đối, không tuyệt đối.
"""

import json
import os
import sys

from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

BASE = os.environ.get("LLM_BASE_URL", "https://mkp-api.fptcloud.com")
KEY = os.environ["LLM_API_KEY"]
CHAT_MODEL = os.environ.get("LLM_MODEL", "gpt-oss-20b")
EMB_MODEL = os.environ.get("EMBED_MODEL", "Vietnamese_Embedding")

data_path = sys.argv[1] if len(sys.argv) > 1 else "ragas_dataset.json"
rows = json.load(open(data_path))

# RAGAS 0.2 schema: user_input / response / retrieved_contexts / reference
ds = Dataset.from_list([
    {
        "user_input": r["question"],
        "response": r["answer"],
        "retrieved_contexts": r["contexts"],
        "reference": r.get("reference") or r["ground_truth"],
    }
    for r in rows
])

llm = LangchainLLMWrapper(ChatOpenAI(model=CHAT_MODEL, base_url=BASE, api_key=KEY, temperature=0))
emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=EMB_MODEL, base_url=BASE, api_key=KEY))

print(f"Chấm RAGAS {len(rows)} mẫu | judge={CHAT_MODEL} | embed={EMB_MODEL}")
result = evaluate(
    ds,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness],
    llm=llm,
    embeddings=emb,
)
print("\n=== KẾT QUẢ RAGAS ===")
print(result)
