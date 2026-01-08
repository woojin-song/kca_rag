import streamlit as st
import os
from legal_processor import LegalDocumentProcessor

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전파법 AI 튜터", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 📱 극한의 반응형 디자인 보강 CSS
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    
    /* 채팅 메시지 너비 및 여백 최적화 */
    .stChatMessage {
        padding: 1rem !important;
        margin-bottom: 1rem !important;
        border-radius: 12px !important;
    }

    /* 모바일 및 작은 화면 대응 */
    @media (max-width: 640px) {
        .main .block-container {
            padding: 1rem 0.5rem !important;
        }
        h1 { font-size: 1.4rem !important; }
        .stSubheader { font-size: 1rem !important; }
        .reasoning-box { padding: 6px !important; font-size: 0.85rem !important; }
    }

    /* 답변 카드 및 박스 스타일 */
    .reasoning-box {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    
    /* 강조 텍스트 */
    .highlight-answer {
        color: #1f77b4;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# 2. 세션 상태 초기화
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'api_key_valid' not in st.session_state:
    st.session_state.api_key_valid = False

# 3. 사이드바 - API 설정 및 관리
with st.sidebar:
    st.header("🔑 설정")
    
    # API 키 입력창
    user_api_key = st.text_input(
        "OpenAI API Key를 입력하세요", 
        type="password", 
        placeholder="sk-...",
        help="입력하신 키는 세션 동안만 메모리에 유지되며 저장되지 않습니다."
    )

    if user_api_key:
        os.environ["OPENAI_API_KEY"] = user_api_key
        st.session_state.api_key_valid = True
    else:
        st.session_state.api_key_valid = False

    st.divider()

    # 시스템 초기화 버튼
    if st.button("🚀 시스템 초기화", use_container_width=True):
        if not st.session_state.api_key_valid:
            st.error("API 키를 먼저 입력해주세요.")
        else:
            with st.spinner("법령 인덱스를 로드하고 있습니다..."):
                try:
                    proc = LegalDocumentProcessor()
                    res = proc.initialize()
                    st.session_state.processor = proc
                    st.success(res["message"])
                except Exception as e:
                    st.error(f"초기화 중 오류 발생: {str(e)}")
    
    if st.button("🗑️ 대화 내역 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 4. 메인 화면 구성
st.title("⚖️ 전파법규 AI 기출 튜터")

# 시스템 미연결 시 가이드 표시
if st.session_state.processor is None:
    st.warning("### 💡 시작 가이드")
    st.markdown("""
    1. 왼쪽 사이드바에 **OpenAI API Key**를 입력하세요.
    2. **[시스템 초기화]** 버튼을 클릭하세요.
    3. 준비가 완료되면 채팅창에 전파법 관련 문제를 입력하세요.
    """)
    st.stop()

# 5. 채팅 히스토리 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            data = msg["content"]
            st.markdown(f"#### ✅ <span class='highlight-answer'>{data.get('answer')}</span>", unsafe_allow_html=True)
            for item in data.get("reasoning", []):
                st.markdown(f"**🔹 {item['clause']}**")
                st.caption(item['interpretation'])
            st.info(data.get("conclusion"))
        else:
            st.markdown(msg["content"])

# 6. 사용자 질문 처리
if prompt := st.chat_input("문제를 입력하거나 '방금 답변을 더 쉽게 설명해줘'라고 요청하세요"):
    # 사용자 메시지 기록
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI 응답 생성
    with st.chat_message("assistant"):
        with st.spinner("법령 데이터 분석 및 답변 구성 중..."):
            try:
                # 이전 대화 기록 전달 (현재 질문 제외)
                res_json, docs = st.session_state.processor.ask_law(
                    prompt, 
                    history=st.session_state.messages[:-1]
                )
                
                # 결과 UI 출력
                st.markdown(f"#### ✅ <span class='highlight-answer'>{res_json.get('answer')}</span>", unsafe_allow_html=True)
                
                for item in res_json.get("reasoning", []):
                    with st.container():
                        st.markdown(f"""
                        <div class="reasoning-box">
                            <strong>📍 {item['clause']}</strong><br/>
                            <div style='color: #495057; margin-top: 4px;'>{item['interpretation']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.info(res_json.get("conclusion"))
                
                # 개선된 참조 조문 표시
                if docs:
                    with st.expander("📚 참조 조문 원문 확인"):
                        for i, d in enumerate(docs, 1):
                            context = d.metadata.get("full_context", "일반")
                            refs = ", ".join(d.metadata.get("law_refs", [])[:3])
                            st.write(f"**[{i}] 위치:** {context}")
                            if refs:
                                st.write(f"**관련 법조:** {refs}")
                            st.write(d.page_content)
                            st.divider()

                # 응답 기록 저장
                st.session_state.messages.append({"role": "assistant", "content": res_json})
            
            except Exception as e:
                st.error(f"답변 생성 중 오류가 발생했습니다: {str(e)}")
                st.info("💡 대부분 JSON 파싱 문제입니다. 최신 코드로 업데이트하면 해결됩니다.")