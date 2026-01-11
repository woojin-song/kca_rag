import streamlit as st
import os
from legal_processor import LegalDocumentProcessor

# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="전파법 AI 튜터",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------
# 2. UI 스타일 (정형화 + 가독성 개선)
# --------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
}

/* 모바일 대응 */
@media (max-width: 640px) {
    .main .block-container {
        padding: 1rem 0.5rem !important;
    }
}

/* ------------------------------
   Answer (최종 답)
------------------------------ */
.answer-card {
    background: #f8f9fa;
    border-left: 6px solid #2f855a;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 20px;
}
.answer-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: #2f855a;
    margin-bottom: 6px;
}
.answer-text {
    font-size: 1.15rem;
    font-weight: 700;
    color: #212529;
}

/* ------------------------------
   Reasoning (조문 + 해석)
------------------------------ */
.reasoning-card {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.reasoning-clause {
    font-weight: 700;
    color: #343a40;
    margin-bottom: 4px;
}
.reasoning-text {
    color: #495057;
    font-size: 0.95rem;
    line-height: 1.6;
}

/* ------------------------------
   Summary (결론 요약)
------------------------------ */
.summary-card {
    background: #f1f3f5;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 16px;
    font-size: 0.95rem;
    color: #212529;
}

/* Chat spacing */
.stChatMessage {
    padding: 1rem !important;
    margin-bottom: 1rem !important;
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# 3. 세션 상태 초기화
# --------------------------------------------------
if "processor" not in st.session_state:
    st.session_state.processor = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_key_valid" not in st.session_state:
    st.session_state.api_key_valid = False

# --------------------------------------------------
# 4. 사이드바 – 설정
# --------------------------------------------------
with st.sidebar:
    st.header("🔑 설정")

    user_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="API 키는 세션 동안만 메모리에 유지됩니다."
    )

    if user_api_key:
        os.environ["OPENAI_API_KEY"] = user_api_key
        st.session_state.api_key_valid = True
    else:
        st.session_state.api_key_valid = False

    st.divider()

    if st.button("🚀 시스템 초기화", use_container_width=True):
        if not st.session_state.api_key_valid:
            st.error("API 키를 먼저 입력해주세요.")
        else:
            with st.spinner("법령 인덱스를 초기화하는 중..."):
                try:
                    processor = LegalDocumentProcessor()
                    result = processor.initialize()
                    st.session_state.processor = processor
                    st.success(result.get("message", "초기화 완료"))
                except Exception as e:
                    st.error(f"초기화 실패: {str(e)}")

    if st.button("🗑️ 대화 내역 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --------------------------------------------------
# 5. 메인 타이틀
# --------------------------------------------------
st.title("⚖️ 전파법규 AI 기출 튜터")

# --------------------------------------------------
# 6. 시스템 미초기화 가이드
# --------------------------------------------------
if st.session_state.processor is None:
    st.warning("### 💡 시작 가이드")
    st.markdown("""
    1. 왼쪽 사이드바에 **OpenAI API Key**를 입력하세요.  
    2. **[시스템 초기화]** 버튼을 클릭하세요.  
    3. 준비가 완료되면 전파법 문제를 입력하세요.
    """)
    st.stop()

# --------------------------------------------------
# 7. 기존 채팅 히스토리 렌더링
# --------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            data = msg["content"]

            # 최종 답
            st.markdown(f"""
            <div class="answer-card">
                <div class="answer-title">✔︎ 최종 답변</div>
                <div class="answer-text">{data.get("answer")}</div>
            </div>
            """, unsafe_allow_html=True)

            # 조문 + 해석
            for item in data.get("reasoning", []):
                st.markdown(f"""
                <div class="reasoning-card">
                    <div class="reasoning-clause">{item['clause']}</div>
                    <div class="reasoning-text">{item['interpretation']}</div>
                </div>
                """, unsafe_allow_html=True)

            # 결론 요약
            st.markdown(f"""
            <div class="summary-card">
                <strong>핵심 정리</strong><br/>
                {data.get("conclusion")}
            </div>
            """, unsafe_allow_html=True)

        else:
            st.markdown(msg["content"])

# --------------------------------------------------
# 8. 사용자 질문 처리
# --------------------------------------------------
if prompt := st.chat_input("전파법 문제를 입력하거나 '쉽게 설명해줘'라고 요청하세요"):
    # 사용자 메시지 저장
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("법령 분석 및 답변 생성 중..."):
            try:
                res_json, docs = st.session_state.processor.ask_law(
                    prompt,
                    history=st.session_state.messages[:-1]
                )

                # 최종 답
                st.markdown(f"""
                <div class="answer-card">
                    <div class="answer-title">✔︎ 최종 답변</div>
                    <div class="answer-text">{res_json.get("answer")}</div>
                </div>
                """, unsafe_allow_html=True)

                # 조문 + 해석
                for item in res_json.get("reasoning", []):
                    st.markdown(f"""
                    <div class="reasoning-card">
                        <div class="reasoning-clause">{item['clause']}</div>
                        <div class="reasoning-text">{item['interpretation']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # 결론 요약
                st.markdown(f"""
                <div class="summary-card">
                    <strong>핵심 정리</strong><br/>
                    {res_json.get("conclusion")}
                </div>
                """, unsafe_allow_html=True)

                # 참조 조문
                if docs:
                    with st.expander("📚 참조 조문 원문"):
                        for i, d in enumerate(docs, 1):
                            st.markdown(f"**[{i}]** {d.metadata.get('full_context', '')}")
                            st.write(d.page_content)
                            st.divider()

                # 응답 저장
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": res_json
                })

            except Exception as e:
                st.error(f"답변 생성 오류: {str(e)}")
                st.info("💡 JSON 포맷 또는 프롬프트 구조를 확인하세요.")
