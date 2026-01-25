import google.genai as genai
import os
from PIL import Image
import json

# Streamlit 설정
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None

# --- [API 키 설정 로직은 기존 코드 그대로 유지] ---
# (정훈님이 작성하신 견고한 API 키 로딩 코드를 그대로 두시면 됩니다.)
try:
    if STREAMLIT_AVAILABLE:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = os.getenv("GEMINI_API_KEY")
        # ... (중략: 기존 파일의 복잡한 로딩 로직 그대로 유지) ...
        if not api_key:
            # 간단한 파싱 fallback 등 기존 로직 유지
            pass 
except Exception as e:
    if STREAMLIT_AVAILABLE:
        st.error(f"API 키 오류: {e}")
        st.stop()

# 클라이언트 초기화
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"초기화 오류: {e}")
    st.stop()

default_model_name = 'gemini-2.5-flash'

# --- UI 구성 ---
st.set_page_config(page_title="AI 가계부 - 입력", page_icon="📝")
st.title("📝 가계부 입력")
st.markdown("영수증을 찍거나 텍스트로 입력하면 AI가 정리해줍니다.")

# 세션 상태 초기화
if 'ledger' not in st.session_state:
    st.session_state.ledger = []

CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

# 입력 섹션
input_type = st.radio("입력 방식", ["텍스트", "이미지 캡처"], horizontal=True)
user_content = None
content_type = None

if input_type == "텍스트":
    user_content = st.text_area("내용 입력", height=150, placeholder="예: 오늘 점심 만두국 9,000원")
    content_type = 'text'
else:
    uploaded_file = st.file_uploader("이미지 업로드", type=['png', 'jpg', 'jpeg'])
    if uploaded_file:
        user_content = Image.open(uploaded_file)
        content_type = 'image'
        st.image(user_content, caption="업로드된 이미지", width=300)

# 분석 로직
if st.button("기록하기 🚀", use_container_width=True):
    if not user_content:
        st.warning("내용을 입력해주세요.")
    else:
        with st.spinner("Gemini가 분석 중입니다..."):
            prompt = f"""
            가계부 전문가로서 다음 데이터를 JSON으로 추출하세요:
            1. date (YYYY-MM-DD, 없으면 2026-01-26)
            2. item (항목명)
            3. amount (숫자만)
            4. category (선택: {CATEGORIES})
            JSON 예시: {{"date": "2026-01-26", "item": "커피", "amount": 5000, "category": "외식"}}
            """
            
            try:
                # 콘텐츠 구성 (기존 로직 활용)
                if content_type == 'text':
                    contents = [prompt + "\n\n" + user_content]
                else:
                    contents = [prompt, user_content]
                
                # 모델 호출
                response = client.models.generate_content(
                    model=default_model_name,
                    contents=contents
                )

                # 응답 처리
                if hasattr(response, 'text'):
                    clean_res = response.text.replace("```json", "").replace("```", "").strip()
                    raw_data = json.loads(clean_res)
                    
                    new_entries = []
                    # 리스트/딕셔너리 통합 처리
                    items = raw_data if isinstance(raw_data, list) else [raw_data]
                    
                    for item in items:
                        safe_entry = {
                            "date": item.get("date", "2026-01-26"),
                            "item": item.get("item", "알 수 없음"),
                            "amount": int(str(item.get("amount", 0)).replace(",","")), 
                            "category": item.get("category", "기타")
                        }
                        new_entries.append(safe_entry)
                    
                    # 저장
                    st.session_state.ledger.extend(new_entries)
                    
                    st.success(f"✅ {len(new_entries)}건 저장 완료! 왼쪽 사이드바의 'Dashboard' 메뉴에서 확인하세요.")
                
            except Exception as e:
                st.error(f"오류 발생: {e}")