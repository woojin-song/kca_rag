import streamlit as st
import os
import time
import json
import re
from legal_processor import LegalDocumentProcessor

# --------------------------------------------------
# Page Config
# --------------------------------------------------
st.set_page_config(
    page_title="전파법 AI 튜터",
    page_icon="⚖️",
    layout="wide"
)

# --------------------------------------------------
# CSS
# --------------------------------------------------
st.markdown("""
<style>
/* 기존 스타일 */
.answer-card {
    background: #f8f9fa;
    border-left: 6px solid #2f855a;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 20px;
}
.answer-title { font-weight: 700; color: #2f855a; }

/* [수정] 본문 텍스트 완전 검정으로 변경 */
.answer-text { 
    font-size: 1.1rem; 
    font-weight: 700; 
    color: #000000; 
}

.reasoning-card {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
}
.reasoning-clause { font-weight: 700; color: #1e40af; }

/* [수정] 근거 텍스트 완전 검정으로 변경 */
.reasoning-text { 
    color: #000000; 
    margin-top: 6px; 
}

.summary-card {
    background: #f1f3f5;
    padding: 14px;
    border-radius: 8px;
    margin-top: 16px;
    /* [수정] 요약 카드 텍스트 검정 명시 */
    color: #000000;
}

.references-card {
    background: #fef3c7;
    padding: 12px;
    border-radius: 8px;
    margin-top: 12px;
    border-left: 4px solid #f59e0b;
    /* [수정] 참조 카드 텍스트 검정 명시 */
    color: #000000;
}

/* 원본 조문 스타일 */
.source-docs-container {
    margin-top: 20px;
    border-top: 2px solid #e5e7eb;
    padding-top: 16px;
}

/* [수정] 헤더 텍스트 색상 변경을 위한 클래스 (Python 코드 내 strong 태그 스타일 대응) */
.source-docs-header-text {
    color: #000000 !important;
    font-size: 1.05rem;
    font-weight: bold;
}

.source-doc-card {
    background: #fefefe;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* [수정] 문서 헤더 검정 변경 */
.source-doc-header {
    font-weight: 700;
    color: #000000;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid #e5e7eb;
}

.source-doc-meta {
    font-size: 0.85rem;
    color: #6b7280; /* 메타 정보는 약간 흐리게 유지하거나, 필요시 #000000으로 변경 */
    margin-bottom: 10px;
}

/* [수정] 문서 본문 내용 검정 변경 */
.source-doc-content {
    color: #000000;
    line-height: 1.6;
    padding: 10px;
    background: #f9fafb;
    border-radius: 6px;
    font-size: 0.95rem;
}

/* 로딩 애니메이션 */
.loading-container {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: #f0f9ff;
    border-radius: 8px;
    margin-bottom: 16px;
}

.loading-spinner {
    width: 24px;
    height: 24px;
    border: 3px solid #e0f2fe;
    border-top: 3px solid #0284c7;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.loading-text {
    color: #0369a1;
    font-weight: 600;
}

.loading-dots::after {
    content: '';
    animation: dots 1.5s steps(4, end) infinite;
}

@keyframes dots {
    0%, 20% { content: ''; }
    40% { content: '.'; }
    60% { content: '..'; }
    80%, 100% { content: '...'; }
}
</style>
""", unsafe_allow_html=True)
# --------------------------------------------------
# Session State Setup
# --------------------------------------------------
if "processor" not in st.session_state:
    st.session_state.processor = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_sources" not in st.session_state:
    st.session_state.show_sources = {}
# [변경됨] API Key 저장을 위한 세션 상태 초기화
if "api_key" not in st.session_state:
    # 이미 환경변수에 있다면 가져오고, 없으면 빈 문자열
    st.session_state.api_key = os.getenv("OPENAI_API_KEY", "")

# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    
    # [변경됨] 세션 상태의 값을 value로 사용하여 입력 유지
    input_key = st.text_input(
        "OpenAI API Key", 
        type="password", 
        value=st.session_state.api_key,
        help="API Key는 세션 동안 유지됩니다."
    )
    
    # [변경됨] 입력값이 있으면 세션 및 환경변수에 저장
    if input_key:
        st.session_state.api_key = input_key
        os.environ["OPENAI_API_KEY"] = input_key

    if st.button("🔄 시스템 초기화", use_container_width=True):
        if not os.environ.get("OPENAI_API_KEY"):
            st.error("API Key를 먼저 입력해주세요!")
        else:
            with st.spinner("초기화 중..."):
                st.session_state.processor = LegalDocumentProcessor()
                result = st.session_state.processor.initialize()
                st.success(result["message"])
    
    st.divider()
    
    if st.button("🗑️ 대화 기록 삭제", use_container_width=True):
        st.session_state.messages = []
        st.session_state.show_sources = {}
        st.rerun()
    
    st.divider()
    
    st.caption("💡 **사용 팁**")
    st.caption("- 구체적인 조문을 언급하면 정확도가 높아집니다")
    st.caption("- 이전 대화 맥락을 자동으로 고려합니다")
    st.caption("- '참조 조문 원본' 버튼으로 근거 확인 가능")

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
def render_source_documents(docs, msg_idx):
    """참조 조문 원본 렌더링"""
    st.markdown("""
    <div class="source-docs-container">
        <strong style="color: #374151; font-size: 1.05rem;">📚 참조 조문 원본</strong>
    </div>
    """, unsafe_allow_html=True)
    
    for i, doc in enumerate(docs):
        # 메타데이터 추출
        context = doc.metadata.get("full_context", "일반")
        law_refs = doc.metadata.get("law_refs", [])
        decree_refs = doc.metadata.get("decree_refs", [])
        rule_refs = doc.metadata.get("rule_refs", [])
        
        all_refs = law_refs + decree_refs + rule_refs
        refs_str = ", ".join(all_refs[:3]) if all_refs else "관련 조문 없음"
        
        # 내용 미리보기 (100자)
        content = doc.page_content
        preview = content[:100] + "..." if len(content) > 100 else content
        
        # 확장 상태 관리
        expand_key = f"expand_{msg_idx}_{i}"
        if expand_key not in st.session_state:
            st.session_state[expand_key] = False
        
        # 카드 렌더링
        st.markdown(f"""
        <div class="source-doc-card">
            <div class="source-doc-header">
                📄 문서 {i+1}
            </div>
            <div class="source-doc-meta">
                <strong>위치:</strong> {context}<br/>
                <strong>관련 조문:</strong> {refs_str}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 확장/축소 토글
        if st.session_state[expand_key]:
            st.markdown(f"""
            <div class="source-doc-content">
                {content}
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"▲ 접기", key=f"collapse_{msg_idx}_{i}", use_container_width=True):
                st.session_state[expand_key] = False
                st.rerun()
        else:
            st.markdown(f"""
            <div class="source-doc-content">
                {preview}
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"▼ 전체 보기", key=f"expand_btn_{msg_idx}_{i}", use_container_width=True):
                st.session_state[expand_key] = True
                st.rerun()

def render_loading_animation():
    """로딩 애니메이션"""
    return """
    <div class="loading-container">
        <div class="loading-spinner"></div>
        <div class="loading-text">
            <span class="loading-dots">답변을 생성하고 있습니다</span>
        </div>
    </div>
    """

# --------------------------------------------------
# Main
# --------------------------------------------------
st.title("⚖️ 전파법 AI 튜터")
st.caption("전파법규 관련 질문에 정확한 답변을 제공합니다")

# [변경됨] Processor 초기화 전 체크 (메시지 표시 방식 개선)
if st.session_state.processor is None:
    if not os.environ.get("OPENAI_API_KEY"):
        st.info("👈 좌측 사이드바에서 OpenAI API Key를 입력해주세요.")
    else:
        st.warning("⚠️ 좌측 사이드바에서 '시스템 초기화' 버튼을 눌러주세요.")
    st.stop()

# --------------------------------------------------
# Chat History Display
# --------------------------------------------------
for msg_idx, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    content = msg["content"]
    
    with st.chat_message(role):
        if role == "user":
            st.write(content)
        else:
            # assistant 메시지 렌더링
            if isinstance(content, dict):
                st.markdown(f"""
                <div class="answer-card">
                    <div class="answer-title">✔︎ 최종 답변</div>
                    <div class="answer-text">{content.get('answer', '')}</div>
                </div>
                """, unsafe_allow_html=True)
                
                if content.get('reasoning'):
                    for item in content['reasoning']:
                        st.markdown(f"""
                        <div class="reasoning-card">
                            <div class="reasoning-clause">📌 {item['clause']}</div>
                            <div class="reasoning-text">{item['interpretation']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                if content.get('conclusion'):
                    st.markdown(f"""
                    <div class="summary-card">
                        <strong>📋 핵심 정리</strong><br/>
                        {content['conclusion']}
                    </div>
                    """, unsafe_allow_html=True)
                
                if content.get('references'):
                    refs = ", ".join(content['references'])
                    st.markdown(f"""
                    <div class="references-card">
                        <strong>📚 참조 조문:</strong> {refs}
                    </div>
                    """, unsafe_allow_html=True)
                
                # 참조 조문 원본 보기 토글
                if content.get('source_docs'):
                    st.divider()
                    source_key = f"show_source_{msg_idx}"
                    
                    if source_key not in st.session_state.show_sources:
                        st.session_state.show_sources[source_key] = False
                    
                    if st.button(
                        f"{'▲ 참조 조문 원본 숨기기' if st.session_state.show_sources[source_key] else '▼ 참조 조문 원본 보기'}",
                        key=f"toggle_source_{msg_idx}",
                        use_container_width=True
                    ):
                        st.session_state.show_sources[source_key] = not st.session_state.show_sources[source_key]
                        st.rerun()
                    
                    if st.session_state.show_sources[source_key]:
                        render_source_documents(content['source_docs'], msg_idx)

# --------------------------------------------------
# Chat Input & Non-Streaming Processing
# --------------------------------------------------
prompt = st.chat_input("전파법 관련 질문을 입력하세요 (예: 무선설비 기술기준은?)")

if prompt:
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.write(prompt)
    
    # 어시스턴트 응답 생성
    with st.chat_message("assistant"):
        # 로딩 애니메이션 표시
        loading_placeholder = st.empty()
        loading_placeholder.markdown(render_loading_animation(), unsafe_allow_html=True)
        
        # ask_law() 호출 (non-streaming)
        result_dict, retrieved_docs = st.session_state.processor.ask_law(
            prompt,
            history=st.session_state.messages[:-1]
        )
        
        # 로딩 애니메이션 제거
        loading_placeholder.empty()
        
        # 답변 렌더링
        st.markdown(f"""
        <div class="answer-card">
            <div class="answer-title">✔︎ 최종 답변</div>
            <div class="answer-text">{result_dict.get('answer', '')}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 근거 렌더링 (애니메이션 효과)
        if result_dict.get('reasoning'):
            for item in result_dict['reasoning']:
                st.markdown(f"""
                <div class="reasoning-card">
                    <div class="reasoning-clause">📌 {item['clause']}</div>
                    <div class="reasoning-text">{item['interpretation']}</div>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(0.2)  # 시각 효과
        
        # 요약 렌더링
        if result_dict.get('conclusion'):
            st.markdown(f"""
            <div class="summary-card">
                <strong>📋 핵심 정리</strong><br/>
                {result_dict['conclusion']}
            </div>
            """, unsafe_allow_html=True)
        
        # 참조 조문 렌더링
        if result_dict.get('references'):
            refs = ", ".join(result_dict['references'])
            st.markdown(f"""
            <div class="references-card">
                <strong>📚 참조 조문:</strong> {refs}
            </div>
            """, unsafe_allow_html=True)
        
        # 메시지 히스토리 저장 (원본 문서 포함)
        assistant_response = {
            "answer": result_dict.get('answer', ''),
            "reasoning": result_dict.get('reasoning', []),
            "conclusion": result_dict.get('conclusion', ''),
            "references": result_dict.get('references', []),
            "source_docs": retrieved_docs
        }
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # 참조 조문 원본 보기 버튼
        if retrieved_docs:
            st.divider()
            current_msg_idx = len(st.session_state.messages) - 1
            source_key = f"show_source_{current_msg_idx}"
            st.session_state.show_sources[source_key] = False
            
            if st.button(
                "▼ 참조 조문 원본 보기",
                key=f"toggle_source_new",
                use_container_width=True
            ):
                st.session_state.show_sources[source_key] = True
                st.rerun()
