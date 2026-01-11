import re
import json
from pathlib import Path
from typing import List, Dict, Tuple, Iterator
from collections import defaultdict

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter, 
    MarkdownHeaderTextSplitter
)
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from openai import OpenAI

from pydantic import BaseModel, Field

# nested model 정의
class ReasoningItem(BaseModel):
    clause: str = Field(..., description="법령 문구 또는 조문 내용")
    interpretation: str = Field(..., description="상세 해석 및 설명")

class LawResponse(BaseModel):
    """전파법 답변 구조"""
    answer: str = Field(..., description="정답 혹은 핵심 결론 (한 문장으로 간결하게)")
    reasoning: List[ReasoningItem] = Field(
        ..., 
        description="법령 문구와 해당 해석 리스트 (최소 1개 이상)"
    )
    conclusion: str = Field(..., description="최종 요약 한 줄")
    references: List[str] = Field(..., description="참조 조문 번호 리스트")

class LegalDocumentProcessor:
    """전파법규 고도화 RAG 시스템"""
    
    def __init__(
        self, 
        markdown_path: str = "data/육상무선통신사(전파법규).md", 
        source_name: str = "육상무선통신사(전파법규).pdf",
        faiss_index_path: str = "faiss_index"
    ):
        self.markdown_path = markdown_path
        self.source_name = source_name
        self.faiss_index_path = faiss_index_path
        
        self.chunks: List[Document] = []
        self.vectorstore = None
        self.dense_retriever = None
        self.bm25_retriever = None
        
        # structured output LLM (non-streaming)
        base_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.llm = base_llm.with_structured_output(LawResponse)
        
        # streaming용 OpenAI client
        self.openai_client = OpenAI()
        
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        self.patterns = {
            "law_refs": r"전파법\s?제\d+조(?:의\d+)?",
            "decree_refs": r"전파법\s?시행령\s?제\d+조",
            "rule_refs": r"전파법\s?시행규칙\s?제\d+조"
        }

    def load_and_split(self) -> List[Document]:
        loader = TextLoader(self.markdown_path, encoding="utf-8")
        raw_text = loader.load()[0].page_content

        headers_to_split_on = [
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        header_split_docs = markdown_splitter.split_text(raw_text)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=100,
            separators=["\n\d+\.", "\n\(", "\n", " "]
        )
        self.chunks = text_splitter.split_documents(header_split_docs)
        return self.chunks

    def enrich_metadata(self, doc: Document) -> Document:
        text = doc.page_content
        header_context = " > ".join([v for k, v in doc.metadata.items() if "Header" in k])
        
        doc.metadata.update({
            "law_refs": list(set(re.findall(self.patterns["law_refs"], text))),
            "decree_refs": list(set(re.findall(self.patterns["decree_refs"], text))),
            "rule_refs": list(set(re.findall(self.patterns["rule_refs"], text))),
            "source": self.source_name,
            "full_context": header_context
        })
        return doc

    def _get_standalone_question(self, question: str, history: List[Dict]) -> str:
        if not history:
            return question
        
        chat_context = "\n".join(
            f"{m['role'].capitalize()}: {m['content'] if m['role'] == 'user' else m.get('content', {}).get('conclusion', '')}"
            for m in history[-3:]
        )
        
        messages = [
            {"role": "system", "content": "너는 이전 대화를 바탕으로 독립적인 검색 질문을 생성한다. 오직 질문만 출력하라."},
            {"role": "user", "content": f"""이전 대화:
{chat_context}

현재 질문: {question}

독립된 검색 질문:"""}
        ]
        
        base_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        res = base_llm.invoke(messages)
        return res.content.split("독립된 검색 질문:")[-1].strip() if "독립된 검색 질문:" in res.content else res.content.strip()

    def load_faiss_index(self) -> bool:
        try:
            self.vectorstore = FAISS.load_local(
                self.faiss_index_path, self.embeddings, allow_dangerous_deserialization=True
            )
            self.dense_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 6})
            self.chunks = list(self.vectorstore.docstore._dict.values())
            return True
        except Exception as e:
            print(f"FAISS 로드 실패: {e}")
            return False

    def build_vectorstore(self) -> None:
        self.chunks = [self.enrich_metadata(c) for c in self.chunks]
        self.vectorstore = FAISS.from_documents(self.chunks, self.embeddings)
        self.dense_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 6})
        self.bm25_retriever = BM25Retriever.from_documents(self.chunks)
        self.bm25_retriever.k = 6
        self.vectorstore.save_local(self.faiss_index_path)

    def fusion_retrieve(self, query: str, top_k: int = 4) -> List[Document]:
        bm25_docs = self.bm25_retriever.invoke(query)
        dense_docs = self.dense_retriever.invoke(query)
        
        k_val = 60
        scores = defaultdict(float)
        doc_map = {}
        
        for rank, doc in enumerate(bm25_docs):
            key = doc.page_content.strip()
            scores[key] += 1 / (k_val + rank + 1)
            doc_map[key] = doc
        
        for rank, doc in enumerate(dense_docs):
            key = doc.page_content.strip()
            scores[key] += 1 / (k_val + rank + 1)
            doc_map[key] = doc
        
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[key] for key, _ in ranked[:top_k]]

    def ask_law(self, question: str, history: List[Dict] = None, top_k: int = 4) -> Tuple[dict, List[Document]]:
        """Non-streaming 방식 (기존 유지)"""
        standalone_q = self._get_standalone_question(question, history or [])
        docs = self.fusion_retrieve(standalone_q, top_k=top_k)
        
        context = ""
        for i, d in enumerate(docs):
            path = d.metadata.get("full_context", "일반")
            ref_info = ", ".join(d.metadata.get("law_refs", [])[:2])
            context += f"[{i+1}] 위치: {path}\n관련법규: {ref_info}\n내용: {d.page_content}\n\n"

        system_msg = f"""당신은 대한민국 전파법 전문가입니다. 제공된 [근거 자료]만을 바탕으로 정확히 답변하세요.

[근거 자료]
{context}
"""

        messages = [("system", system_msg)]
        if history:
            for m in history[-2:]:
                role = "human" if m["role"] == "user" else "assistant"
                content = m["content"] if role == "human" else m.get("content", {}).get("conclusion", "")
                messages.append((role, content))
        messages.append(("human", question))

        response: LawResponse = self.llm.invoke(messages)
        
        result_dict = {
            "answer": response.answer,
            "reasoning": [
                {"clause": item.clause, "interpretation": item.interpretation} 
                for item in response.reasoning
            ],
            "conclusion": response.conclusion,
            "references": response.references
        }
        
        return result_dict, docs

    def ask_law_stream(self, question: str, history: List[Dict] = None, top_k: int = 4) -> Iterator[Dict]:
        """
        Streaming 방식: 마커 기반 출력
        yield {"type": "token", "content": "..."}
        yield {"type": "done", "data": {...}}
        """
        standalone_q = self._get_standalone_question(question, history or [])
        docs = self.fusion_retrieve(standalone_q, top_k=top_k)
        
        context = ""
        for i, d in enumerate(docs):
            path = d.metadata.get("full_context", "일반")
            ref_info = ", ".join(d.metadata.get("law_refs", [])[:2])
            context += f"[{i+1}] 위치: {path}\n관련법규: {ref_info}\n내용: {d.page_content}\n\n"

        system_msg = f"""당신은 대한민국 전파법 전문가입니다. 제공된 [근거 자료]만을 바탕으로 정확히 답변하세요.

[근거 자료]
{context}

**중요**: 반드시 아래 형식을 엄격히 지켜 답변하세요:

<ANSWER>
정답 또는 핵심 결론 (한 문장)
</ANSWER>

<REASONING>
[
  {{"clause": "전파법 제XX조", "interpretation": "해당 조문의 상세 해석"}},
  {{"clause": "관련 법령 문구", "interpretation": "추가 설명"}}
]
</REASONING>

<SUMMARY>
최종 요약 한 줄
</SUMMARY>

<REFERENCES>
["전파법 제XX조", "전파법 시행령 제YY조"]
</REFERENCES>
"""

        messages = [{"role": "system", "content": system_msg}]
        
        if history:
            for m in history[-2:]:
                role = "user" if m["role"] == "user" else "assistant"
                content = m["content"] if role == "user" else m.get("content", {}).get("conclusion", "")
                messages.append({"role": role, "content": content})
        
        messages.append({"role": "user", "content": question})

        # OpenAI streaming 호출
        try:
            stream = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    yield {"type": "token", "content": token}
            
            yield {"type": "done", "docs": docs}
            
        except Exception as e:
            yield {"type": "error", "message": str(e)}

    def initialize(self) -> dict:
        index_path = Path(self.faiss_index_path)
        
        if index_path.exists():
            if self.load_faiss_index():
                self.bm25_retriever = BM25Retriever.from_documents(self.chunks)
                self.bm25_retriever.k = 6
                return {"success": True, "message": "기존 인덱스 로드 완료"}
        
        self.load_and_split()
        self.build_vectorstore()
        return {"success": True, "message": "새로운 인덱스 구축 완료"}
